# Эксперимент: перевод SSB без ограничения длины исходной строки

## Что удалось подтвердить на PCSG00129

На пользовательском `SCN_CJIN_1Y_1112x_010.ssb` (190804 байта,
SHA256 `bfddd7fb3f322a289a9f9df70b0699184e4b6c4ed7d72a4fca1da7d27d247add`)
выполнено адресное исследование скриптовых указателей.

Для всех **87** реплик, ранее извлечённых в CSV, обнаружена ровно одна команда
с парой 32-битных little-endian слов `0x00000003` и `offset/4`.
Для исходной строки со смещением `0x2C418` указатель лежит по
`0x20B48` и хранит `0xB106`.

Экспериментально был создан тестовый SSB с новой длинной строкой
`У меня проблемы с едой.▼`:
- исходная длина UTF-8 — 24 байта, новая — 44 байта;
- оригинальный файл — 190804 байта, экспериментальный — 190852 байта;
- новая строка добавлена по смещению `0x2E954`;
- в старой части изменены **только 4 байта** указателя по `0x20B48`;
- проверка восстановлением старого указателя даёт полное побайтовое
  совпадение со старым файлом;
- итоговый SHA256 экспериментального SSB:
  `62ea776adf6cc8d89c5e845c01be856915a6ee5c0ded14e63d2f767c74081a51`.

Это **офлайновая** структурная проверка. Оригинальный движок Vita3K ещё
не проверен с **увеличенным** SSB. Поддержка новых адресов и чтение
строк за прежним концом файла должны проверяться в игре.

## Использование в Windows PowerShell

Рабочая директория — корень `Sakurasou-RU-main`. Нужны уже полученные
локальные `work/samples/SCN_CJIN_1Y_1112x_010.ssb`,
`work/translations/CJIN_010.csv`,
`work/samples/font_m.fnt`, `work/samples/font_s.fnt`
и `tools/bin/CriPakTools.exe`.

**1. Обновить инструменты без игровых ресурсов**

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/IZKGMD/Sakurasou-RU/main/tools/ssb_patch_relocate.py" -OutFile ".\tools\ssb_patch_relocate.py"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/IZKGMD/Sakurasou-RU/main/tools/fnt_inspect.py" -OutFile ".\tools\fnt_inspect.py"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/IZKGMD/Sakurasou-RU/main/tools/build_test_cpk.py" -OutFile ".\tools\build_test_cpk.py"
```

**2. Подготовить отдельный CSV с длинной тестовой репликой**

```powershell
$rows = @(Import-Csv ".\work\translations\CJIN_010.csv")
$row = $rows | Where-Object { [Convert]::ToInt32($_.offset_hex.Substring(2), 16) -eq 0x2C418 } | Select-Object -First 1
if (-not $row) { throw "Искомая реплика не найдена" }
$row.translation_ru = "У меня проблемы с едой.▼"
$rows | Export-Csv ".\work\translations\CJIN_010_long.csv" -NoTypeInformation -Encoding UTF8
```

**3. Сначала dry-run, затем сохранить модифицированную копию SSB**

```powershell
$originalHash = "bfddd7fb3f322a289a9f9df70b0699184e4b6c4ed7d72a4fca1da7d27d247add"
$arguments = @(
  "--ssb", ".\work\samples\SCN_CJIN_1Y_1112x_010.ssb",
  "--csv", ".\work\translations\CJIN_010_long.csv",
  "--font", ".\work\samples\font_m.fnt",
  "--font", ".\work\samples\font_s.fnt",
  "--expected-sha", $originalHash,
  "--out", ".\work\patches\SCN_CJIN_relocated.ssb",
  "--report", ".\work\reports\ssb_relocate.json"
)
py -3 .\tools\ssb_patch_relocate.py @arguments
py -3 .\tools\ssb_patch_relocate.py @arguments --apply
```

Не перезаписывайте тестовый SSB или отчёт, если они уже существуют:
инструмент специально откажется это делать.

**4. Создать проверенный отдельный тестовый CPK**

```powershell
$cpk = "C:\Users\Bruh\Downloads\Sakurasou-Decrypted\PCSG00129\files\DATA.CPK"
$ssb = ".\work\patches\SCN_CJIN_relocated.ssb"
$ssbSha = (Get-FileHash $ssb -Algorithm SHA256).Hash
py -3 .\tools\build_test_cpk.py --cpk "$cpk" --ssb "$ssb" --expected-ssb-sha "$ssbSha" --control-ssb ".\work\samples\SCN_CMSK_1Y_1112x_010.ssb" --out ".\work\patches\DATA_long_test.CPK" --build
```

После успешной сборки `DATA_long_test.report.json` подтвердит
сохранность архива, списка ресурсов и нового SSB после обратного
извлечения. Это **ещё не** тест совместимости с движком.

**5. Только для отдельного теста в Vita3K**

Сначала полностью закройте эмулятор. Убедитесь, что оригинальный
расшифрованный CPK сохранён вне папки Vita3K. Установленная ранее игра
может уже содержать старый `DATA_test.CPK`; новая версия должна заменить
именно его **в папке Vita3K**, не в исходном каталоге расшифрованной игры.

```powershell
$destination = Join-Path $env:APPDATA "Vita3K\Vita3K\ux0\app\PCSG00129\files\DATA.CPK"
$replacement = ".\work\patches\DATA_long_test.CPK"
if (!(Test-Path $destination) -or !(Test-Path $replacement)) { throw "Файл не найден" }
Copy-Item $replacement $destination -Force -ErrorAction Stop
if ((Get-FileHash $destination).Hash -ne (Get-FileHash $replacement).Hash) { throw "Ошибка проверки копии" }
Write-Host "Длинный тестовый CPK установлен в Vita3K"
```

Тестируйте только копию игры. Если игра перестанет загружаться,
восстановите предыдущий рабочий CPK.

## Ограничения

- Патчер меняет только один подтверждённый тип операнда (opcode 3).
  Для другого SSB обязательно нужно доказать формат ссылок, а не
  предполагать его идентичность.
- Ограничения строки по **ширине диалогового окна**, игровые функции
  разбивки строк, отображение Unicode и возможный лимит буфера
  остаются неизвестны.
- Патчер требует сохранения `▼` / `▽` и отвергает отсутствующие глифы,
  если переданы шрифты.
- Не публикуйте .ssb, .cpk, .fnt или заполненный оригинальными
  строками CSV в GitHub. Репозиторий хранит только код и документацию.
