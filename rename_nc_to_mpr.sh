#!/bin/bash
# Автоматическое переименование .nc файлов в .mpr для WoodWOP
# Использование: ./rename_nc_to_mpr.sh /path/to/file.nc

if [ $# -eq 0 ]; then
    echo "Использование: $0 <file.nc>"
    echo "Или просто перетащите .nc файл на этот скрипт"
    exit 1
fi

NC_FILE="$1"

# Проверяем что файл существует
if [ ! -f "$NC_FILE" ]; then
    echo "Ошибка: Файл не найден: $NC_FILE"
    exit 1
fi

# Проверяем расширение
if [[ "$NC_FILE" != *.nc ]]; then
    echo "Ошибка: Файл должен иметь расширение .nc"
    exit 1
fi

# Создаём имя .mpr файла
MPR_FILE="${NC_FILE%.nc}.mpr"

# Переименовываем
mv "$NC_FILE" "$MPR_FILE"

if [ $? -eq 0 ]; then
    echo "✓ Файл переименован: $MPR_FILE"
    echo "Теперь его можно открыть в WoodWOP"
else
    echo "✗ Ошибка при переименовании файла"
    exit 1
fi
