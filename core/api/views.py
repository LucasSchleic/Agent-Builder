import json
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.domain.connection import Connection
from core.domain.workflow import Workflow
from core.factory.block_creators import (
    AgentBlockCreator,
    BufferMemoryBlockCreator,
    HTTPBlockCreator,
    LLMBlockCreator,
    PythonScriptBlockCreator,
)
from core.services.export_service import ExportService
from core.services.workflow_executor import WorkflowExecutor
from core.services.workflow_service import WorkflowService

WORKFLOWS_DIR = Path(settings.BASE_DIR) / "workflows"

# Module-level singletons: one instance per process avoids repeated construction overhead.
_service = WorkflowService()
_executor = WorkflowExecutor()
_export = ExportService()

# Maps the "block_type" string sent by the frontend to the matching creator class.
_CREATORS = {
    "LLMBlock": LLMBlockCreator,
    "AgentBlock": AgentBlockCreator,
    "HTTPBlock": HTTPBlockCreator,
    "PythonScriptBlock": PythonScriptBlockCreator,
    "BufferMemoryBlock": BufferMemoryBlockCreator,
}


def _ensure_workflows_dir() -> None:
    """Create the workflows directory if it does not already exist."""
    WORKFLOWS_DIR.mkdir(exist_ok=True)


def _sync_agent_config(wf: Workflow, block_id: str) -> None:
    """Keep AgentBlock config in sync with visual connections.

    Called after any connection change so the config always reflects the actual wiring.
    """
    from core.domain.block import AgentBlock
    try:
        block = wf.get_block(block_id)
    except ValueError:
        return
    if not isinstance(block, AgentBlock):
        return
    llm_id = ""
    tool_ids = []
    memory_id = ""
    for conn in wf.connections:
        if conn.target_block_id != block_id:
            continue
        target_port = next((p for p in block.input_ports if p.id == conn.target_port_id), None)
        if not target_port:
            continue
        if target_port.name == "llm_input":
            llm_id = conn.source_block_id
        elif target_port.name == "tool_input":
            tool_ids.append(conn.source_block_id)
        elif target_port.name == "memory_input":
            memory_id = conn.source_block_id
    block.config["llm_block_id"] = llm_id
    block.config["tool_block_ids"] = tool_ids
    block.config["memory_block_id"] = memory_id


def _load_body(request) -> dict:
    """Decode the JSON request body and return it as a dict."""
    return json.loads(request.body)


def _workflow_from_body(data: dict) -> Workflow:
    """Reconstruct a Workflow from the 'workflow' key of the request body."""
    return Workflow.from_dict(data["workflow"])


# ---------------------------------------------------------------------------
# Workflow list
# ---------------------------------------------------------------------------

@require_GET
def list_workflows(request):
    """Return the list of saved workflow filenames.

    GET /api/workflows/
    Response: {"workflows": ["wf1.json", "wf2.json", ...]}
    """
    _ensure_workflows_dir()
    return JsonResponse({"workflows": _service.list_workflows(str(WORKFLOWS_DIR))})


# ---------------------------------------------------------------------------
# Create / load / save
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def new_workflow(request):
    """Create a new empty workflow and return it.

    POST /api/workflow/new/
    Body: {"name": "my_workflow"}
    Response: {"workflow": {...}}
    """
    data = _load_body(request)
    name = data.get("name", "new_workflow")
    wf = _service.create_workflow(name)
    return JsonResponse({"workflow": wf.to_dict()})


