# CLAUDE.md — Agent Builder

Fichier de configuration pour Claude Code.  
Ce fichier décrit le projet, ses conventions, son architecture et les règles de travail à respecter.

---

## Présentation du projet

**Agent Builder** est une application web locale permettant de composer visuellement des workflows d'agents IA, de les sauvegarder et de les exporter sous forme de scripts Python autonomes basés sur LangChain.

- Stack : Python, Django, HTML/JS natif
- Exécution : 100 % locale (`python manage.py runserver`)
- Pas de cloud, pas d'authentification, pas de multi-utilisateur

---

## Structure du projet

```
agent_builder/
├── manage.py                   # Point d'entrée Django
├── .env                        # Clés API et URL — jamais versionné
├── .gitignore
├── README.md
├── IDEAS.md
│
├── agent_builder/              # Configuration Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── core/                       # Application principale Django
│   ├── domain/                 # Couche Domaine
│   │   ├── workflow.py         # Classe Workflow (Publisher Observer)
│   │   ├── block.py            # Classe abstraite Block + LLMBlock, AgentBlock, HTTPBlock, PythonScriptBlock
│   │   ├── port.py             # Classe Port
│   │   └── connection.py       # Classe Connection
│   │
│   ├── factory/                # Couche Factory Method
│   │   └── block_creators.py   # BlockCreator (abstraite) + créateurs concrets
│   │
│   ├── services/                # Couche Services applicatifs
│   │   ├── workflow_service.py  # Création, chargement, sauvegarde des workflows
│   │   ├── export_service.py    # Génération du script Python autonome
│   │   └── workflow_executor.py # Exécution locale (tri topologique + contexte)
│   │
│   ├── api/
│   │   ├── views.py            # Vues Django retournant du JSON
│   │   └── urls.py
│   │
│   ├── tests/                   # Tests unitaires
│   └── templates/
│       └── index.html          # Frontend (canvas, toolbox, toolbar)
│
├── docs/
│   ├── img/                    # Diagrammes UML (PNG)
│   ├── uml/
│   │   └── DiagClass.puml
│   ├── Conception.md
│   └── cahier-des-charges-Lucas.md
│
├── .claude/
│   └── skills/                 # Skills consultés par Claude Code
│       ├── blocks/SKILL.md
│       └── export-format/SKILL.md
│
└── workflows/                  # Fichiers JSON des workflows sauvegardés
```

---

## Architecture et design patterns

### Packages

| Package | Rôle |
|---|---|
| `domain/` | Objets métier : Workflow, Block, Port, Connection |
| `factory/` | Création des blocs (Factory Method) |
| `services/` | Opérations globales : persistance, export, exécution |
| `api/` | Exposition des services au frontend via JSON |
| `templates/` | Interface utilisateur (canvas, toolbox, toolbar) |

### Pattern Factory Method

- `BlockCreator` (abstraite) expose `add_block_to(workflow)` et `create_block()` (protégée)
- Créateurs concrets : `LLMBlockCreator`, `AgentBlockCreator`, `HTTPBlockCreator`, `PythonScriptBlockCreator`
- La `Toolbox` délègue toujours la création à un créateur — elle ne construit jamais de bloc directement

### Pattern Observer

- `Workflow` est le Publisher : il maintient une liste de `Subscriber` et appelle `notify_subscribers()` après chaque modification
- `Canvas` implémente `Subscriber` et sa méthode `update(workflow)` — c'est le seul composant UI abonné
- Ne pas contourner ce mécanisme en appelant directement le Canvas depuis le domaine

### Composants UI

| Composant | Rôle |
|---|---|
| `Toolbox` | Ajoute des blocs au workflow via un `BlockCreator` |
| `Toolbar` | Actions globales : nouveau, sauvegarder, charger, exporter, exécuter |
| `Canvas` | Zone d'édition principale — abonné au `Workflow` via Observer |
| `WorkflowListPanel` | Liste les workflows sauvegardés disponibles au chargement |
| `BlockUI` | Représentation visuelle d'un bloc sur le canvas |

### Exécution des workflows

- `WorkflowExecutor` ordonne les blocs via un **tri topologique (DFS suffixe inversé)**
- Il prépare les entrées de chaque bloc depuis un `context` partagé (dict Python)
- Il appelle `block.execute(context)` dans l'ordre

### Persistance

- Format : **JSON** dans `workflows/`
- Chaque objet métier expose `to_dict()` et `from_dict(data)`
- `WorkflowService` orchestre lecture/écriture — jamais le domaine directement

