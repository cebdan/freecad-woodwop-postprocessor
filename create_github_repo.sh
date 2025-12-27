#!/bin/bash

# Скрипт для создания репозитория на GitHub

set -e

REPO_NAME="freecad-woodwop-postprocessor"
REPO_DESCRIPTION="WoodWOP MPR 4.0 Post Processor for FreeCAD Path Workbench"

cd "$(dirname "$0")"

echo "🚀 Создание репозитория на GitHub..."

# Проверка авторизации
if ! gh auth status &>/dev/null; then
    echo "⚠️  Требуется авторизация в GitHub CLI"
    echo "Выполните: gh auth login"
    echo ""
    echo "Или создайте репозиторий вручную:"
    echo "1. Перейдите на https://github.com/new"
    echo "2. Создайте репозиторий с именем: $REPO_NAME"
    echo "3. Затем выполните:"
    echo "   git remote add origin https://github.com/YOUR_USERNAME/$REPO_NAME.git"
    echo "   git push -u origin main"
    exit 1
fi

# Создание репозитория
echo "📦 Создание репозитория '$REPO_NAME'..."
gh repo create "$REPO_NAME" \
    --public \
    --source=. \
    --remote=origin \
    --description "$REPO_DESCRIPTION" \
    --push

echo ""
echo "✅ Репозиторий успешно создан и код отправлен!"
echo "🌐 URL: https://github.com/$(gh api user --jq .login)/$REPO_NAME"

