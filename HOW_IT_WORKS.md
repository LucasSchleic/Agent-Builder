# Agent Builder — How It Works

Detailed walkthrough of every flow: block creation, execution, export, streaming, memory, custom templates.
Every method call in the chain is named.

---

## Architecture overview

```text
core/
├── domain/
│   ├── blocks/              # one file per block type (refactored from block.py)
│   │   ├── base.py          # Block ABC + _to_var_name() + _memory_savers dict
│   │   ├── llm.py           # LLMBlock
│   │   ├── agent.py         # AgentBlock
│   │   ├── http.py          # HTTPBlock
│   │   ├── python_script.py # PythonScriptBlock
│   │   ├── buffer_memory.py # BufferMemoryBlock
│   │   └── __init__.py      # re-exports all classes
│   ├── block.py             # thin backward-compat shim → re-exports from blocks/
│   ├── port.py              # Port dataclass (id, name, direction, data_type, position)
│   ├── connection.py        # Connection dataclass
│   └── workflow.py          # Workflow (Publisher/Observer)
├── factory/
│   └── block_creators.py    # BlockCreator ABC + one concrete creator per type
├── services/
│   ├── workflow_service.py  # save / load / list JSON files
│   ├── export_service.py    # generate standalone Python script
│   └── workflow_executor.py # execute locally (topological sort + context dict)
├── api/
│   ├── views.py             # all Django view functions (JSON + SSE)
│   └── urls.py              # URL routing
├── static/js/               # one ES module per UML class
└── templates/index.html     # single-page app shell
```

---

## 1. Block Creation

### Trigger

User clicks a block button in the **Toolbox** (frontend) or drags it onto the canvas.

### Frontend → Backend call

```text
POST /api/workflow/block/add/
Body: { "workflow": {...}, "block_type": "LLMBlock" }
```

### Backend call chain

```text
views.add_block(request)
  └─ _load_body(request)               # json.loads(request.body)
  └─ _workflow_from_body(data)         # Workflow.from_dict(data["workflow"])
       └─ Block.from_dict(b)           # for each block — dispatches on b["type"]
            └─ LLMBlock.__init__()     # (or AgentBlock, HTTPBlock, …)
            └─ Port.from_dict(p)       # rebuilds input_ports / output_ports with saved IDs
       └─ Connection.from_dict(c)
  └─ _CREATORS.get(block_type)         # maps "LLMBlock" → LLMBlockCreator class
  └─ LLMBlockCreator().add_block_to(wf)          # Factory Method entry point
       └─ LLMBlockCreator._create_block()        # returns LLMBlock() with default config
            └─ LLMBlock.__init__()
                 └─ Block.__init__()             # assigns id (uuid4), name, config
                 └─ self.config.setdefault(...)  # api_url, model_name, temperature, api_key_env_var
                 └─ self.output_ports = [Port("llm_output", "output", "llm")]
       └─ workflow.add_block(block)
            └─ self.blocks.append(block)
            └─ self.notify_subscribers()    # Observer — triggers Canvas.update() if subscribed
  └─ JsonResponse({"workflow": wf.to_dict()})
```

### Block types and their ports

| Block | Input ports | Output port | Config keys |
| --- | --- | --- | --- |
| `LLMBlock` | none | `llm_output` (`llm`) | `api_url`, `model_name`, `temperature`, `api_key_env_var` |
| `AgentBlock` | `llm_input` (`llm`), `tool_input` (`tool`), `memory_input` (`memory`, bottom) | `agent_output` (`str`) | `system_prompt`, `user_prompt`, `llm_block_id`, `tool_block_ids`, `memory_block_id` |
| `HTTPBlock` | `http_input` (`any`) | `http_output` (`dict`) | `method`, `url`, `headers`, `body` |
| `PythonScriptBlock` | derived from function params | `output` (`any`) | `script_code`, `function_name`, `detected_inputs`, `detected_config` |
| `BufferMemoryBlock` | none | `memory_output` (`memory`) | none |

### Port.position

`Port` has an optional `position` attribute (default `None`).
When `position="bottom"`, the port is rendered on the bottom edge of the block card instead of the sides.
Currently used by `AgentBlock.memory_input` so the `BufferMemoryBlock` connection enters from below.

---

## 2. Connection Operations

### Add connection