Schéma JSON d'un workflow :

```json
{
  "id": "uuid-string",
  "name": "nom_du_workflow",
  "blocks": [
    {
      "id": "uuid-block",
      "type": "LLMBlock",
      "name": "Mon LLM",
      "config": { "api_url": "...", "model_name": "...", "temperature": 0.7 },
      "input_ports": [
        { "id": "...", "name": "input", "direction": "input", "data_type": "str", "required": true }
      ],
      "output_ports": [
        { "id": "...", "name": "output", "direction": "output", "data_type": "llm", "required": false }
      ]
    }
  ],
  "connections": [
    {
      "id": "uuid-conn",
      "source_block_id": "...",
      "source_port_id": "...",
      "target_block_id": "...",
      "target_port_id": "..."
    }
  ]
}
```

---

## Références UML
- Diagramme de classes : `docs/uml/DiagClass.puml`

---

## Skills

Les skills sont dans `.claude/skills/`. Consulter le skill correspondant avant toute tâche.

| Skill | Quand le consulter |
|---|---|
| `blocks` | Avant d'implémenter ou modifier un type de bloc |
| `export-format` | Avant de toucher à `export_service.py` ou `workflow_service.py` |

---

## Conventions de code

- **Langue** : code et commentaires en **anglais**
- **Nommage** :
  - Classes : `PascalCase`
  - Fonctions et variables : `snake_case`
  - Constantes : `UPPER_SNAKE_CASE`
- **Docstrings** : toutes les classes et méthodes publiques en ont une
- **Interface `Block`** : tout bloc concret doit implémenter `execute(context)`, `generate_code_snippet()`, `validate()`, `to_dict()` et `from_dict(data)`
- **Responsabilité unique** : chaque module a un rôle clair — ne pas faire déborder les services dans le domaine, ni le domaine dans l'UI
- **Pas de code obscur** : tout code généré doit pouvoir être expliqué ligne par ligne

---

## Règles absolues

- Ne **jamais** commettre de clé API, mot de passe ou URL sensible — tout passe par `.env`
- Ne **jamais** implémenter une fonctionnalité hors MVP sans validation de Francky — noter l'idée dans `IDEAS.md`
- Ne **jamais** introduire de dépendance inaccessible depuis le réseau Capgemini
- Ne **pas** mélanger les couches : le domaine n'importe pas les services, les services n'importent pas l'UI

---

## Périmètre MVP

### Dans le périmètre

- Blocs : LLM, Agent, HTTP, Script Python
- Canvas drag & drop avec connexions orientées
- Sauvegarde / chargement / nouveau workflow
- Export en script `.py` autonome LangChain
- Exécution locale depuis l'interface

### Hors périmètre (ne pas développer)

- Authentification
- Mémoire persistante (base de données)
- Multi-utilisateur
- Déploiement cloud
- Blocs avancés (RAG, Vector Store, parsers...)

---

## Commits

Format : `type: description courte en anglais`

| Type | Usage |
|---|---|
| `feat` | Nouvelle fonctionnalité |
| `fix` | Correction de bug |
| `refactor` | Refactoring sans changement de comportement |
| `docs` | Documentation uniquement |
| `chore` | Tâche technique (config, dépendances...) |

Exemples :
```
feat: add HTTPBlock execute method
fix: topological sort fails on disconnected graph
refactor: extract port validation to Port.validate()
```

---

## Ce que Claude Code peut faire sans demander

- Créer ou modifier des fichiers dans la structure définie
- Ajouter des docstrings et commentaires
- Écrire des tests unitaires dans `core/tests/`
- Refactorer du code existant tant que le comportement est préservé
- Committer et **pusher** sur git après chaque modification significative

## Ce que Claude Code doit demander avant de faire

- Ajouter une dépendance Python (`pip install`)
- Créer un nouveau type de bloc (hors MVP)
- Modifier la structure de sérialisation JSON des workflows
- Changer l'architecture ou introduire un nouveau pattern

---

## Ressources

- [LangChain Docs](https://python.langchain.com/docs/)
- [Django Docs](https://docs.djangoproject.com/)
- [Refactoring Guru — Design Patterns](https://refactoring.guru/design-patterns)
- [Generative AI Capgemini](https://generative-eu.engine.capgemini.com/)
- Cahier des charges : `docs/cahier-des-charges-Lucas.md`
- Dossier de conception : `docs/Conception.md`