# Cahier des charges
## Plateforme locale de création d'agents IA

**Projet :** Agent Builder  
**Encadrant :** Francky, Practice Cyber Nord-Est, Capgemini  
**Contexte :** Stage, développement d'un POC interne  
**Date de rédaction :** 20 Avril 2026

---

## 1. Contexte et objectifs

Dans le cadre de la Practice Cyber de Capgemini, nous cherchons à accélérer la création de workflows d'agents IA pour l'automatisation de tâche à faible valeur ajoutée (tâches répétitives). Les outils existants du marché (n8n, LangFlow, etc.) nécessitent une infrastructure distante ou des dépendances cloud incompatibles avec les contraintes du réseau d'entreprise et des entreprises clientes.

L'objectif de ce projet est de développer une **plateforme légère, 100 % locale**, permettant de composer visuellement des workflows d'agents IA, et d'**exporter ces workflows sous forme d'un script Python autonome** basé sur LangChain, exécutable sans l'application.

---

## 2. Périmètre du projet (MVP)

### 2.1 Ce que le projet EST

- Une application web locale démarrée via un simple script Python
- Une interface graphique accessible dans le navigateur (type `localhost:8000`)
- Un éditeur visuel de workflows (drag & drop de blocs, connexions entre blocs)
- Un système d'export du workflow en fichier `.py` autonome

### 2.2 Ce que le projet N'EST PAS

- Un service hébergé ou cloud
- Un produit final destiné à être déployé en production
- Un clone exhaustif de LangFlow ou n8n

---

## 3. Architecture technique

### 3.1 Stack recommandée

