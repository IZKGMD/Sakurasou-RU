# PS Vita game asset research workflow (PCSG00129)

1. Use VitaShell on **your own installed game**. In `ux0:app/PCSG00129`, highlight the directory, press Triangle > Open decrypted, and use VitaShell FTP to transfer only `data.cpk` into `work/original/data.cpk` on your computer.
2. On Windows with Python 3.10+ installed, double-click `RESEARCH_WINDOWS.bat` to verify the archive header and save a SHA-256/size report.
3. Download or compile `CriPakTool.exe` from https://github.com/esperknight/CriPakTools and put it in `tools/bin/`. Read the source and virus-scan any binaries you obtain from third parties. Do not run unknown downloads.
4. Double-click `RESEARCH_WINDOWS.bat` again. The script will try to extract into **an empty** `work/unpacked/`, not modify the original, and write `work/reports/triage.json`. If extraction fails, leave original untouched and share only the error message.
5. Share `work/reports/archive.json` and `work/reports/triage.json` in chat. Both reports intentionally omit game dialogue and assets. Do not publish `data.cpk` or extracted files to GitHub.

The metadata scanner is NOT a decoder/rebuilder for `.ssb`. The file-format claims for `.ssb`, `.fnt`, `.cmed`, `.tipd`, `.tmd`, `.tskd` are based on a **PSP** reverse-engineering thread and must be verified on Vita. This research step only locates and fingerprints candidate files for later format analysis.

## Manual commands

```powershell
py -3 tools/scan_assets.py work/original/data.cpk --report work/reports/archive.json
py -3 tools/extract_cpk.py work/original/data.cpk --tool tools/bin/CriPakTool.exe --output work/unpacked
py -3 tools/triage_scripts.py work/unpacked --report work/reports/triage.json
```

**Source references**:
- VitaShell Open decrypted: https://consolemods.org/wiki/Vita:Applying_ROM_Patches
- CriPakTools: https://github.com/esperknight/CriPakTools
- Sakurasou PSP file formats: https://gbatemp.net/threads/sakurasou-no-pet-na-kanojo-translating-open-txg-txgtl-etc.379085/

## Если написано Not a recognisable CPK header

Это означает только то, что файл **не начинается с байтов** `43 50 4B 20` (`CPK `). Проверка количества извлечённых текстовых файлов здесь ничего не говорит: сканировали единственный внешний архив.

1. Проверьте, что игра ваша и запускается на самой PS Vita. Убедитесь, что архив взят из PS Vita PCSG00129, а не PSP.
2. Откройте VitaShell на консоли и в `ux0:app/` **выделите каталог `PCSG00129`**, затем △ → Open decrypted. **Оставайтесь в этом режиме**.
3. В VitaShell нажмите SELECT, предварительно выбрав FTP в настройках START, и перенесите `files/DATA.CPK` на ПК через FTP именно из открытого расшифрованного представления. Копирование microSD на ПК или распаковка PKG не гарантируют расшифровки PFS.
4. Сохраните прежний локальный файл под другим именем и скопируйте новую версию в `work/original/data.cpk` — не меняйте оригинал на Vita.
5. Повторно запустите `RESEARCH_WINDOWS.bat` (или `py -3 tools/diagnose_cpk.py work/original/data.cpk --report work/reports/header.json`). Если сигнатура опять не распознана, отправьте только `header.json` и способ получения файла для дальнейшего анализа.

Отсутствие сигнатуры не доказывает PFS-шифрование: возможен иной контейнер или служебный заголовок. Не удаляйте первые байты вручную.

Источник: [Vita3K — Using VitaShell to dump your own files](https://vita3k.org/quickstart); [VitaShell decrypted view](https://github.com/Cimmerian-Iter/Vita-troubleshooting-guide/blob/master/vitashell.md).
