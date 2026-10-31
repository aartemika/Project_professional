# Экономико-кадровый навигатор — Flask

Структура сверена с учебным примером Flask_web_7_Скачан_Bootstrap_и_env.zip из папки Яндекса.

```text
main.py                           настройка и запуск Flask
backend/
  api/                            блупринты страниц, авторизации, CRUD и HTTP API
  database/
    db_session.py                 подключение SQLAlchemy
    default_data.py               первоначальный администратор
    models/                       отдельный файл для каждой таблицы
  forms/data_form.py              поля форм и проверка введённых значений
  errors.py                       обработчики ошибок
  services.py                     импорт и расчёт показателей
  dataset.py                      подготовка CSV
  charts.py                       графики matplotlib
templates/                        base.html и дочерние шаблоны
static/css/                       отдельные стили сайта
static/vendor/                    локальные Bootstrap и jQuery
data/                             navigator.db и CSV для импорта
tests/                            проверки HTTP, CRUD и расчётов
docs/                             пояснительная записка и схемы
.env                              локальные настройки сервера
.env.sample                       образец настроек
```

## Запуск

При первой установке запустите setup.bat, затем run.bat. Из терминала: `.venv\Scripts\python.exe main.py`. Сайт доступен по http://127.0.0.1:5000. Логин администратора — admin, пароль находится в .env, поле ADMIN_PASSWORD. Существующая база уже содержит 99 653 вакансии; пароль существующего пользователя меняется через админку.

SQLite расположена в data/navigator.db. Все справочные таблицы находятся в этой базе. CSV для импорта лежат рядом в data. Bootstrap и jQuery подключаются из static/vendor, CDN не используются. Все страницы наследуют templates/base.html.

Для новой установки создайте .env по .env.sample и задайте свои SECRET_KEY и ADMIN_PASSWORD. При пустой базе администратор создаётся автоматически; CSV импортируется через админку.

## Возможности

Авторизация, роли аналитика и администратора, фильтры, сравнение городов, кластеризация, графики matplotlib, PDF, список вакансий, справка и контакты.

В админке «Управление всеми данными» предоставляет CRUD пользователей, городов, областей, форматов, вакансий и журнала импорта. Проверяются права, типы, уникальность и внешние ключи. Нельзя удалить занятый справочник или свою текущую учётную запись. Импорт заменяет вакансии и справочники одной транзакцией; при ошибке сохраняется прежний набор.

## HTTP API

POST /api/login — JSON username и password, ответ token и expires_in. GET /api/references и /api/summary требуют Authorization: Bearer <token>. Токен действует один час.

CRUD администратора: GET/POST /api/admin/<entity>; GET/PUT/DELETE /api/admin/<entity>/<id>. entity: users, cities, categories, formats, vacancies, imports. GET списка поддерживает page и q. Эти маршруты использует оконное приложение из отдельной папки Project_SemHaj_Desktop.

## Проверки и лицензия

Установите requirements-dev.txt и выполните `python -m pytest -q` из этой папки. Названия web_app в общей записке соответствуют текущей папке Project_SemHaj_Web; актуальная структура приведена выше.

Код — MIT, см. LICENSE. Исходные CSV сохранены; лицензия программного кода не определяет права на датасет.