```text
POST /api/workflow/connection/add/
Body: { "workflow": {...}, "source_block_id": "...", "source_port_id": "...",
        "target_block_id": "...", "target_port_id": "..." }

views.add_connection(request)
  └─ Connection(source_block_id, source_port_id, target_block_id, target_port_id)
  └─ wf.add_connection(conn)
       └─ wf.get_block(source_block_id)    # validates both blocks exist
       └─ wf.get_block(target_block_id)
       └─ self.connections.append(conn)
       └─ self.notify_subscribers()
  └─ _sync_agent_config(wf, conn.target_block_id)
```

### `_sync_agent_config(wf, block_id)` — keeps AgentBlock config in sync with wiring

Called after every connection add/remove.
Scans all connections targeting this block's ports and rebuilds:

- `llm_block_id`    ← source of the connection on `llm_input` port
- `tool_block_ids`  ← all sources on `tool_input` ports
- `memory_block_id` ← source of the connection on `memory_input` port

This means the AgentBlock config always reflects the actual visual wiring, without the user having to type IDs manually.

### Remove connection

```text
POST /api/workflow/connection/remove/
Body: { "workflow": {...}, "connection_id": "..." }

views.remove_connection(request)
  └─ wf.remove_connection(connection_id)
  └─ _sync_agent_config(wf, removed_conn.target_block_id)   # re-sync after removal
```

---

## 3. Workflow Persistence (Save / Load)

### Save

```text
POST /api/workflow/save/
Body: { "workflow": {...} }

views.save_workflow(request)
  └─ _workflow_from_body(data)
  └─ _service.save_workflow(wf, path)     # WorkflowService
       └─ workflow.to_dict()              # deep serialization
       └─ json.dump(data, f)              # writes workflows/<name>.json
```

### Load

```text
GET /api/workflow/load/<name>/

views.load_workflow(request, name)
  └─ _service.load_workflow(path)
       └─ json.load(f)
       └─ Workflow.from_dict(data)
            └─ Block.from_dict(b)         # dispatches on b["type"]
            └─ Connection.from_dict(c)
```

### New workflow

```text
POST /api/workflow/new/
Body: { "name": "my_workflow" }

views.new_workflow(request)
  └─ _service.create_workflow(name)
       └─ Workflow(name=name)             # empty workflow, fresh UUID
```

### List

```text
GET /api/workflows/

views.list_workflows(request)
  └─ _service.list_workflows(dir)         # os.listdir → filter *.json files
```

---

## 4. Block Config Update

When the user edits fields in the config panel and clicks **Save**:

```text
POST /api/workflow/block/update/
Body: { "workflow": {...}, "block_id": "...", "config": {"model_name": "gpt-4"}, "name": "..." }

views.update_block(request)
  └─ wf.get_block(block_id)
  └─ block.name = new_name               # if provided
  └─ block.config.update(new_config)     # merge — only touched keys are overwritten
  └─ if hasattr(block, "parse_signature"):
       └─ if "script_code" or "function_name" changed:
            └─ block.parse_signature()   # re-infer ports from new function signature
  └─ JsonResponse({"workflow": wf.to_dict()})
```

### PythonScriptBlock — `parse_signature()` and ALL_CAPS config fields

`parse_signature()` walks the function AST to:

1. Extract parameter names → rebuild `input_ports` (one port per param)
2. Detect `ALL_CAPS = <literal>` assignments at the top of the function body → `detected_config`

`detected_config` is a dict like:

```python
{
  "OUTPUT_DIR": {"label": "Output Dir", "default": "output", "value": "output"},
  "MAX_MAILS":  {"label": "Max Mails",  "default": 10,       "value": 10},
}
```

At **execute time** and **export time**, a `_ConfigInjector` AST transformer walks the function body
and replaces those constant assignments with the user-set `value`. This lets users configure a
PythonScriptBlock without editing the script code directly.

---

## 5. Execution

### Trigger

User clicks **Run** in the Toolbar.
The frontend uses the streaming endpoint — results appear in the bottom console in real time.

### Frontend → Backend call

```text
POST /api/workflow/run/stream/
Body: { "workflow": {...} }
Response: text/event-stream (SSE)
```

### Backend call chain

