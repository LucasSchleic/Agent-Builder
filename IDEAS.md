# IDEAS — Agent Builder

Fonctionnalités post-MVP à explorer. Ne pas développer sans validation.

---

## Human-in-the-loop (approbation utilisateur mid-workflow)

**Idée** : ajouter un bloc `HumanApprovalBlock` qui pause l'exécution, affiche
une proposition à l'utilisateur, et reprend selon sa décision (Approuver / Rejeter).

**Cas d'usage typique** : workflow `email_triage` → l'agent génère une réponse →
l'utilisateur valide → le workflow envoie le mail.

**Ce qu'il faut** :
- Nouveau type de bloc `HumanApprovalBlock` avec port `proposal_input` et ports
  `approved_output` / `rejected_output`
- Exécution asynchrone du workflow (pause / reprise avec état persistant)
- Nouveau composant UI : dialog de confirmation mid-run avec aperçu du contenu
- Gestion des timeouts (que se passe-t-il si l'utilisateur ne répond pas ?)

**Workaround actuel** : deux workflows séparés (`email_draft` génère les brouillons
dans `email_drafts/`, l'utilisateur édite le fichier, `email_send` envoie les
approuvés). Fonctionnel mais manuel.

---
