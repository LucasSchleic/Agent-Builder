# Agent Builder — How It Works

Detailed walkthrough of the three main flows: block creation, export, and execution.
Every method call in the chain is named.

---

## 1. Block Creation

### Trigger
User clicks a block button in the **Toolbox** (frontend).

### Frontend → Backend call
```
POST /api/workflow/block/add/
Body: { "workflow": {...}, "block_type": "LLMBlock" }
```

### Backend call chain

```
views.add_block(request)
  └─ _load_body(request)              # JSON.loads(request.body)
  └─ _workflow_from_body(data)        # Workflow.from_dict(data["workflow"])
       └─ Workflow.__init__()
       └─ Block.from_dict(b)          # for each saved block — dispatches on b["type"]
            └─ LLMBlock.__init__()    # (or AgentBlock, HTTPBlock, PythonScriptBlock)
            └─ Port.from_dict(p)      # reconstructs input_ports and output_ports
       └─ Connection.from_dict(c)     # reconstructs connections
  └─ _CREATORS.get(block_type)        # maps "LLMBlock" → LLMBlockCreator class
  └─ LLMBlockCreator().add_block_to(wf)          # Factory Method entry point
       └─ LLMBlockCreator._create_block()        # returns LLMBlock() with default config
            └─ LLMBlock.__init__()
                 └─ Block.__init__()             # assigns id, name, config
                 └─ self.config.setdefault(...)  # api_url, model_name, temperature, api_key_env_var
                 └─ self.output_ports = [Port(...)]
       └─ workflow.add_block(block)
            └─ self.blocks.append(block)
            └─ self.notify_subscribers()         # triggers Canvas.update() if subscribed
  └─ JsonResponse({"workflow": wf.to_dict()})
       └─ Workflow.to_dict()
            └─ block.to_dict()        # for each block
            └─ conn.to_dict()         # for each connection
```

### Key objects involved

| Class | Role |
|---|---|
| `BlockCreator` (abstract) | Defines `add_block_to(workflow)` — calls `_create_block()` then `workflow.add_block()` |
| `LLMBlockCreator` | Concrete creator — overrides `_create_block()` to return `LLMBlock()` |
| `Workflow.add_block()` | Appends block, then calls `notify_subscribers()` |
| `Workflow.notify_subscribers()` | Calls `subscriber.update(self)` on every registered Subscriber |
| `Canvas` (JS) | The only Subscriber in practice — re-renders the canvas on every update |

### Same flow for all block types

- `AgentBlock` → `AgentBlockCreator._create_block()` → sets `system_prompt`, `user_prompt`, `memory_enabled`, `llm_block_id`, `tool_block_ids`, plus input/output ports
- `HTTPBlock` → `HTTPBlockCreator._create_block()` → sets `method`, `url`, `headers`, `body`
- `PythonScriptBlock` → `PythonScriptBlockCreator._create_block()` → sets `script_code`, `function_name`, `detected_inputs`; calls `parse_signature()` if script_code is already set

---

## 2. Workflow Persistence (Save / Load)

### Save

```
POST /api/workflow/save/
Body: { "workflow": {...} }

views.save_workflow(request)
  └─ _workflow_from_body(data)         # Workflow.from_dict(...)
  └─ _service.save_workflow(wf, path)  # WorkflowService
       └─ workflow.to_dict()           # deep serialization to dict
       └─ json.dump(data, f)           # writes workflows/<name>.json
```

### Load

```
GET /api/workflow/load/<name>/

views.load_workflow(request, name)
  └─ _service.load_workflow(path)      # WorkflowService
       └─ json.load(f)                 # reads JSON from disk
       └─ Workflow.from_dict(data)
            └─ Block.from_dict(b)      # dispatches on b["type"] to correct subclass
            └─ Connection.from_dict(c)
```

### New workflow

```
POST /api/workflow/new/
Body: { "name": "my_workflow" }

views.new_workflow(request)
  └─ _service.create_workflow(name)    # WorkflowService
       └─ Workflow(name=name)          # empty workflow, fresh UUID
```

### List

```
GET /api/workflows/

views.list_workflows(request)
  └─ _service.list_workflows(dir)      # os.listdir → filter *.json files
```

---

## 3. Export

### Trigger
User clicks **Export** in the Toolbar.

### Frontend → Backend call
```
POST /api/workflow/export/
Body: { "workflow": {...} }
```

### Backend call chain