```text
views.run_workflow_stream(request)
  └─ _workflow_from_body(data)
  └─ StreamingHttpResponse(
         _executor.execute_workflow_stream(wf),
         content_type="text/event-stream"
     )

WorkflowExecutor.execute_workflow_stream(workflow)
  │
  ├─ workflow.validate()
  │    └─ block.validate()              # for each block — checks required config fields
  │    └─ conn.validate()               # all 4 IDs non-empty
  │
  ├─ self.topological_sort(workflow)    # DFS postorder reversed
  │
  ├─ yield _sse({"type": "start", "total": N})
  │
  └─ for block in sorted_blocks:
       ├─ yield _sse({"type": "block_start", "block_name": ..., "block_type": ...})
       ├─ self.prepare_inputs(block, context)
       ├─ result = block.execute(context)
       ├─ context[block.id] = result
       └─ yield _sse({"type": "block_done", "output": safe_result})
           (or "block_error" if an exception is raised — stream stops)

  └─ yield _sse({"type": "done", "context": safe_context})
```

### SSE event types

| Type | When | Key fields |
| --- | --- | --- |
| `start` | Workflow begins | `workflow`, `total` |
| `block_start` | Block about to execute | `block_id`, `block_name`, `block_type` |
| `block_done` | Block succeeded | `block_id`, `block_name`, `output` |
| `block_error` | Block raised exception (stream stops) | `block_id`, `error` |
| `done` | All blocks finished | `context` (full result dict) |
| `error` | Validation failed (never starts) | `error` |

### `prepare_inputs(block, context)` — port-name mapping

`AgentBlock` reads context by **block ID** (e.g. `context[llm_block_id]`).
`PythonScriptBlock` reads context by **parameter name** (e.g. `context["article_text"]`).

`prepare_inputs()` bridges the two:

```text
for conn where conn.target_block_id == block.id:
    target_port = block.input_ports.find(conn.target_port_id)
    context[target_port.name] = context[conn.source_block_id]
```

### Block execute methods

#### `LLMBlock.execute(context)`

```python
return ChatOpenAI(
    base_url=self._resolve(self.config["api_url"]),    # resolves env var names
    model=self._resolve(self.config["model_name"]),
    temperature=self.config["temperature"],
    api_key=os.getenv(self.config["api_key_env_var"]),
)
# → context[block.id] = ChatOpenAI instance
```

`_resolve(value)` — if `value` matches `^[A-Z][A-Z0-9_]*$` (POSIX env var), returns `os.getenv(value)`.
Otherwise returns the value as-is (e.g. model names like `anthropic.claude-3-haiku-…`).

#### `AgentBlock.execute(context)`

```python
llm = context[self.config["llm_block_id"]]
tools = [Tool(...) for tid in tool_block_ids]

agent_kwargs = {"model": llm, "tools": tools, ...}
if memory_block_id and memory_block_id in context:
    agent_kwargs["checkpointer"] = context[memory_block_id]   # MemorySaver instance
    invoke_config = {"configurable": {"thread_id": self.id}}  # required by LangGraph

agent = create_agent(**agent_kwargs)
result = agent.invoke({"messages": [{"role": "user", "content": user_prompt}]},
                      config=invoke_config)
# → context[block.id] = last message content (string)
```

#### `BufferMemoryBlock.execute(context)`

```python
from langgraph.checkpoint.memory import MemorySaver
if self.id not in _memory_savers:
    _memory_savers[self.id] = MemorySaver()    # created once per server process
# → context[block.id] = MemorySaver instance (same object across workflow runs)
```

`_memory_savers` is a **module-level dict** in `base.py`.
It persists across Django requests (same Python process), which is how conversation history survives
multiple workflow runs. It is cleared when the dev server restarts.

#### `HTTPBlock.execute(context)`

```python
response = requests.request(method, url, headers=headers, json=body or None)
# → context[block.id] = response.json()
```

#### `PythonScriptBlock.execute(context)`

```python
# 1. Inject user-configured ALL_CAPS values via AST transformer
tree = _ConfigInjector(overrides).visit(ast.parse(script_code))
script = ast.unparse(tree)

# 2. Execute in isolated namespace
exec(script, {}, local_vars)
func = local_vars[function_name]
inputs = {k: context[k] for k in detected_inputs}
# → context[block.id] = func(**inputs)
```

### Context dict — the execution bus

