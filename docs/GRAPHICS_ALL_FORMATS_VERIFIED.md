# Sakurasou-RU: GXT/P8, XTTL, LOC, CSU, CBG: проверенные форматы

## Проверка десяти пользовательских бинарных образцов

В архиве Sakurasou_Graphics_Review.zip были три ранее неподдержанных GXT/GXTTL, три CSU, один CBG и три LOC.
На всех десяти исходных файлах независимо выполнены: декодирование в PNG, точный побайтовый обратный цикл, однопиксельное изменение и обратная проверка картинки.

| Файл | Размер декодированного изображения | Устройство |
| --- | --- | --- |
| action_bg.gxttl / action_bg02.gxttl | 960x544 | Плитки 128x128, сетка 8x5; правый и нижний край обрезаны |
| conversation_cloud.gxt | 256x512 | Swizzled P8, формат 0x95001000, палитра BGRA8888 из 256 цветов |
| LC_BITN.loc / LC_SIREC.loc / lc_test.loc | 512x64 | Обычный RGBA GXT внутри LOC |
| bg_test.cbg | 960x544 | CBG, вложенный XTTL 15x9 плиток 64x64 |
| SUMIDSUW_U.csu | 128x128 | CSU, вложенный XTTL 2x2 |
| SUNNMMAG_B.csu | 368x544 | CSU, вложенный XTTL 6x9, дополнительные данные |
| SUMSKWAI_UC.csu | 672x640 | CSU, вложенный XTTL 11x10, дополнительные данные |

Результат: 10/10 точных бинарных циклов, 10/10 тестов изменения пикселя. Заголовки и все данные CSU/CBG вне встроенного XTTL оставались без изменений.
Эта проверка ещё не означает, что изменённые текстуры уже протестированы в Vita3K.

Конвертер: tools/gxt_png.py. Массовая инвентаризация: tools/gxt_batch.py.
Формат P8 подтверждён документацией https://github.com/vitasdk/vita-headers/blob/master/include/psp2/gxm.h

## Команды Windows

Сначала перейти в проект, затем обновить два небольших инструмента:

    cd "$env:USERPROFILE\Downloads\sakurasou\Sakurasou-RU-main"
    $base = "https://raw.githubusercontent.com/IZKGMD/Sakurasou-RU/main/tools"
    Invoke-WebRequest "$base/gxt_png.py" -OutFile ".\tools\gxt_png.py"
    Invoke-WebRequest "$base/gxt_batch.py" -OutFile ".\tools\gxt_batch.py"
    py -3 -m pip install pillow

Просканировать графику пяти расширений (без тяжёлого массового экспорта PNG):

    py -3 .\tools\gxt_batch.py --assets .\work\all-assets-scan --all-graphics --out .\work\reports\all_graphics_v2.csv --summary .\work\reports\all_graphics_v2.json

Проверить точный обратный цикл любого исходного образца:

    py -3 .\tools\gxt_png.py roundtrip .\work\all-assets-scan\conversation_cloud.gxt
    py -3 .\tools\gxt_png.py roundtrip .\work\all-assets-scan\action_bg.gxttl
    py -3 .\tools\gxt_png.py roundtrip .\work\all-assets-scan\bg_test.cbg
    py -3 .\tools\gxt_png.py roundtrip .\work\all-assets-scan\SUNNMMAG_B.csu
    py -3 .\tools\gxt_png.py roundtrip .\work\all-assets-scan\LC_BITN.loc

Не заливайте исходные коммерческие ресурсы игры в публичный GitHub. Все изменённые файлы сначала надо проверить в Vita3K.
Совместимость на десяти образцах не гарантирует поддержку всех 1210 файлов графики.
Декодирование графики и перевод японских надписей — две разные стадии работы.
