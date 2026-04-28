#!/usr/bin/env bash
# ==============================================================================
# Agent Builder — Bootstrap
# Initialise le projet Django et crée la structure de dossiers.
# À exécuter une seule fois après clonage.
# ==============================================================================

set -e

echo "=== Agent Builder — Bootstrap ==="

# 1. Vérifier que l'environnement virtuel est actif
if [ -z "$VIRTUAL_ENV" ]; then
  echo "⚠️  Active ton environnement virtuel d'abord : source venv/bin/activate"
  exit 1
fi

# 2. Installer les dépendances
echo "→ Installation des dépendances..."
pip install -r requirements.txt

# 3. Initialiser le projet Django
echo "→ Création du projet Django..."
django-admin startproject agent_builder .
django-admin startapp core

# 4. Créer la structure des dossiers métier dans core/
echo "→ Création de la structure core/..."
mkdir -p core/domain core/factory core/services core/api
touch core/domain/__init__.py
touch core/domain/workflow.py
touch core/domain/block.py
touch core/domain/port.py
touch core/domain/connection.py
touch core/factory/__init__.py
touch core/factory/block_creators.py
touch core/services/__init__.py
touch core/services/workflow_service.py
touch core/services/export_service.py
touch core/services/workflow_executor.py
touch core/api/__init__.py
touch core/api/views.py
touch core/api/urls.py

# 5. Créer les dossiers de données
mkdir -p workflows
mkdir -p docs/img docs/uml

echo ""
echo "✅ Bootstrap terminé."
echo "   Prochaine étape : édite .env puis lance 'python manage.py migrate'"
