# IMPROVEMENTS — Agent Builder

Améliorations identifiées, classées par priorité (effort × valeur).

---

## Niveau 1 — Rapide et utile

### 1. Bandeau de version en bas
**Effort** : ~30 min — HTML/CSS uniquement  
**Valeur** : Cosmétique mais professionnel  
Afficher un footer fixe avec le numéro de version de l'app.

---

### 2. Exemple de code par défaut pour les PythonScriptBlocks
**Effort** : ~15 min — modifier `PythonScriptBlockCreator`  
**Valeur** : Aide à la prise en main  
Pré-remplir `script_code` avec un exemple minimal (`def run(input): return input`) à la création d'un nouveau bloc.

---

### 3. Champs configurables dans les PythonScriptBlocks (convention ALL_CAPS)
**Effort** : ~2-3h — AST dans `parse_signature()` + config panel + exécution  
**Valeur** : Permet de paramétrer un bloc sans toucher au code brut  
Toute variable `ALL_CAPS` assignée en début de fonction est détectée comme champ de config et exposée dans l'IHM :
```python
def run(emails):
    OUTPUT_DIR = 'email_drafts'   # → champ "Output Dir" éditable dans le config panel
    MAX_MAILS  = 5                # → champ "Max Mails" éditable dans le config panel
    ...
```
À l'exécution, les valeurs saisies dans l'IHM remplacent les valeurs par défaut du script.  
Détection via AST (`ast.Assign` avec cible `ast.Name` en majuscules), valeur par défaut = literal du script.

---

## Niveau 2 — Valeur réelle, effort modéré

### 4. Export avec/sans API key (popup + case à cocher)
**Effort** : ~2-3h — modal JS + logique dans `ExportService`  
**Valeur** : Sécurité — évite de hardcoder les clés dans les scripts exportés  
Avant l'export, afficher une modale avec une case à cocher. Si déscochée, l'export génère `os.getenv("GENAI_API_KEY")` au lieu de la valeur résolue.

---

### 5. ConversationBufferMemory réellement câblé pour les AgentBlocks
**Effort** : ~2-3h — modifier `AgentBlock.execute()` + `generate_code_snippet()`  
**Valeur** : Complète une feature existante (checkbox présente mais non fonctionnelle)  
Quand `memory_enabled = true`, instancier et passer un `ConversationBufferMemory` à l'agent LangChain.

---

### 6. Console de sortie en bas (style VSCode)
**Effort** : ~4-5h — nouveau composant JS/CSS  
**Valeur** : Gros gain UX — les résultats d'exécution sont actuellement dans une modale peu pratique  
Panel redimensionnable en bas du canvas affichant les logs et résultats bloc par bloc en temps réel.

---

## Niveau 3 — Refactoring / features avancées

### 7. Déplacer les blocs dans `domain/blocks/`
**Effort** : ~2h — refactoring pur (un fichier par type de bloc)  
**Valeur** : Aucune valeur utilisateur directe, mais facilite la maintenabilité et le point suivant  
Séparer `LLMBlock`, `AgentBlock`, `HTTPBlock`, `PythonScriptBlock` en fichiers distincts dans `core/domain/blocks/`.

---

### 8. Bouton "Généraliser" sur les PythonScriptBlocks
**Effort** : ~1 journée — dépend du point 7  
**Valeur** : Réutilisabilité — transformer un bloc ad hoc en bloc réutilisable  
Exporter un `PythonScriptBlock` configuré vers `core/domain/blocks/` pour le réutiliser dans d'autres workflows, avec rechargement dynamique dans la toolbox.

---

## Autres idées (non classées)

- **AgentBlock avec placeholders dynamiques** : supporter `{variable}` dans `user_prompt`, avec ports d'entrée auto-générés correspondants (comme `parse_signature` pour les Python blocks).
- Voir aussi `IDEAS.md` pour les idées post-MVP plus structurantes (ex. `HumanApprovalBlock`).
