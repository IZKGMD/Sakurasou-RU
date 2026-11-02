# Sakurasou-RU: ручной перевод всего SCN_MAIN_1Y_1112__010

Отдельный оригинальный SSB пользователя был переведён вручную: 71 сюжетная реплика, 36 записей имён персонажей и 4 записи неизвестного говорящего. Все 111 строк проверены на единственность opcode-3-ссылки; каждый перенос строки и маркеры ▼/▽ сохранены. Цветовая разметка «†91‡...‡» в названии общежития также сохранена.

Строки адаптированы под ограничение <=36 символов на одну исходную строку; это **эвристика**, реальные поля текста в Vita3K нужно проверить визуально. Кириллица, знаки и имена проверены по исходным двум FNT. Изменена только одна сцена MAIN 1Y; другие сценарии, меню, изображения и развилки не переведены.

## Получение (без больших загрузок)

В корне проекта в PowerShell:

\`\`\`powershell
cd "C:\Users\Bruh\Downloads\Sakurasou-RU-main"
New-Item -ItemType Directory -Force ".\translations" | Out-Null

Invoke-WebRequest "https://raw.githubusercontent.com/IZKGMD/Sakurasou-RU/main/translations/MAIN_1Y_1112__010.ru.json" -OutFile ".\translations\MAIN_1Y_1112__010.ru.json"
Invoke-WebRequest "https://raw.githubusercontent.com/IZKGMD/Sakurasou-RU/main/tools/build_ru_manifest.py" -OutFile ".\tools\build_ru_manifest.py"

$original = "C:\Users\Bruh\Downloads\Sakurasou-Decrypted\PCSG00129\files\DATA.CPK"
py -3 .\tools\build_ru_manifest.py --build-cpk --cpk "$original"
\`\`\`

Используются уже существующие в репозитории инструменты:
- \`tools/ssb_extract.py\`
- \`tools/ssb_patch_relocate.py\`
- \`tools/fnt_inspect.py\`
- \`tools/build_test_cpk.py\`
- \`tools/bin/CriPakTools.exe\`

И локальные оригинальные (не патченные) файлы:
- \`work/all-assets-scan/SCN_MAIN_1Y_1112__010.ssb\` (SHA256 \`9e9476c2a2184b34c969b434da6cd72ba136ddc1d50c5ab66d8cd8028802d94d\`);
- \`work/samples/font_m.fnt\` и \`work/samples/font_s.fnt\`;
- оригинальный расшифрованный \`DATA.CPK\`.

Получится \`work/patches/DATA_MAIN_1Y_FULL_RU.CPK\`. Скрипт проверит совпадение всех файлов в CPK и извлечёт обратно изменённый SSB для сравнения; **это не является проверкой отображения всех реплик в игровом движке**.

Для установки **полностью закрыть Vita3K**, сделать резервную копию установленного \`PCSG00129/files/DATA.CPK\`, затем заменить его готовым CPK и проверить SHA256. Не перезаписывать расшифрованный оригинал в папке \`Sakurasou-Decrypted\`.

## Что дополнительно создаётся

- \`work/patches/SCN_MAIN_1Y_1112__010_FULL_RU.ssb\` — готовый русский сценарий;
- \`work/translations/SCN_MAIN_1Y_1112__010_FULL_RU.csv\` — таблица оригинал/перевод для последующей вычитки (**не заливать на публичный GitHub**);
- \`work/patches/SCN_MAIN_1Y_1112__010_FULL_RU.report.json\` — проверка указателей и хешей;
- \`work/patches/DATA_MAIN_1Y_FULL_RU.CPK\` — установленная сборка для Vita3K.

Текущая локализация полностью покрывает все распознанные сюжетные строки этого **одного** файла; любой следующий SSB потребует своего перевода и дополнения инструмента для многофайловой сборки.
