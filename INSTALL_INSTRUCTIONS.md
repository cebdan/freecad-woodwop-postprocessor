# Инструкция по установке WoodWOP Post Processor для FreeCAD

## Метод 1: Установка в системную директорию (Рекомендуется)

Этот метод требует прав администратора, но постпроцессор будет доступен для всех пользователей.

### macOS:

1. Откройте Finder
2. Нажмите `Cmd+Shift+G` (Переход к папке)
3. Вставьте путь: `/Applications/FreeCAD.app/Contents/Resources/Mod/CAM/Path/Post/scripts/`
4. Нажмите "Перейти"
5. Скопируйте файл `woodwop_post.py` в эту папку
6. При запросе введите пароль администратора
7. Перезапустите FreeCAD

### Через терминал (macOS):

```bash
sudo cp "woodwop_post.py" "/Applications/FreeCAD.app/Contents/Resources/Mod/CAM/Path/Post/scripts/"
```

---

## Метод 2: Установка в пользовательскую директорию

Этот метод не требует прав администратора.

### macOS:

#### Вариант A: Через Preferences (настройки FreeCAD)

1. Запустите FreeCAD
2. Откройте **Edit → Preferences → CAM → Job Preferences**
3. Найдите опцию **User Post Processor Path** или **Search Path**
4. Нажмите на кнопку с тремя точками `...` и выберите папку, куда вы хотите поместить постпроцессор
5. Или создайте папку вручную, например: `~/Documents/FreeCAD_PostProcessors/`
6. Скопируйте `woodwop_post.py` в эту папку
7. Перезапустите FreeCAD

#### Вариант B: Через Terminal

```bash
# Создайте директорию для постпроцессоров
mkdir -p "$HOME/Documents/FreeCAD_PostProcessors"

# Скопируйте файл
cp "woodwop_post.py" "$HOME/Documents/FreeCAD_PostProcessors/"
```

Затем в FreeCAD укажите путь к этой папке в настройках (см. Вариант A).

---

## Метод 3: Через Macro директорию (Альтернативный)

**Примечание**: Этот метод может не работать во всех версиях FreeCAD.

### macOS:

```bash
# Создайте директорию
mkdir -p "$HOME/Library/Application Support/FreeCAD/Macro"

# Скопируйте файл
cp "woodwop_post.py" "$HOME/Library/Application Support/FreeCAD/Macro/"
```

---

## Проверка установки

1. Запустите FreeCAD
2. Откройте или создайте проект с Path workbench
3. Создайте Job и операции обработки
4. Выберите **Path → Post Process** (или нажмите на кнопку Post Process)
5. В выпадающем списке **Post Processor** должен появиться **woodwop_post**
6. Если постпроцессора нет в списке:
   - Перезапустите FreeCAD
   - Проверьте правильность пути к файлу
   - Убедитесь, что файл называется именно `woodwop_post.py`

---

## Настройка пути к постпроцессорам в FreeCAD

Если постпроцессор не отображается:

1. Откройте **Edit → Preferences**
2. Перейдите в **CAM → Job Preferences** (или **Path → Job Preferences** в старых версиях)
3. Найдите секцию **Post Processor**
4. В поле **Search Path** или **User Post Processor Path** укажите путь к папке с `woodwop_post.py`
5. Нажмите **OK**
6. Перезапустите FreeCAD

---

## Использование

После установки:

1. В Path workbench создайте Job и операции
2. Нажмите **Path → Post Process**
3. Выберите **woodwop_post** из списка
4. При необходимости укажите аргументы (например: `--precision=2`)
5. Нажмите **OK**
6. Выберите место сохранения .mpr файла
7. Откройте сгенерированный файл в WoodWOP

---

## Поддерживаемые операции FreeCAD

- **Profile** / **Contour** → Contourfraesen (контурное фрезерование)
- **Drilling** → BohrVert (вертикальное сверление)
- **Pocket** → Pocket (карманы)

---

## Аргументы командной строки

В поле "Arguments" можно указать:

- `--no-comments` - убрать комментарии из MPR файла
- `--precision=2` - точность координат (количество знаков после запятой)
- `--workpiece-length=800` - длина заготовки в мм
- `--workpiece-width=600` - ширина заготовки в мм
- `--workpiece-thickness=18` - толщина заготовки в мм
- `--use-part-name` - назвать MPR файл по имени детали вместо документа

Пример:
```
--precision=2 --workpiece-thickness=18 --no-comments --use-part-name
```

---

## Устранение неполадок

### Постпроцессор не появляется в списке

**Решение 1**: Проверьте имя файла
- Файл должен называться **точно** `woodwop_post.py`
- Расширение должно быть `.py`, а не `.py.txt`

**Решение 2**: Проверьте права доступа
```bash
ls -la "$HOME/Library/Application Support/FreeCAD/Macro/woodwop_post.py"
```
Файл должен иметь права на чтение (r--).

**Решение 3**: Проверьте путь в настройках FreeCAD
- Edit → Preferences → CAM → Job Preferences
- Убедитесь, что путь к постпроцессорам указан правильно

**Решение 4**: Очистите кэш FreeCAD
```bash
rm -rf "$HOME/Library/Application Support/FreeCAD/Mod/__pycache__"
```

### Ошибка при экспорте

Проверьте консоль FreeCAD (**View → Panels → Report view**) для деталей ошибки.

Типичные проблемы:
- Не создан Job
- Не назначен ToolController
- Операции пустые (без путей)

---

## Дополнительная информация

Подробную документацию смотрите в файле `README.md`.

Спецификация формата MPR: `mpr4x_format_us (1).txt`