```python
context = {
    "uuid-llm-1":     "<ChatOpenAI instance>",
    "uuid-memory-1":  "<MemorySaver instance>",
    "uuid-agent-1":   "The answer is 42",
    "llm_input":      "<ChatOpenAI instance>",   # added by prepare_inputs (port name)
    "memory_input":   "<MemorySaver instance>",
}
```

---

## 6. Export

### Trigger

User clicks **Export** in the Toolbar.
A modal appears with a checkbox: **"Inclure les clés API"**.

### Frontend → Backend call

```text
POST /api/workflow/export/
Body: { "workflow": {...}, "resolve_secrets": true|false }
```

### Backend call chain

```text
views.export_workflow(request)
  └─ wf = _workflow_from_body(data)
  └─ resolve_secrets = data.get("resolve_secrets", True)
  └─ _export.generate_python(wf, resolve_secrets=resolve_secrets)
       │
       ├─ self.topological_sort(workflow)
       │    └─ DFS postorder reversed — dependencies come first
       │
       ├─ self._collect_imports(blocks)
       │    ├─ LLMBlock present        → "from langchain_openai import ChatOpenAI"
       │    ├─ AgentBlock/HTTPBlock    → "from langchain_core.tools import Tool"
       │    ├─ AgentBlock              → "from langchain.agents import create_agent"
       │    ├─ BufferMemoryBlock       → "from langgraph.checkpoint.memory import MemorySaver"
       │    └─ HTTPBlock               → "import requests"
       │
       ├─ self._build_port_map(workflow)
       │    └─ {target_port_id: source_block}  — used by PythonScriptBlock call args
       │
       ├─ for block in sorted_blocks:
       │    print "# --- Bloc : <name> (<type>) ---"
       │
       │   ── LLMBlock ──────────────────────────────────────────────────────────
       │    └─ block.generate_code_snippet()
       │         → "llm = ChatOpenAI(base_url=os.getenv('GENAI_API_URL'), ...)"
       │         LLMBlock._snippet_value(value) detects UPPER_SNAKE_CASE → emits os.getenv(...)
       │         Otherwise keeps the value as a literal (model names are NOT env vars)
       │
       │   ── BufferMemoryBlock ───────────────────────────────────────────────
       │    └─ block.generate_code_snippet()
       │         → "<var> = MemorySaver()"
       │
       │   ── AgentBlock ─────────────────────────────────────────────────────────
       │    └─ self._agent_glue_lines(block, workflow)
       │         ├─ "llm = <llm_var>"          if llm var name differs from "llm"
       │         ├─ "tools = [<var>_tool, ...]"
       │         └─ "checkpointer = <mem_var>" if memory_block_id is set
       │    └─ block.generate_code_snippet()
       │         without memory:
       │           → "agent_<var> = create_agent(...)"
       │           → "result_<var> = agent_<var>.invoke({...})"
       │           → "print(result_<var>['messages'][-1].content)"
       │         with memory (interactive loop):
       │           → "agent_<var> = create_agent(..., checkpointer=checkpointer)"
       │           → "while True: user_input = input(...); agent.invoke(...)"
       │
       │   ── HTTPBlock (standalone) ──────────────────────────────────────────
       │    └─ self._is_tool_block() → False
       │    └─ block.generate_standalone_snippet()
       │         → "result_<var> = requests.request(...)"
       │
       │   ── HTTPBlock (tool — wired to AgentBlock) ──────────────────────────
       │    └─ self._is_tool_block() → True
       │    └─ block.generate_code_snippet()
       │         → "def block_<var>(input=None): ..."
       │         → "<var>_tool = Tool(name=..., func=block_<var>, ...)"
       │
       │   ── PythonScriptBlock ─────────────────────────────────────────────
       │    └─ block.generate_code_snippet()   (already has ALL_CAPS values injected)
       │    └─ rename: def <func_name>( → def run_<var>(   (avoids name collisions)
       │    └─ for each input_port:
       │         → self._output_var(port_map[port.id])   if connected
       │         → "None"                                 if not connected
       │    └─ "result_<var> = run_<var>(<arg1>, <arg2>)"
       │
       └─ self._resolve_env_vars(script, resolve=resolve_secrets)
            ├─ resolve=True  → regex replaces os.getenv('X') with repr(os.getenv('X'))
            │                  bakes in the actual value — script runs without .env
            └─ resolve=False → replaces os.getenv('X') with repr("INSERER VOTRE CLE")
                               safe to share — no secrets in the file

  └─ _export.export_to_file(wf, script_path, resolve_secrets)
       └─ open(path, "w").write(code)    # writes workflows/<name>.py
  └─ JsonResponse({"script": script, "path": path})
```