@require_GET
def load_workflow(request, name: str):
    """Load a workflow from disk and return it.

    GET /api/workflow/load/<name>/
    Response: {"workflow": {...}}  or {"error": "..."} with 404
    """
    _ensure_workflows_dir()
    path = WORKFLOWS_DIR / name
    try:
        wf = _service.load_workflow(str(path))
        return JsonResponse({"workflow": wf.to_dict()})
    except FileNotFoundError:
        return JsonResponse({"error": f"Workflow '{name}' not found."}, status=404)
    except (KeyError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
@require_POST
def save_workflow(request):
    """Persist a workflow to disk under workflows/<name>.json.

    POST /api/workflow/save/
    Body: {"workflow": {...}}
    Response: {"status": "ok", "path": "..."}
    """
    data = _load_body(request)
    wf = _workflow_from_body(data)
    _ensure_workflows_dir()
    path = WORKFLOWS_DIR / f"{wf.name}.json"
    _service.save_workflow(wf, str(path))
    return JsonResponse({"status": "ok", "path": str(path)})


# ---------------------------------------------------------------------------
# Block operations
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def add_block(request):
    """Add a new block of the requested type to the workflow.

    POST /api/workflow/block/add/
    Body: {"workflow": {...}, "block_type": "LLMBlock"}
    Response: {"workflow": {...}}
    """
    data = _load_body(request)
    wf = _workflow_from_body(data)
    block_type = data.get("block_type")
    creator_cls = _CREATORS.get(block_type)
    if creator_cls is None:
        return JsonResponse({"error": f"Unknown block type: {block_type!r}."}, status=400)
    creator_cls().add_block_to(wf)
    return JsonResponse({"workflow": wf.to_dict()})


@csrf_exempt
@require_POST
def remove_block(request):
    """Remove a block (and its connections) from the workflow.

    POST /api/workflow/block/remove/
    Body: {"workflow": {...}, "block_id": "..."}
    Response: {"workflow": {...}}
    """
    data = _load_body(request)
    wf = _workflow_from_body(data)
    try:
        wf.remove_block(data.get("block_id"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    return JsonResponse({"workflow": wf.to_dict()})


@csrf_exempt
@require_POST
def update_block(request):
    """Merge new config values into a block's config dict.

    POST /api/workflow/block/update/
    Body: {"workflow": {...}, "block_id": "...", "config": {...}}
    Response: {"workflow": {...}}

    For PythonScriptBlock, ports are re-derived from the new script if
    script_code or function_name changes.
    """
    data = _load_body(request)
    wf = _workflow_from_body(data)
    try:
        block = wf.get_block(data.get("block_id"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    new_name = data.get("name", "").strip()
    if new_name:
        block.name = new_name

    new_config = data.get("config", {})
    block.config.update(new_config)

    # PythonScriptBlock derives its ports from the function signature.
    # Re-parse whenever the script source or entry-point name changes.
    if hasattr(block, "parse_signature") and (
        "script_code" in new_config or "function_name" in new_config
    ):
        block.parse_signature()

    return JsonResponse({"workflow": wf.to_dict()})


# ---------------------------------------------------------------------------
# Connection operations
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def add_connection(request):
    """Wire two ports together and add the connection to the workflow.

    POST /api/workflow/connection/add/
    Body: {"workflow": {...}, "source_block_id": "...", "source_port_id": "...",
           "target_block_id": "...", "target_port_id": "..."}
    Response: {"workflow": {...}}
    """
    data = _load_body(request)
    wf = _workflow_from_body(data)
    try:
        conn = Connection(
            source_block_id=data["source_block_id"],
            source_port_id=data["source_port_id"],
            target_block_id=data["target_block_id"],
            target_port_id=data["target_port_id"],
        )
        wf.add_connection(conn)
        _sync_agent_config(wf, conn.target_block_id)
    except (KeyError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"workflow": wf.to_dict()})


@csrf_exempt
@require_POST
def remove_connection(request):
    """Remove a connection from the workflow by its ID.

    POST /api/workflow/connection/remove/
    Body: {"workflow": {...}, "connection_id": "..."}
    Response: {"workflow": {...}}
    """
    data = _load_body(request)
    wf = _workflow_from_body(data)
    connection_id = data.get("connection_id")
    # Capture target before removal so we can resync the AgentBlock config.
    removed_conn = next((c for c in wf.connections if c.id == connection_id), None)
    try:
        wf.remove_connection(connection_id)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    if removed_conn:
        _sync_agent_config(wf, removed_conn.target_block_id)
    return JsonResponse({"workflow": wf.to_dict()})


# ---------------------------------------------------------------------------
# Export / run
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def export_workflow(request):
    """Generate a standalone Python script from the workflow.

    POST /api/workflow/export/
    Body: {"workflow": {...}}
    Response: {"script": "...", "path": "..."}
    """
    data = _load_body(request)
    wf = _workflow_from_body(data)
    resolve_secrets = bool(data.get("resolve_secrets", True))
    _ensure_workflows_dir()
    script_path = WORKFLOWS_DIR / f"{wf.name}.py"
    try:
        script = _export.generate_python(wf, resolve_secrets=resolve_secrets)
        _export.export_to_file(wf, str(script_path), resolve_secrets=resolve_secrets)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"script": script, "path": str(script_path)})


@csrf_exempt
@require_POST
def run_workflow_stream(request):
    """Stream workflow execution progress as Server-Sent Events.

    POST /api/workflow/run/stream/
    Body: {"workflow": {...}}
    Response: text/event-stream — one SSE message per block lifecycle event.

    Using POST (not GET) so the full workflow JSON can be sent in the body
    without URI length limits.  The frontend reads the stream via fetch() +
    ReadableStream rather than EventSource, which supports POST natively.
    """
    data = _load_body(request)
    wf = _workflow_from_body(data)
    response = StreamingHttpResponse(
        _executor.execute_workflow_stream(wf),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    # Disable proxy / nginx buffering so events reach the browser immediately.
    response["X-Accel-Buffering"] = "no"
    return response


@csrf_exempt
@require_POST
def run_workflow(request):
    """Execute the workflow locally and return the result context.

    POST /api/workflow/run/
    Body: {"workflow": {...}}
    Response: {"context": {"block_id": result, ...}}

    Non-JSON-serializable results (e.g. ChatOpenAI objects) are converted
    to their string representation so the response is always valid JSON.
    """
    data = _load_body(request)
    wf = _workflow_from_body(data)
    try:
        context = _executor.execute_workflow(wf)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # Only primitive types can be serialized directly; everything else becomes a string.
    _serializable = (str, int, float, bool, list, dict, type(None))
    safe_context = {
        k: v if isinstance(v, _serializable) else str(v)
        for k, v in context.items()
    }
    return JsonResponse({"context": safe_context})
