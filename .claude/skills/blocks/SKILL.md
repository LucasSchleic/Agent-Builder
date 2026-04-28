# skill: blocks
# Description: Comportement attendu de chaque type de bloc

---

## LLMBlock

Configure un appel à un modèle de langage.

### Attributs (config)
```python
api_url: str          # URL de base de l'API GenAI
model_name: str       # ex: "gpt-4o"
temperature: float    # défaut 0.7
api_key_env_var: str  # nom de la variable d'env contenant la clé, ex: "GENAI_API_KEY"
```

### Ports
- **Aucun port d'entrée** — configuré statiquement
- **Output** : `llm_output` (data_type: `"llm"`) — l'objet LLM instancié

### execute(context)
Instancie et retourne un objet LLM LangChain configuré :
```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    base_url=self.config["api_url"],
    model=self.config["model_name"],
    temperature=self.config["temperature"],
    api_key=os.getenv(self.config["api_key_env_var"])
)
return llm
```

### generate_code_snippet()
```python
llm = ChatOpenAI(base_url="...", model="...", temperature=0.7, api_key=os.getenv("GENAI_API_KEY"))
```

---

## AgentBlock

Représente un agent LangChain.

### Attributs (config)
```python
system_prompt: str
user_prompt: str          # peut contenir des variables {input}
memory_enabled: bool      # active ConversationBufferMemory
llm_block_id: str         # ID du LLMBlock connecté (obligatoire)
tool_block_ids: List[str] # IDs des HTTPBlock utilisés comme tools
```

### Ports
- **Input** : `llm_input` (data_type: `"llm"`, required: True)
- **Input** : `tool_input` (data_type: `"tool"`, required: False) — répétable
- **Output** : `agent_output` (data_type: `"str"`)

### get_dependencies()
Retourne `[self.llm_block_id] + self.tool_block_ids`

### execute(context)
1. Récupère le LLM depuis `context[llm_block_id]`
2. Récupère les tools depuis `context[tool_block_id]` pour chaque tool
3. Instancie l'agent LangChain
4. Invoque avec `user_prompt`
5. Retourne la réponse texte

---

## HTTPBlock

Effectue une requête HTTP. Peut être utilisé comme tool d'un agent.

### Attributs (config)
```python
method: str    # "GET" | "POST" | "PUT" | "DELETE"
url: str
headers: dict  # clé/valeur
body: dict     # JSON body pour POST/PUT
```

### Ports
- **Input** : `http_input` (data_type: `"any"`, required: False)
- **Output** : `http_output` (data_type: `"dict"`)

### execute(context)
```python
import requests
response = requests.request(
    method=self.config["method"],
    url=self.config["url"],
    headers=self.config["headers"],
    json=self.config["body"]
)
return response.json()
```

### Utilisation comme Tool LangChain
Quand connecté à un `AgentBlock`, le bloc HTTP est wrappé en `Tool` LangChain :
```python
from langchain.tools import Tool
tool = Tool(name=self.name, func=self.execute, description="...")
```

---

## PythonScriptBlock

Intègre du code Python personnalisé dans le workflow.

### Attributs (config)
```python
script_code: str             # code Python complet écrit par l'utilisateur
function_name: str           # nom de la fonction principale, ex: "run"
detected_inputs: List[str]   # déduits automatiquement des paramètres de la fonction
detected_outputs: List[str]  # déduits du return (simplifié : une sortie "output")
```

### Ports
Déduits automatiquement par `parse_signature()` :
- **Inputs** : un port par paramètre de la fonction principale
- **Output** : `output` (data_type: `"any"`)

### parse_signature()
```python
import ast

tree = ast.parse(self.config["script_code"])
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == self.config["function_name"]:
        self.config["detected_inputs"] = [arg.arg for arg in node.args.args]
```

### validate_script()
Vérifie que le code est parseable par `ast.parse()` sans erreur.

### execute(context)
```python
local_vars = {}
exec(self.config["script_code"], {}, local_vars)
func = local_vars[self.config["function_name"]]
inputs = {k: context[k] for k in self.config["detected_inputs"]}
return func(**inputs)
```

---

## Règles communes à tous les blocs

- Chaque bloc a un `id` uuid4 généré à l'instanciation
- `validate()` vérifie que les champs obligatoires du `config` sont renseignés
- `to_dict()` inclut toujours le champ `"type"` pour permettre la reconstruction depuis JSON
- `from_dict()` est un `classmethod` qui instancie la bonne sous-classe selon `data["type"]`
