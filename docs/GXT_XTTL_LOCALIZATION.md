# Sakurasou-RU: настоящие Vita-текстуры GXT и XTTL

## Что уже подтверждено на оригинальных игровых файлах

В присланном пользователем \`Sakurasou_Textures_Test.zip\` находятся четыре ресурса:

| Файл | Формат | Разрешение | Исходный размер | Результат |
| --- | --- | --- | ---: | --- |
| \`title_start.gxt\` | GXT swizzled BGRA8888 \`0x0C001000\` | 512×64 | 131 136 Б | PNG и точная обратная сборка |
| \`common_help_parts.gxt\` | тот же | 256×128 | 131 136 Б | PNG и точная обратная сборка |
| \`option_bg_text.gxt\` | тот же | 512×256 | 524 352 Б | PNG и точная обратная сборка |
| \`title_trial.gxttl\` | XTTL, 15×9 блоков GXT 64×64 | 960×544 | 2 220 528 Б | PNG и точная обратная сборка |

Все **четыре** исходных файла без изменения PNG после декодирования и повторной упаковки совпадают с оригиналом **байт-в-байт**. Изменение отдельных пикселей в PNG проверено отдельно: обратная сборка сохраняет исходные размеры/формат, а обратное декодирование воспроизводит отредактированные пиксели. Пиксели за видимой высотой XTTL (последняя плиточная строка) и все исходные заголовки сохраняются.

Так мы подтвердили, что японские надписи в GXT и XTTL можно редактировать без замены всего UI. **Это не означает, что были переведены сами текстуры или что уже проверено их обновление в игре.** Для оригинальных картинок остаётся локальное графическое редактирование.

Реальные изображения:
- \`title_start.gxt\`: кнопка начала игры с японской надписью.
- \`common_help_parts.gxt\`: небольшие значки/плашки с японскими надписями.
- \`option_bg_text.gxt\`: подписи параметров, ориентированы вертикально внутри текстуры.
- \`title_trial.gxttl\`: большой титульный экран с логотипом и японскими элементами; исходное направление рисунка нужно сохранять при импортировании.

Документация формата GXT (типы, палитры и варианты сжатия):
- https://www.psdevwiki.com/vita/index.php?title=GXT
- https://docs.vitasdk.org/group__SceGxtUser.html

**Текущий собственный конвертер:** \`tools/gxt_png.py\`. Пока сознательно поддерживает **только** проверенный swizzled BGRA8888 \`0x0C001000\` без mipmap-цепочек. Все остальные форматы отклоняются, а не молча повреждаются.

## Запуск на Windows

В проекте:

\`\`\`powershell
cd "$env:USERPROFILE\Downloads\sakurasou\Sakurasou-RU-main"
$base = "https://raw.githubusercontent.com/IZKGMD/Sakurasou-RU/main/tools"
Invoke-WebRequest "$base/gxt_png.py" -OutFile ".\tools\gxt_png.py"
Invoke-WebRequest "$base/gxt_batch.py" -OutFile ".\tools\gxt_batch.py"

py -3 -m pip install pillow
\`\`\`

### Проверить сам формат и байт-в-байт обратную сборку

\`\`\`powershell
py -3 .\tools\gxt_png.py inspect ".\work\all-assets-scan\title_start.gxt"
py -3 .\tools\gxt_png.py roundtrip ".\work\all-assets-scan\title_start.gxt"
py -3 .\tools\gxt_png.py roundtrip ".\work\all-assets-scan\title_trial.gxttl"
\`\`\`

### Выгрузить PNG

\`\`\`powershell
py -3 .\tools\gxt_png.py export ".\work\all-assets-scan\title_start.gxt" --out ".\work\textures\title_start.png"
py -3 .\tools\gxt_png.py export ".\work\all-assets-scan\title_trial.gxttl" --out ".\work\textures\title_trial.png"
\`\`\`

**Редактор изображений:** необходимо сохранить точные размеры исходного PNG, канал прозрачности RGBA, исходные границы элементов и визуальный стиль. Если японский текст вертикальный/повёрнутый, русский следует размещать в той ориентации, которую ожидает игровой интерфейс.

### Вернуть отредактированный PNG в GXT/GXTTL

\`\`\`powershell
py -3 .\tools\gxt_png.py import ".\work\all-assets-scan\title_start.gxt" --png ".\work\textures\title_start_ru.png" --out ".\work\patches\title_start.gxt"
py -3 .\tools\gxt_png.py import ".\work\all-assets-scan\title_trial.gxttl" --png ".\work\textures\title_trial_ru.png" --out ".\work\patches\title_trial.gxttl"
\`\`\`

Конвертер сверит пиксели и не перезапишет оригинал. При необходимости поместить изменения сразу в один DATA.CPK можно использовать \`tools/build_multi_cpk.py\`, указывая \`entry\` (имя ресурса внутри CPK) и \`file\` (локально восстановленный GXT/GXTTL).

### Массовая проверка всех GXT/GXTTL

\`\`\`powershell
py -3 .\tools\gxt_batch.py --assets ".\work\all-assets-scan" --export ".\work\texture-pngs"
\`\`\`

Отчёты:
- \`work/reports/gxt_audit.csv\` — все \`.gxt\` и \`.gxttl\`, разрешение, формат, какие можно декодировать и что не поддерживается.
- \`work/reports/gxt_audit.json\` — количество поддерживаемых/неподдерживаемых;
- \`work/texture-pngs/\` — декодированные PNG для графической редакции.

В анализе пользователя обнаружено 153 файла GXT и 11 GXTTL, но **сколько именно из них подойдут для ограниченного декодера пока неизвестно**. Сначала запустить сканер. Отдельные форматы \`.csu\` (785), \`.cbg\` (209), \`.loc\` (52) не поддерживаются этим инструментом и нуждаются в следующем исследовании.

## Точность и безопасность

Код проверен на четырёх оригинальных тестовых файлах пользователя и в CI на синтетических бинарных файлах. Необработанные оригинальные ресурсы игры НЕ попадают в публичный GitHub: там только код, тестовые генераторы и инструкции. Отчёт об обнаруженных неподдерживаемых форматах можно передать в чат для доработки конвертера. Полная русификация пока не завершена.
