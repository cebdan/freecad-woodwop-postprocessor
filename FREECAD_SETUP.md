# Инструкция по клонированию FreeCAD и добавлению поддержки G41/G42

## Клонирование исходного кода FreeCAD

### 1. Клонирование репозитория

```bash
cd ~/Documents
git clone https://github.com/FreeCAD/FreeCAD.git
cd FreeCAD
```

### 2. Структура проекта FreeCAD

Основные директории для работы с Path (G-code):

- `src/Mod/Path/` - Модуль Path (обработка траекторий)
- `src/Mod/Path/PathScripts/` - Скрипты Path
- `src/Mod/Path/PathScripts/post/` - Post-processors (пост-процессоры)
- `src/Mod/Path/Path/` - Основные классы Path

### 3. Где обрабатываются G-коды

**Post-processors:**
- `src/Mod/Path/PathScripts/post/` - Здесь находятся все post-processors
- Каждый post-processor обрабатывает команды из `Path.Commands`

**Генерация команд:**
- `src/Mod/Path/PathScripts/PathUtils.py` - Утилиты для работы с Path
- `src/Mod/Path/Path/Command.py` - Класс Command для G-code команд

## Добавление поддержки G41/G42 в WoodWOP Post Processor

### Текущее состояние

В `woodwop_post.py` уже есть:
- `G40` - Отмена компенсации радиуса инструмента (строка 1337)

### Что нужно добавить

**G41** - Компенсация радиуса инструмента слева (Left Cutter Compensation)
**G42** - Компенсация радиуса инструмента справа (Right Cutter Compensation)

### Где добавить поддержку

1. **В функции `generate_gcode()`** - добавить обработку команд G41/G42 из Path.Commands
2. **В функции обработки команд** - проверить наличие G41/G42 в командах Path

### Пример реализации

```python
# В функции generate_gcode(), при обработке команд:
for cmd in obj.Path.Commands:
    line = cmd.Name
    
    # Обработка G41/G42
    if cmd.Name in ['G41', 'G41.1', 'G42', 'G42.1']:
        # G41 - компенсация слева
        # G41.1 - динамическая компенсация слева
        # G42 - компенсация справа  
        # G42.1 - динамическая компенсация справа
        
        # Добавить параметр D (номер корректора)
        if 'D' in cmd.Parameters:
            line += f" D{int(cmd.Parameters['D'])}"
        else:
            # Использовать номер инструмента по умолчанию
            tool_number = get_tool_number(obj)
            if tool_number:
                line += f" D{tool_number}"
    
    # Добавить остальные параметры
    for param, value in sorted(cmd.Parameters.items()):
        if param != 'D' or cmd.Name not in ['G41', 'G41.1', 'G42', 'G42.1']:
            line += f" {param}{fmt(value)}"
    
    gcode_lines.append(line)
```

## Изучение исходного кода FreeCAD

### Полезные файлы для изучения

1. **Path/Command.py** - Класс Command
   ```bash
   cd ~/Documents/FreeCAD
   find . -name "Command.py" -path "*/Path/*"
   ```

2. **PathScripts/PathUtils.py** - Утилиты Path
   ```bash
   find . -name "PathUtils.py"
   ```

3. **Примеры post-processors:**
   ```bash
   ls src/Mod/Path/PathScripts/post/
   ```

### Поиск обработки G41/G42 в исходном коде

```bash
cd ~/Documents/FreeCAD
grep -r "G41\|G42" src/Mod/Path/
```

## Альтернативный подход

Вместо модификации исходного кода FreeCAD, можно:

1. **Модифицировать только post-processor** `woodwop_post.py`
2. **Добавить обработку G41/G42** в функции `generate_gcode()`
3. **Проверить, генерирует ли FreeCAD команды G41/G42** в Path.Commands

### Проверка генерации G41/G42 FreeCAD

FreeCAD может генерировать G41/G42 автоматически, если:
- В настройках операции включена компенсация радиуса инструмента
- Tool Controller имеет настройки компенсации

Проверьте в отчете Job (`*_job_report.txt`), есть ли информация о компенсации.

## Быстрый старт

1. Клонировать FreeCAD:
   ```bash
   cd ~/Documents
   git clone https://github.com/FreeCAD/FreeCAD.git
   ```

2. Изучить структуру:
   ```bash
   cd FreeCAD
   ls src/Mod/Path/PathScripts/post/
   ```

3. Найти обработку G41/G42:
   ```bash
   grep -r "G41\|G42" src/Mod/Path/
   ```

4. Модифицировать `woodwop_post.py` для поддержки G41/G42

