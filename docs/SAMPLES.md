# Первые образцы PS Vita: SSB и шрифты

Подтверждено непосредственно списком пользователя: расшифрованный CPK начинается с `CPK ` и содержит `SCN_*.ssb`, `font_m.fnt`, `font_s.fnt`, `comment_list.cmed`.

**Текстовый формат SSB ещё НЕ декодирован.** Не нужно извлекать весь архив для первой проверки.

## Проверка на Windows

В PowerShell, находясь в корне проекта, обновите файл инструмента, если репозиторий был скачан ранее:

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/IZKGMD/Sakurasou-RU/main/tools/extract_samples.py" -OutFile ".\tools\extract_samples.py"
```

Убедитесь, что доверенный CriPakTools.exe уже находится в `tools/bin/`. Затем:

```powershell
$cpk = "C:\Users\Bruh\Downloads\Sakurasou-Decrypted\PCSG00129\files\DATA.CPK"
py -3 .\tools\extract_samples.py --cpk "$cpk" --tool ".\tools\bin\CriPakTools.exe"
```

Скрипт выбирает **два .ssb, два .fnt и один .cmed**. Он ничего не пишет в исходный CPK. Выходная папка `work/samples/` должна быть пустой. Результаты:

- `work/samples/` — локальные файлы игры, не загружать в GitHub;
- `work/reports/samples.json` — технические метаданные, SHA-256 и первые 32 байта каждого образца.

При ошибке `Cannot find NAME` проверьте точное имя файла через `cpk_list.txt`. Некоторые версии могут иметь отличающиеся списки. Если нужно извлечь иной файл:

```powershell
py -3 .\tools\extract_samples.py --cpk "$cpk" --out ".\work\samples-2" --name "SCN_BCHI_1Y_1112x_010.ssb"
```

Важные ограничения:
- Скрипт **пока не извлекает или не декодирует японские диалоги**, а лишь готовит образцы и их небольшой метаотчёт.
- Не запускайте CriPakTools с командой `REPLACE_ME` и не меняйте CPK на месте.
- Не публикуйте оригинальные .ssb, .fnt, .cmed или бинарные ресурсы.
- `work/reports/samples.json` можно передать на технический анализ.

В будущем потребуется реверс-инжиниринг бинарного формата SSB: команды, смещения строк, кодировка и обратная упаковка, затем тестовый перевод одной строки.
