# Репозиторий проекта

Основной репозиторий: https://github.com/IZKGMD/Sakurasou-RU
Рабочая ветка: main.

## Клонирование и тесты

    git clone https://github.com/IZKGMD/Sakurasou-RU.git
    cd Sakurasou-RU
    py -3 -m unittest discover -s tests -v
    py -3 tools/check_translations.py translations/strings.csv

Файлы игры, CPK, дампы и сценарии держите только в локальном work/. Эта директория игнорируется Git.

Перед отправкой pull request проверьте тесты и git status. Не коммитьте игровые ресурсы, чужие патчи или ключи доступа.

Статус: исследовательский инструментарий. Рабочего русификатора пока нет.
