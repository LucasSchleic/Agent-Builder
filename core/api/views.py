import json
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.domain.connection import Connection
from core.domain.workflow import Workflow
from core.factory.block_creators import (
    AgentBlockCreator,
    HTTPBlockCreator,
    LLMBlockCreator,
    PythonScriptBlockCreator,
)
from core.services.export_service import ExportService
from core.services.workflow_executor import WorkflowExecutor
from core.services.workflow_service import WorkflowService

WORKFLOWS_DIR = Path(settings.BASE_DIR) / "workflows"

_service = WorkflowService()
_executor = WorkflowExecutor()
_export = ExportService()

# Maps the "block_type" string sent by the frontend to the matching creator class.
_CREATORS = {
    "LLMBlock": LLMBlockCreator,
    "AgentBlock": AgentBlockCreator,
    "HTTPBlock": HTTPBlockCreator,
    "PythonScriptBlock": PythonScriptBlockCreator,
}


def _ensure_workflows_dir() -> None:
    """Create the workflows directory if it does not already exist."""
    WORKFLOWS_DIR.mkdir(exist_ok=True)


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
    try:
        wf.remove_connection(data.get("connection_id"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
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
    _ensure_workflows_dir()
    script_path = WORKFLOWS_DIR / f"{wf.name}_export.py"
    try:
        # generate_python is called first so any generation error is caught
        # before writing to disk.
        script = _export.generate_python(wf)
        _export.export_to_file(wf, str(script_path))
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"script": script, "path": str(script_path)})


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
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # Only primitive types can be serialized directly; everything else becomes a string.
    _serializable = (str, int, float, bool, list, dict, type(None))
    safe_context = {
        k: v if isinstance(v, _serializable) else str(v)
        for k, v in context.items()
    }
    return JsonResponse({"context": safe_context})
