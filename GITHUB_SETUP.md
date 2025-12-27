# Инструкция по созданию репозитория на GitHub

## Шаг 1: Создайте репозиторий на GitHub

1. Перейдите на https://github.com/new
2. Заполните форму:
   - **Repository name**: `freecad-woodwop-postprocessor` (или другое имя)
   - **Description**: `WoodWOP MPR 4.0 Post Processor for FreeCAD Path Workbench`
   - **Visibility**: Public или Private (на ваш выбор)
   - **НЕ** создавайте README, .gitignore или лицензию (они уже есть)
3. Нажмите **Create repository**

## Шаг 2: Подключите локальный репозиторий к GitHub

После создания репозитория GitHub покажет инструкции. Выполните команды:

```bash
cd "/Users/user/Documents/freecad/woodwop post"

# Добавьте remote (замените YOUR_USERNAME на ваш GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/freecad-woodwop-postprocessor.git

# Или если используете SSH:
# git remote add origin git@github.com:YOUR_USERNAME/freecad-woodwop-postprocessor.git

# Отправьте код на GitHub
git push -u origin main
```

## Шаг 3: Проверка

Откройте ваш репозиторий на GitHub и убедитесь, что все файлы загружены.

## Альтернативный способ (через GitHub CLI)

Если установлен GitHub CLI (`gh`):

```bash
cd "/Users/user/Documents/freecad/woodwop post"

# Создать репозиторий и отправить код одной командой
gh repo create freecad-woodwop-postprocessor --public --source=. --remote=origin --push
```

## Текущий статус репозитория

- ✅ Git инициализирован
- ✅ Создан .gitignore
- ✅ Создан README.md
- ✅ Создан CHANGES_REPORT.md
- ✅ Добавлены основные файлы
- ✅ Создан начальный коммит
- ⏳ Ожидается подключение к GitHub

## Файлы в репозитории

- `woodwop_post.py` - Основной постпроцессор
- `README.md` - Описание проекта
- `CHANGES_REPORT.md` - Отчет об изменениях
- `INSTALL_INSTRUCTIONS.md` - Инструкции по установке
- `USAGE_GUIDE.md` - Руководство по использованию
- `CHANGELOG.md` - История изменений
- `Tools/` - Библиотека инструментов для FreeCAD
- `.gitignore` - Игнорируемые файлы

## Игнорируемые файлы

Следующие файлы и папки НЕ будут загружены на GitHub:
- `test mpr/` - Тестовые файлы
- `*.log` - Логи
- `*.FCStd` - Файлы FreeCAD
- `__pycache__/` - Кэш Python
- `.DS_Store` - Системные файлы macOS
- `v1-2/` - Старые версии