| Composant | Technologie |
|---|---|
| Backend | Python, Django (ou Flask si justifié) |
| Interface graphique | HTML/JS dans le navigateur, bibliothèque de flow type [LangFlow](https://www.langflow.org/) ou équivalent sobre |
| Export | Génération de code Python (LangChain) |
| Exécution locale | `python workflow1.py` ou équivalent |

> **Principe directeur :** pas de technologie exotique. Chaque choix doit être justifiable par sa maintenabilité et sa lisibilité pour un développeur Python junior.

### 3.2 Contraintes réseau et API

- L'application doit fonctionner **entièrement en local** : aucune dépendance à un service externe sauf l'API GenAI configurée par l'utilisateur.
- L'utilisateur renseigne dans l'interface :
  - L'URL de base de l'API GenAI (ex. : plateforme GenAI Capgemini, OpenAI, LM Studio local)
  - Sa clé API
- Ces informations sont stockées **localement** (fichier `.env` ou équivalent), **jamais dans le code source ni dans le dépôt Git**.

---

## 4. Fonctionnalités attendues (MVP)

### 4.1 Éditeur visuel de workflows

- Interface de type "canvas", "n8n", "flowise" ou "langflow" avec des blocs connectables par des arêtes orientées
- Les blocs représentent des composants du workflow (voir section 4.2)
- Les connexions représentent le flux de données entre les blocs
- L'utilisateur peut ajouter, déplacer, connecter et supprimer des blocs
- L'interface est inspirée de LangFlow dans son fonctionnement (pas nécessairement dans son apparence)

### 4.2 Blocs disponibles (MVP)

#### Bloc LLM
- Permet de configurer un appel à un modèle de langage
- Paramètres : URL de l'API, modèle cible, température (optionnel)
- Se connecte à un bloc Agent

#### Bloc Agent
- Représente un agent LangChain
- Entrées configurables :
  - le system prompt
  - le user prompt
  - Un LLM (obligatoire)
  - Une mémoire (in-memory, non persistante — `ConversationBufferMemory` ou équivalent LangChain)
  - Un ou plusieurs Tools (ex. : bloc HTTP)
- Sortie : la réponse de l'agent

#### Bloc HTTP
- Permet d'effectuer des requêtes HTTP depuis un workflow ou d'être utilisé comme tool d'un agent
- Méthodes supportées : `GET`, `POST`, `PUT`, `DELETE`
- Paramètres : URL, headers (clé/valeur), body (JSON)
- Peut être branché directement dans un workflow OU utilisé comme tool dans un bloc Agent

#### Bloc Script Python
- Permet d'intégrer du code Python personnalisé dans le workflow
- L'utilisateur écrit son code directement dans l'interface (éditeur de code intégré)
- **Le nombre d'entrées et de sorties du bloc est automatiquement déduit** des paramètres de la fonction principale définie dans le script (ex. : `def run(input1, input2):` → 2 entrées, une sortie)
- Le bloc expose les entrées et sorties comme des ports de connexion dans le canvas

### 4.3 Gestion des workflows

- L'interface affiche la **liste de tous les fichiers `.py`** présents dans le dossier `workflows/` du projet
- Un clic sur un workflow de la liste :
  - Charge et affiche le workflow dans l'éditeur visuel
  - Permet de l'éditer
  - Permet de le sauvegarder (écrase le fichier `.py` existant, ou un nouveau si "sauvegarder sous...")
- Un bouton "Nouveau workflow" permet de repartir d'un canvas vide
- Un bouton "Sauvegarder" génère ou met à jour le fichier `.py` correspondant

### 4.4 Export du workflow en script Python autonome

- Chaque workflow est sauvegardé sous forme d'**un seul fichier `.py`**
- Ce fichier doit être **exécutable directement avec Python**, sans avoir besoin de l'application. Il peut toutefois être exécuté **en plus** dans l'application
- Il utilise **LangChain** pour la partie LLM/Agent
- Il doit être lisible et compréhensible par un développeur (pas de code généré obscur)
- Les paramètres sensibles (clé API, URL) sont lus depuis des variables d'environnement ou un fichier `.env`

---

## 5. Hors périmètre MVP (à ne pas développer sauf MVP terminé)

Les éléments suivants ne font **pas** partie du MVP et ne doivent pas être développés tant que les fonctionnalités ci-dessus ne sont pas complètes et stables :

- Mémoire persistante (base de données, fichier)
- Authentification utilisateur
- Autres types de blocs (RAG, Vector Store, parser de fichiers, etc.)
- Déploiement ou packaging de l'application
- Interface multi-utilisateurs

> **Règle absolue :** ne pas inventer de fonctionnalité. Si une idée semble bonne, la noter dans un fichier `IDEAS.md` et en parler à Francky, mais ne pas l'implémenter sans validation.

---

## 6. Qualité du code

- Le code doit être **propre, lisible, documenté et commenté**
- Les **design patterns** courants doivent être appliqués là où ils sont pertinents (Factory, Strategy, Observer, etc.) -> se référer au livre fourni (https://refactoring.guru/)
- Chaque module doit avoir une responsabilité claire (principe de responsabilité unique)
- Les noms de variables, fonctions et classes doivent être explicites, en anglais (utiliser une nomenclature)
- Un fichier `README.md` doit expliquer comment installer (pip install..) et lancer le projet

---

## 7. Consignes de travail

### 7.1 Gestion du temps

- **Ne pas rester bloqué plus d'une journée** sur un problème. Passé ce délai, contacter Francky pour débloquer la situation.
- Avancer de manière incrémentale : faire fonctionner une feature simple avant de la complexifier.

### 7.2 Versionnement

- Utiliser **son propre compte GitHub personnel** pour héberger le projet
- Créer un dépôt dédié et **inviter Francky** (Francky46) en collaborateur
- **Ne jamais pousser de clé API, mot de passe ou URL sensible** dans le dépôt, utiliser `.env` et ajouter `.env` au `.gitignore`
- Faire des commits **réguliers** avec des messages clairs, par exemple -> feature: explication, soit "bloc http : ajout de la méthode http_get()"

### 7.3 Utilisation de Claude Code

- L'utilisation de **Claude Code** est autorisée et encouragée (pas de raison de ne pas regarder vers l'avenirs), **uniquement sur PC personnel** (non compatible avec le réseau Capgemini)
- Le code produit avec Claude Code doit être **compris par le stagiaire** : si une ligne de code ne peut pas être expliquée, elle ne doit pas être gardée telle quelle
- Le code final doit **fonctionner sur le PC Capgemini** (pas de dépendances inaccessibles depuis le réseau interne)
- Si Claude Code est utilisé, **publier le dossier `.claude/`** sur le dépôt GitHub, incluant :
  - Les fichiers d'agents
  - Les skills
  - Le fichier `CLAUDE.md`
  - ⚠️ **Ne pas inclure `settings.json`** (peut contenir des informations sensibles)

### 7.4 Propriété du projet

- Ce projet **appartient au stagiaire** et est Open Source (MIT). Il peut le conserver, le publier, le faire évoluer après son stage.
- Capgemini n'en revendique pas la propriété.

---

## 8. Livrables attendus

| Livrable | Description |
|---|---|
| Dépôt GitHub | Code source complet, propre, avec `README.md` |
| Application fonctionnelle | Lançable en local via `python manage.py runserver` (ou équivalent) |
| Workflows d'exemple | Au moins 2 workflows exemples dans le dossier `workflows/` |
| Script exporté autonome | Un exemple de fichier `.py` généré, fonctionnel avec LangChain |
| `CLAUDE.md` (si Claude Code utilisé) | Documentation de l'usage de Claude Code dans le projet |

---

## 9. Ressources

- [LangChain Documentation](https://python.langchain.com/docs/)
- [LangFlow](https://www.langflow.org//) — bibliothèque JS pour les éditeurs de graphes
- [Django Documentation](https://docs.djangoproject.com/)
- [Generative AI Capgemini Platform](https://generative-eu.engine.capgemini.com/)
- Livre de design patterns fourni par Francky

---

## 10. Points de contact

| Besoin | Action |
|---|---|
| Bloqué > 1 jour | Contacter Francky directement |
| Doute sur le périmètre | En parler avant de coder |
| Nouvelle idée de fonctionnalité | La noter dans `IDEAS.md`, en discuter avec Francky |
| Problème réseau Capgemini | Contacter Francky (expérience avec les contraintes Zscaler/proxy) |

---

*Document rédigé par Francky, Practice Cyber, Capgemini, Avril 2026*