```
views.export_workflow(request)
  └─ _workflow_from_body(data)         # Workflow.from_dict(...)
  └─ _export.generate_python(wf)       # ExportService — main generation method
       │
       ├─ self.topological_sort(workflow)
       │    └─ DFS postorder on blocks (using connections as edges)
       │    └─ reversed() → dependency-first order (dependencies before dependents)
       │
       ├─ self._collect_imports(blocks)
       │    └─ checks isinstance(b, LLMBlock)    → "from langchain_openai import ChatOpenAI"
       │    └─ checks isinstance(b, AgentBlock)  → "from langchain_core.tools import Tool"
       │                                          → "from langchain.agents import create_agent"
       │                                          → "from langgraph.checkpoint.memory import MemorySaver" (if memory_enabled)
       │    └─ checks isinstance(b, HTTPBlock)   → "import requests"
       │
       ├─ self._build_port_map(workflow)
       │    └─ {target_port_id: source_block}  — one entry per connection
       │    └─ used later by PythonScriptBlock to map input ports to upstream variables
       │
       ├─ for block in sorted_blocks:
       │
       │   ── LLMBlock ──────────────────────────────────────────────────────────
       │    └─ block.generate_code_snippet()
       │         → "<var> = ChatOpenAI(base_url=..., model=..., temperature=..., api_key=os.getenv(...))"
       │
       │   ── AgentBlock ─────────────────────────────────────────────────────────
       │    └─ self._agent_glue_lines(block, workflow)
       │         ├─ looks up llm_block_id → finds LLMBlock → computes var name
       │         │    → injects "llm = <llm_var>" if var differs from "llm"
       │         └─ collects tool_block_ids → builds "tools = [<var>_tool, ...]"
       │    └─ block.generate_code_snippet()
       │         → "agent_<var> = create_agent(model=llm, tools=tools, ...)"
       │         → "result_<var> = agent_<var>.invoke({...})"
       │         → "print(result_<var>['messages'][-1].content)"
       │
       │   ── HTTPBlock (standalone — not a tool) ───────────────────────────────
       │    └─ self._is_tool_block(block.id, workflow)   → False
       │    └─ block.generate_standalone_snippet()
       │         → "result_<var> = requests.request('GET', 'http://...', headers={...})"
       │         → "print(result_<var>.json())"
       │
       │   ── HTTPBlock (tool — used by an AgentBlock) ──────────────────────────
       │    └─ self._is_tool_block(block.id, workflow)   → True
       │    └─ block.generate_code_snippet()
       │         → "def block_<var>(input=None): ..."
       │         → "<var>_tool = Tool(name='<var>', func=block_<var>, ...)"
       │
       │   ── PythonScriptBlock ─────────────────────────────────────────────────
       │    └─ block.generate_code_snippet()        → raw script_code (function definition)
       │    └─ rename def <func_name>( → def run_<var>(   (avoids name collisions)
       │    └─ for each input_port:
       │         └─ if port.id in port_map → self._output_var(source_block, workflow)
       │              ├─ LLMBlock    → "<var>"                       (the ChatOpenAI object)
       │              ├─ AgentBlock  → "result_<var>['messages'][-1].content"
       │              ├─ HTTPBlock (tool)       → "block_<var>()"
       │              ├─ HTTPBlock (standalone) → "result_<var>.json()"
       │              └─ PythonScriptBlock      → "result_<var>"
       │         └─ else → "None"
       │    └─ appends "result_<var> = run_<var>(<arg1>, <arg2>, ...)"
       │
       └─ self._resolve_env_vars(script)
            └─ regex: replaces every os.getenv('X') with repr(os.getenv('X'))
            └─ runs server-side where .env is loaded — value is hardcoded into the file
            └─ makes the exported script fully standalone (no .env needed at runtime)

  └─ _export.export_to_file(wf, script_path)
       └─ self.generate_python(wf)     # called again to write to disk
       └─ open(path, "w").write(code)  # writes workflows/<name>_export.py
  └─ JsonResponse({"script": script, "path": str(script_path)})
```

### Helper: `_to_var(name)`
Converts a block name to a Python variable name:
```
"My Custom LLM" → "my_custom_llm"
"Fetch Articles" → "fetch_articles"
```
Used everywhere a variable name must be derived from a block name.

### Output file
Written to `workflows/<workflow_name>_export.py`.
This file contains hardcoded API keys — it is in `.gitignore` and must never be committed.

---

## 4. Execution

### Trigger
User clicks **Run** in the Toolbar.

### Frontend → Backend call
```
POST /api/workflow/run/
Body: { "workflow": {...} }
```

### Backend call chain