### `_to_var(name)` / `_to_var_name(name)`

Converts a block name to a valid Python snake_case variable name:

```text
"My Custom LLM" → "my_custom_llm"
"Buffer Memory" → "buffer_memory"
```

Used everywhere a variable name must be derived from a block name.

---

## 7. Custom Block Templates ("Généraliser")

Allows saving a `PythonScriptBlock` (with its script, function name, and ALL_CAPS config)
as a reusable template stored in `custom_blocks/`.

### Save a template

```text
POST /api/blocks/save_custom/
Body: { "block": {...} }     ← the block's to_dict() output from state.workflow

views.save_custom_block(request)
  └─ _to_var_name(block["name"])        # slug for the filename, e.g. "mon_formateur"
  └─ json.dump(block_data, ...)         # writes custom_blocks/<slug>.json
```

### List templates

```text
GET /api/blocks/custom/
Response: { "blocks": [{"filename": "mon_formateur.json", "data": {...}}, ...] }

views.list_custom_blocks(request)
  └─ glob("custom_blocks/*.json")       # alphabetical order
```

### Add a template to a workflow

```text
POST /api/workflow/block/add_custom/
Body: { "workflow": {...}, "template": {...} }

views.add_custom_block(request)
  └─ Block.from_dict(template)          # reconstructs full PythonScriptBlock (ports included)
  └─ block.id = str(uuid.uuid4())       # fresh ID — avoids collision with the original
  └─ wf.add_block(block)
```

Using `from_dict` (rather than constructing manually) preserves the serialized ports exactly,
including their UUIDs relative to the template — the only change is the top-level block ID.

### Frontend flow

1. User selects a `PythonScriptBlock` on canvas → config panel shows **"Généraliser"** button (purple border).
2. Click → `ConfigPanel._generalize(block)` POSTs to `/api/blocks/save_custom/`.
3. A `CustomEvent('customBlockSaved')` is dispatched on `document`.
4. `Toolbox.loadCustomBlocks()` listens for that event → re-fetches `/api/blocks/custom/` → re-renders the "Blocs sauvegardés" section.
5. Custom block buttons support both click and drag-onto-canvas (uses `application/custom-block` MIME type in `dataTransfer` to distinguish from standard block drags).

---

## 8. Summary diagram

```text
Frontend (JS)
    │  POST /api/workflow/block/add/
    ▼
views.add_block()
    │
    ▼
BlockCreator.add_block_to()          ← Factory Method
    │
    ▼
Block.__init__()  +  Workflow.add_block()
                              │
                              ▼
                    Workflow.notify_subscribers()
                              │
                              ▼
                         Canvas.update()  (JS)


    │  POST /api/workflow/connection/add/
    ▼
views.add_connection()
    │
    ├─ wf.add_connection(conn)
    └─ _sync_agent_config()   ← rebuilds llm_block_id / tool_block_ids / memory_block_id


    │  POST /api/workflow/run/stream/
    ▼
views.run_workflow_stream()
    │
    ▼
WorkflowExecutor.execute_workflow_stream()      → SSE to browser console panel
    ├─ workflow.validate()
    ├─ topological_sort()
    └─ for each block:
            prepare_inputs()       ← maps port names into context
            block.execute()        ← LLM / Agent / HTTP / PythonScript / BufferMemory
            context[block.id] = result
            yield SSE event


    │  POST /api/workflow/export/
    ▼
views.export_workflow()
    │
    ▼
ExportService.generate_python(workflow, resolve_secrets)
    ├─ topological_sort()
    ├─ _collect_imports()
    ├─ _build_port_map()
    ├─ per-block: generate_code_snippet() / generate_standalone_snippet()
    └─ _resolve_env_vars()   ← bakes in values OR injects "INSERER VOTRE CLE"


    │  POST /api/blocks/save_custom/        (Généraliser)
    ▼
views.save_custom_block()
    └─ json.dump(block.to_dict(), custom_blocks/<slug>.json)

    │  POST /api/workflow/block/add_custom/ (use saved template)
    ▼
views.add_custom_block()
    └─ Block.from_dict(template) + new UUID → wf.add_block()
```
