# Agent Builder

A lightweight, fully local web application for visually composing AI agent workflows. Build pipelines by connecting blocks on a canvas, then export them as standalone Python scripts or run them directly from the interface.

No cloud, no authentication, no database — everything runs locally.

---

## Installation

**Prerequisites:** Python 3.10+, pip

```bash
git clone https://github.com/schleich6u/Agent-Builder.git
cd Agent-Builder

pip install -r requirements.txt

cp .env.example .env   # then fill in your API keys
python manage.py migrate
python manage.py runserver
```

Open [http://localhost:8000](http://localhost:8000).

### Environment variables (`.env`)

| Variable | Description |
| --- | --- |
| `GENAI_API_KEY` | API key for your GenAI provider |
| `GENAI_API_URL` | Base URL of the OpenAI-compatible API |
| `GMAIL_EMAIL` | Gmail address (for Gmail workflows) |
| `GMAIL_PASSWORD` | Gmail App Password (for Gmail workflows) |

---

## What you can do

### Build workflows visually

Drag blocks onto the canvas, connect their ports, configure each block in the side panel. Workflows are saved as JSON in `workflows/`.

### Block types

| Block | Purpose |
| --- | --- |
| **LLM** | Instantiates a language model (ChatOpenAI-compatible) |
| **Agent** | ReAct agent — uses a LLM + optional tools + optional memory |
| **HTTP** | Makes a GET/POST/PUT/DELETE request; can be wired as an agent tool |
| **Python Script** | Runs arbitrary Python code; inputs/outputs auto-detected from the function signature |
| **Buffer Memory** | Adds conversation memory to an Agent block |

### Save, load, export, run

- **Save / Load** — persist and reopen any workflow
- **Export** — generates a standalone `.py` script with all secrets resolved
- **Run** — executes the workflow locally with real-time output in the console panel (SSE streaming)

### Reusable custom blocks

Click **Généraliser** on any Python Script block to save it as a reusable template. It appears under "Blocs sauvegardés" in the toolbox and can be dragged onto any future workflow.

---

## Example workflows (included)

| File | Description |
| --- | --- |
| `simple_agent.json` | Minimal LLM → Agent pipeline |
| `memory_agent_demo.json` | Agent with conversation memory |
| `gmail_lire_et_repondre.json` | Reads 5 unread Gmail messages, generates draft replies |
| `gmail_envoyer_reponses.json` | Sends validated replies from a `.txt` file via SMTP |
| `github_activity_analyser.json` | Fetches GitHub commits via HTTP, analyses them with an agent |
| `email_priority_triage.json` | Classifies incoming emails by priority |

---

## Project structure

```text
agent_builder/
├── core/
│   ├── domain/          # Block, Workflow, Port, Connection
│   ├── factory/         # BlockCreator pattern
│   ├── services/        # Execution, export, persistence
│   └── api/             # Django JSON endpoints
├── workflows/           # Saved workflow JSON files
├── custom_blocks/       # Saved reusable block templates
└── docs/                # Architecture & specs
```

See [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for a detailed walkthrough of every flow.
