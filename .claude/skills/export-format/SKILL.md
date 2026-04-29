# skill: export-format
# Description: Règles de génération du script Python autonome et du JSON de sauvegarde

---

## Sauvegarde JSON

### Emplacement
`workflows/<nom_du_workflow>.json`

### WorkflowService

```python
class WorkflowService:

    def save_workflow(self, workflow: Workflow, path: str) -> None:
        """Serialize workflow to JSON and write to disk."""
        data = workflow.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_workflow(self, path: str) -> Workflow:
        """Read JSON file and reconstruct a Workflow instance."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Workflow.from_dict(data)

    def list_workflows(self, directory: str) -> List[str]:
        """Return all .json filenames in the workflows directory."""
        return [f for f in os.listdir(directory) if f.endswith(".json")]
```

---

## Export Python autonome

### Emplacement
`workflows/<nom_du_workflow>_export.py`

### Principe
`ExportService.generate_python(workflow)` :
1. Tri topologique des blocs (algorithme de Kahn)
2. Pour chaque bloc dans l'ordre : appel de `block.generate_code_snippet()`
3. Assemblage du script final

### Structure du script exporté

```python
# ============================================================
# Agent Builder — Export automatique
# Workflow : mon_workflow
# ============================================================

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.memory import ConversationBufferMemory
from langchain.tools import Tool
import requests

load_dotenv()

# --- Bloc : Mon LLM (LLMBlock) ---
llm = ChatOpenAI(
    base_url=os.getenv("GENAI_API_URL"),
    model="gpt-4o",
    temperature=0.7,
    api_key=os.getenv("GENAI_API_KEY")
)

# --- Bloc : Mon HTTP Tool (HTTPBlock) ---
def block_http_abc123(input=None):
    response = requests.request("GET","https://api.example.com/data", headers={})
    return response.json()

http_tool = Tool(name="Mon HTTP Tool", func=block_http_abc123, description="HTTP GET request")

# --- Bloc : Mon Agent (AgentBlock) ---
memory = ConversationBufferMemory()
agent_executor = AgentExecutor.from_agent_and_tools(
    agent=create_react_agent(llm=llm, tools=[http_tool], prompt=...),
    tools=[http_tool],
    memory=memory,
    verbose=True
)
result = agent_executor.invoke({"input": "Ton prompt ici"})
print(result)
```

### Règles du script exporté
- Lisible par un développeur Python junior
- Paramètres sensibles uniquement via `os.getenv()`
- `load_dotenv()` toujours en début de script
- Chaque bloc introduit par un commentaire `# --- Bloc : <name> (<type>) ---`
- Variables nommées d'après le nom du bloc en snake_case
- Le script doit être exécutable avec `python <fichier>.py` sans l'application

### Tri topologique (DFS suffix inverse)

```python
def topological_sort(self, workflow: Workflow) -> List[Block]:
    visited = set()
    result = []

    def dfs(block_id: str):
        visited.add(block_id)
        for conn in workflow.connections:
            if conn.source_block_id == block_id and conn.target_block_id not in visited:
                dfs(conn.target_block_id)
        result.append(block_id)

    for block in workflow.blocks:
        if block.id not in visited:
            dfs(block.id)

    return [workflow.get_block(bid) for bid in reversed(result)]
```

### ExportService

```python
class ExportService:

    def generate_python(self, workflow: Workflow) -> str:
        """Generate a standalone Python script from a workflow."""
        blocks = self.topological_sort(workflow)
        lines = [
            "# Agent Builder — Export automatique",
            f"# Workflow : {workflow.name}",
            "",
            "import os",
            "from dotenv import load_dotenv",
            "# ... autres imports selon les blocs présents",
            "",
            "load_dotenv()",
            "",
        ]
        for block in blocks:
            lines.append(f"# --- Bloc : {block.name} ({block.__class__.__name__}) ---")
            lines.append(block.generate_code_snippet())
            lines.append("")
        return "\n".join(lines)

    def export_to_file(self, workflow: Workflow, path: str) -> None:
        """Write the generated Python script to disk."""
        code = self.generate_python(workflow)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
```
