# Исследование PS Vita PCSG00129 полностью на ПК (Windows)

**Для работы НЕ нужно устанавливать игру на PS Vita.** Если у вас уже есть папка:
```text
Sakura-Sou no Pet na Kanojo (JPN)/
  app/PCSG00129/
    eboot.bin
    files/DATA.CPK
    files/STRM.CPK
    sce_sys/package/work.bin  # если эта лицензия присутствует у вашей копии
```
работайте с её копией на Windows. Не отправляйте игровые данные или лицензию в публичный репозиторий.

## Шаг 1. Проверка заголовка файла

1. Скопируйте DATA.CPK в work/original/data.cpk.
2. Выполните:

```powershell
py -3 tools/scan_assets.py work/original/data.cpk --report work/reports/archive.json
py -3 tools/diagnose_cpk.py work/original/data.cpk --report work/reports/header.json
```

Нормальная CRI CPK-сигнатура начинается с `43 50 4B 20` (`CPK `). Если `cpk_magic: false` или `status: unknown_header_possibly_encrypted`, **не пытайтесь распаковать его через CriPakTools**: никакие диалоги пока не извлечены.

## Шаг 2. Если PFS ещё зашифрован

Обычная распаковка PKG/NoNpDrm не обязательно расшифровывает слой PFS. При наличии необходимых данных и лицензии от вашей законно полученной копии игры можно обработать папку приложения **целиком на ПК**:

- [PSVita NPDRM Decryptor](https://github.com/SuleMareVientu/PSVitaNPDRMDecryptor) — Windows GUI; выберите исходный каталог приложения `app/PCSG00129`, назначьте отдельную выходную папку и запустите обработку. Утилита принимает папку игры, не отдельный CPK. Если исходные файлы неполные или лицензионных данных недостаточно, обработка может не сработать.
- [psvpfstools](https://github.com/motoharu-gosuto/psvpfstools) — исходники самостоятельного PFS-дешифратора для ПК; сложнее в сборке.

Не ищите чужие лицензии и не меняйте оригинальную папку. Получив результат, проверьте новый `files/DATA.CPK` через `diagnose_cpk.py`.

**Если формат так и не распознан**, передайте только `work/reports/header.json`. Отсутствие сигнатуры само по себе **не доказывает** PFS-шифрование: архив может иметь нестандартную оболочку, формат или быть повреждён.

## Шаг 3. Извлечение и анализ

Когда заголовок действительно начинается с `CPK `, установите отдельно [CriPakTools](https://github.com/esperknight/CriPakTools). Положите доверенный `CriPakTool.exe` в `tools/bin/` и запустите `RESEARCH_WINDOWS.bat`. Скрипт попытается извлечь файлы только в пустую папку `work/unpacked/` и создать `work/reports/triage.json`.

```powershell
py -3 tools/extract_cpk.py work/original/data.cpk --tool tools/bin/CriPakTool.exe --output work/unpacked
py -3 tools/triage_scripts.py work/unpacked --report work/reports/triage.json
```

Диагностический инструмент не умеет декодировать `.ssb` и не утверждает, что форматы PSP непременно совпадают с Vita.

## Шаг 4. Тестирование

Первые проверки текста и упаковки можно делать на ПК; для тестов в реальной PS Vita-игре позже понадобится совместимая среда запуска или консоль.

Источники:
- https://vita3k.org/quickstart
- https://github.com/SuleMareVientu/PSVitaNPDRMDecryptor
- https://github.com/motoharu-gosuto/psvpfstools
