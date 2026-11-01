# Sakurasou no Pet na Kanojo — русский фанатский перевод (PS Vita)

![Status](https://img.shields.io/badge/статус-исследование-orange) ![Platform](https://img.shields.io/badge/PS%20Vita-PCSG00129-blue)

**Независимый некоммерческий проект локализации** игры *Sakurasou no Pet na Kanojo* (さくら荘のペットな彼女) для PS Vita. Идентификатор версии: `PCSG00129` (Япония).

> **Статус: инструменты исследования v0.1.0.** Русский перевод НЕ готов; здесь пока НЕТ работающего патча, восстановленного игрового скрипта или проверенной поддержки кириллицы. Этот репозиторий — безопасная техническая основа для начала работы.

## Что уже установлено

По документации существующего английского проекта, изменённый архив игры загружается с помощью rePatch по пути:

```text
ux0:rePatch/PCSG00129/files/data.cpk
```

Архив `data.cpk` относится к формату CRIWARE CPK. Его структура **внутри конкретной Vita-версии ещё не исследована**. Переносимость PSP-скриптов и патчей на Vita не гарантируется.

## Быстрый старт на Windows

1. Установите Python 3.10+; эти скрипты не требуют сторонних библиотек Python.
2. Подготовьте *собственную законно полученную копию* игры на прошитой Vita. Через VitaShell найдите каталог `ux0:app/PCSG00129/` (путь/структура могут различаться), используйте `Open decrypted` и перенесите оригинальный `data.cpk` на свой ПК по FTP. Если файла нет, изучите структуру без предположений о пути.
3. Поместите полученный файл в `work/original/data.cpk`. **Не загружайте его на GitHub!**
4. Запустите:

```powershell
py -3 tools/scan_assets.py work/original/data.cpk --report work/reports/archive.json
```

Это только проверит заголовок и составит отчёт о размере/контрольной сумме: **пока не извлекает** содержимое CPK.

5. Для извлечения изучите [CriPakTools](https://github.com/esperknight/cripaktools) или [CriPakTools GUI](https://github.com/FFBE-JP-Translation/CriPakTools-GUI). Извлечённые файлы держите в `work/unpacked/`.
6. Выполните анализ списка файлов:

```powershell
py -3 tools/scan_assets.py work/unpacked --report work/reports/unpacked.json
py -3 tools/check_translations.py translations/strings.csv
```

7. Изучите `docs/ROADMAP.md` и `docs/ASSETS.md`, прежде чем менять что-либо в архивах.

## Сборка патча (когда будет изменённый CPK)

Для создания распространяемого **бинарного delta-патча**, а не готового архива игры, установите `xdelta3` (отдельный инструмент) и проверьте наличие команды `xdelta3 --version`.

```powershell
py -3 tools/build_xdelta.py --original work/original/data.cpk --modified work/modified/data.cpk --patch dist/Sakurasou-RU-PCSG00129.xdelta
```

Проверка установки на собственном архиве:

```powershell
py -3 tools/apply_xdelta.py --original work/original/data.cpk --patch dist/Sakurasou-RU-PCSG00129.xdelta --manifest dist/Sakurasou-RU-PCSG00129.manifest.json --output work/test/data.cpk
```

После проверки целостности можно перенести **полученный на своём ПК** `data.cpk` в `ux0:rePatch/PCSG00129/files/data.cpk` на SD2Vita. Всегда оставляйте оригинальные данные и сохранения нетронутыми; заранее сделайте резервные копии.

**Внимание:** xdelta-файл ещё нужно проверить на отсутствие встроенных фрагментов чужих защищённых материалов и совместимость конкретной редакции. Не публикуйте патчи, содержащие значительные защищённые игровые данные, без разрешения правообладателей.

## Структура

```text
Sakurasou-RU-starter/
├── tools/                 # автономные утилиты анализа и patch build
├── translations/          # наш глоссарий и пустой шаблон локализации
├── docs/                  # исследовательские заметки, план, инструкция
├── tests/                 # тесты на синтетических файлах
└── work/                  # локальные файлы игры (НЕ входят в Git)
```

## Вклад сообщества

Можно помогать с анализом форматов, кириллическим шрифтом, переводом **собственных** записей/кратких системных строк и тестированием. Смотрите `CONTRIBUTING.md`.

## Авторство и права

Это неофициальный фанатский проект, не связан с издателем или создателями игры. Все права на игру, сюжет, персонажей, музыку, графику и игровые тексты принадлежат их владельцам. Репозиторий **не содержит игру, ROM, VPK, `data.cpk`, оригинальные сценарии или файлы английской команды**. Права на отдельно разработанные здесь скрипты определяются `LICENSE`. Если добавляете переводы игровых текстов, учитывайте права владельцев исходного произведения.

## Источники технических сведений

- [Eternal Nyaboron — Vita guide](https://eternalnyaboronofficial.weebly.com/vita-guide.html): расположение `data.cpk` в rePatch.
- [CRI Pak Tools](https://github.com/esperknight/cripaktools): извлечение и замена файлов в CPK.
- [ConsoleMods — Applying Vita ROM Patches](https://consolemods.org/wiki/Vita%3AApplying_ROM_Patches): принцип работы rePatch.
## Новый этап: поиск сценариев PS Vita

Для Windows: распакуйте проект, скопируйте собственный data.cpk в work/original/ и запустите RESEARCH_WINDOWS.bat.

Если tools/bin/CriPakTool.exe пока отсутствует, скрипт остановится после проверки заголовка CPK. После добавления инструмента повторный запуск попробует извлечь архив в отдельную папку и сохранит work/reports/triage.json.

Подробности: [инструкция исследования](docs/RESEARCH_WORKFLOW.md).

**Это исследовательский набор, а не готовый декодер .ssb или русский патч.** Не публикуйте оригинальные файлы игры.