```
views.run_workflow(request)
  └─ _workflow_from_body(data)              # Workflow.from_dict(...)
  └─ _executor.execute_workflow(wf)         # WorkflowExecutor — main entry point
       │
       ├─ workflow.validate()
       │    └─ block.validate()             # for each block:
       │         ├─ LLMBlock    → name + api_url + model_name + api_key_env_var non-empty
       │         ├─ AgentBlock  → name + llm_block_id non-empty
       │         ├─ HTTPBlock   → name + method in (GET/POST/PUT/DELETE) + url non-empty
       │         └─ PythonScript → name + script_code + function_name + no SyntaxError
       │    └─ conn.validate()              # for each connection: all 4 IDs non-empty
       │    └─ checks source/target block IDs exist in the workflow
       │
       ├─ self._workflow = workflow          # stored so prepare_inputs() can access connections
       │
       ├─ self.topological_sort(workflow)
       │    └─ DFS postorder (same algorithm as ExportService)
       │    └─ reversed() → dependency-first order
       │
       ├─ context = {}                       # shared dict: {block_id: result}
       │
       └─ for block in sorted_blocks:
            └─ self.execute_block(block, context)
                 ├─ self.prepare_inputs(block, context)
                 │    └─ for each connection where conn.target_block_id == block.id:
                 │         └─ finds the target Port by conn.target_port_id
                 │         └─ context[port.name] = context[conn.source_block_id]
                 │              (maps port name → upstream block's result value)
                 │
                 └─ block.execute(context)
                      │
                      ├─ LLMBlock.execute(context)
                      │    └─ ChatOpenAI(base_url=..., model=..., api_key=os.getenv(...))
                      │    └─ returns the ChatOpenAI object itself
                      │    └─ context[block.id] = <ChatOpenAI instance>
                      │
                      ├─ AgentBlock.execute(context)
                      │    └─ llm = context[self.config["llm_block_id"]]
                      │    └─ tools = [Tool(...) for tid in tool_block_ids]
                      │    └─ agent = create_agent(model=llm, tools=tools, ...)
                      │    └─ result = agent.invoke({"messages": [{"role": "user", "content": user_prompt}]})
                      │    └─ returns result["messages"][-1].content  (the AI's final answer)
                      │    └─ context[block.id] = "<final answer string>"
                      │
                      ├─ HTTPBlock.execute(context)
                      │    └─ requests.request(method, url, headers=..., json=body or None)
                      │    └─ returns response.json()
                      │    └─ context[block.id] = {response JSON dict}
                      │
                      └─ PythonScriptBlock.execute(context)
                           └─ exec(script_code, {}, local_vars)     # isolated namespace
                           └─ func = local_vars[function_name]
                           └─ inputs = {k: context[k] for k in detected_inputs}
                           └─ returns func(**inputs)
                           └─ context[block.id] = <return value>

  └─ safe_context = {k: v if isinstance(v, serializable) else str(v) ...}
  └─ JsonResponse({"context": safe_context})
```

### Context dict — the execution bus

The `context` dict is the central data bus:
- Key = block UUID
- Value = block result
- Also has port-name keys added by `prepare_inputs()` (e.g. `context["article_text"] = context[upstream_block_id]`)

This is how `PythonScriptBlock` gets its named inputs: `prepare_inputs()` copies `context[upstream_id]` into `context[port.name]`, then `block.execute()` reads `context["article_text"]`.

---

## 5. Block Update (Config Panel)

When the user edits a block's config fields:

```
POST /api/workflow/block/update/
Body: { "workflow": {...}, "block_id": "...", "config": {"model_name": "gpt-4"} }

views.update_block(request)
  └─ _workflow_from_body(data)
  └─ wf.get_block(block_id)
  └─ block.config.update(new_config)          # merge new values into existing config
  └─ if hasattr(block, "parse_signature"):    # only PythonScriptBlock has this
       └─ if "script_code" or "function_name" in new_config:
            └─ block.parse_signature()        # re-infer ports from new function signature
  └─ JsonResponse({"workflow": wf.to_dict()})
```

---

## 6. Connection Operations

### Add connection

```
POST /api/workflow/connection/add/
Body: { "workflow": {...}, "source_block_id": "...", "source_port_id": "...",
        "target_block_id": "...", "target_port_id": "..." }

views.add_connection(request)
  └─ Connection(source_block_id, source_port_id, target_block_id, target_port_id)
  └─ wf.add_connection(conn)
       └─ wf.get_block(source_block_id)   # validates block exists
       └─ wf.get_block(target_block_id)   # validates block exists
       └─ self.connections.append(conn)
       └─ self.notify_subscribers()
```

### Remove connection

```
POST /api/workflow/connection/remove/
Body: { "workflow": {...}, "connection_id": "..." }

views.remove_connection(request)
  └─ wf.remove_connection(connection_id)
       └─ scans self.connections for matching id
       └─ self.connections.remove(conn)
       └─ self.notify_subscribers()
```

---

## Summary diagram

```
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


    │  POST /api/workflow/export/
    ▼
views.export_workflow()
    │
    ▼
ExportService.generate_python()
    ├─ topological_sort()
    ├─ _collect_imports()
    ├─ _build_port_map()
    ├─ per-block: generate_code_snippet() / generate_standalone_snippet()
    └─ _resolve_env_vars()   ← hardcodes all os.getenv() values


    │  POST /api/workflow/run/
    ▼
views.run_workflow()
    │
    ▼
WorkflowExecutor.execute_workflow()
    ├─ workflow.validate()
    ├─ topological_sort()
    └─ for each block:
            prepare_inputs()     ← maps port names into context
            block.execute()      ← LLM / Agent / HTTP / PythonScript
            context[block.id] = result
```
