# Проверка полного DATA.CPK и вторая сцена MAIN 1Y (2 ноября 2026)

Основание: локальный пользовательский архив \`Sakurasou_Text_Audit.zip\` с \`complete_inventory.csv\`, \`complete_audit.json\` и приватными CSV японских строк. Оригинальные игровое содержимое, распакованный SSB и японские тексты в репозиторий НЕ загружаются.

## Результаты полной инвентаризации DATA.CPK

- Всего: **1681 файл**.
- **442** SSB-файла; первоначально извлечены кандидатные диалоги из **414**, ещё **28** системных/необычных сценариев пропущены из-за отсутствия стандартного \`START : SCN_\` (включая \`SCR_*\`, \`script_system_*\`). В \`localization_audit.py\` добавлена безопасная повторная попытка с \`scope=all\`; для этих файлов данные остаются непроверенными и **не подходят для прямого репакинга** без исследования структуры.
- 22 822 извлечённых кандидатов на сюжетные реплики — эвристическая оценка, не 22 822 уникальных переводимых строки.
- **1210** графических файлов: \`.csu\` 785, \`.cbg\` 209, \`.gxt\` 153, \`.loc\` 52, \`.gxttl\` 11. Последние 11 ранее ошибочно считались неизвестным форматом; классификация исправлена.
- 4 таблицы UTF-8 с 4 889 потенциальными текстовыми фрагментами: \`comment_list\` 2 170, \`task_list\` 2 105, \`tips_list\` 477, \`team_list\` 137. Эти UTF-8-смещения НЕ проверены для обратной записи.
- Не учтены \`STRM.CPK\`, \`eboot.bin\` и \`sce_sys\`: для заявления о 100% нужно отдельно их проверить.

### Графика для первого анализа

Рекомендуемые небольшие/средние игровые ресурсы для исследования формата на подлинных байтах (с оригинальной распаковки): \`common_help_parts.gxt\`, \`title_start.gxt\`, \`title_logo.gxt\`, \`menu_button.gxt\`, \`option_bg_text.gxt\`, \`title_obj.gxttl\`. Проверить формат, PNG-декодирование, текст, затем обратную сборку **без обращения к закрытым SDK**.

Универсальные источники: PS Vita GXT format https://www.psdevwiki.com/vita/index.php?title=GXT ; https://github.com/xdanieldzd/Scarlet ; https://github.com/xdanieldzd/GXTConvert . Поддержка конкретного проприетарного \`.gxttl\` и обратная упаковка пока **НЕ подтверждены**.

## Второй ручной перевод

Файл \`SCN_MAIN_1Y_1112__020.ssb\` содержит **82** извлечённые реплики о конкурсе, Отохе Накано и Масиро. Переведены все 82 строки; создан исключительно русский текстовый манифест \`translations/MAIN_1Y_1112__020.ru.json\`.

В отличие от предыдущего \`010\`, сам оригинальный бинарный \`020.ssb\` ещё не загружен в переписку. Поэтому этот новый файл **не был ни собран, ни проверен в Vita3K**. Для теста используй его локальный оригинал и \`tools/build_ru_from_audit.py\`: он сравнит каждую японскую строку в приватном исходном CSV с реальными байтами SSB и требует уникальную opcode-3-ссылку.

### Подготовить на Windows две сцены в одном CPK

\`\`\`powershell
cd "$env:USERPROFILE\Downloads\sakurasou\Sakurasou-RU-main"

New-Item -ItemType Directory -Force ".\translations" | Out-Null
$base = "https://raw.githubusercontent.com/IZKGMD/Sakurasou-RU/main"
Invoke-WebRequest "$base/tools/build_ru_from_audit.py" -OutFile ".\tools\build_ru_from_audit.py"
Invoke-WebRequest "$base/tools/build_multi_cpk.py" -OutFile ".\tools\build_multi_cpk.py"
Invoke-WebRequest "$base/translations/MAIN_1Y_1112__020.ru.json" -OutFile ".\translations\MAIN_1Y_1112__020.ru.json"

$cpk = "$env:USERPROFILE\Downloads\sakurasou\Sakurasou-Decrypted\PCSG00129\files\DATA.CPK"
if (!(Test-Path $cpk)) { throw "Original decrypted DATA.CPK not found: $cpk" }

if (!(Test-Path ".\work\patches\SCN_MAIN_1Y_1112__010_FULL_RU.ssb")) {
    throw "First translated SSB not found; rebuild MAIN 1Y 010 first"
}
if (!(Test-Path ".\work\all-assets-scan\SCN_MAIN_1Y_1112__020.ssb")) {
    throw "Original local SCN_MAIN_1Y_1112__020.ssb missing"
}
if (!(Test-Path ".\work\translations\all-ssb-candidates\DATA\SCN_MAIN_1Y_1112__020.csv")) {
    throw "Original private CSV missing; rerun localization_audit.py with --export-ssb"
}

py -3 .\tools\build_ru_from_audit.py --original-cpk "$cpk" --build-combined
if ($LASTEXITCODE -ne 0) { throw "Failed to build combined CPK" }
\`\`\`

После успешного выполнения: \`work/patches/DATA_MAIN_1Y_010_020_RU.CPK\`. Он будет содержать **обе** переведённые сцены. Закрой Vita3K, сохрани резервную копию установленного \`DATA.CPK\` и замени его комбинированным CPK. Исходный расшифрованный архив хранить неизменным.

В случае отказа сборщика по указателям/оригинальному тексту/шрифтам пришли вывод: не обходи его проверки. Это именно проверенная подготовка к локальному тесту, а не подтверждение безупречной русификации всей игры.

## Дополнить 28 пропущенных системных файлов

После получения обновлённого \`localization_audit.py\` перезапусти его с **новыми** именами отчётов и новой папкой экспорта, чтобы не перезаписывать пользовательские исходные CSV:

\`\`\`powershell
Invoke-WebRequest "$base/tools/localization_audit.py" -OutFile ".\tools\localization_audit.py"
py -3 .\tools\localization_audit.py --assets ".\work\all-assets-scan" --report ".\work\reports\audit_v2.json" --csv ".\work\reports\inventory_v2.csv" --export-ssb ".\work\translations\audit_v2_ssb"
\`\`\`

Новые низкоуверенные CSV из файлов \`SCR_*\` и \`script_*\` нельзя автоматически репаковать при помощи обычного \`ssb_patch_relocate.py\`.
