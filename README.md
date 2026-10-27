# Чат-бот бронирования СибКодинг

Информационная система для бронирования пространства «СибКодинг» в ИКИТ СФУ студентами и сотрудниками. Telegram-бот проверяет занятость через Google Calendar, принимает заявки и предоставляет администратору функции согласования и отмены.

## Состояние и архитектура

Текущая версия — Python-бот с long polling, интеграцией Google Calendar, хранением заявок в JSON и списка администраторов в CSV. Основная логика находится в `classroom_bot/bot.py`. Вспомогательные модули выполняют проверку времени, отмену и журналирование административных действий.

Модули MAX уже присутствуют, но сценарий не завершён: просмотр занятости содержит заглушку, а продолжение бронирования не подключено к обработчику. Полный рабочий сценарий MAX требует доработки и проверки.

**Целевой вариант:** адаптеры Telegram/MAX → общее ядро Python/FastAPI → PostgreSQL и модуль Google Calendar. Эти компоненты описаны в C4 и ER как проект, а не как внедрённая архитектура. Подробнее: [текущее и целевое состояние](docs/architecture/README.md).

## Технологический стек

В текущем коде используются Python, python-telegram-bot 22.0, Google API Client, python-dotenv, pytz и maxbot 0.2.0. Полный список закреплён в [requirements.txt]. Django присутствует в зависимостях, но Django-приложение в проекте отсутствует. FastAPI и PostgreSQL относятся к целевому решению.

## Установка и запуск

Нужны Python 3.10+ и доступ к Telegram и Google Calendar API. Python 3.10+ указан с учётом Django 5.1.6 в текущем файле зависимостей. Установка и реальный запуск с внешними сервисами отдельно не проверялись.

```powershell
git clone https://github.com/koren-feyhoa/chat-bot-SibCoding.git
cd chat-bot-SibCoding/classroom_bot
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

На Linux/macOS используйте `.venv/bin/python` вместо `.venv\Scripts\python.exe`.

1. Создайте `classroom_bot/.env` вручную: готового `.env.example` в репозитории нет.
2. Укажите параметры из таблицы ниже.
3. Включите Google Calendar API для своего проекта Google и поместите собственный OAuth-файл `credentials.json` в `classroom_bot`.
4. Заполните `admin_users.csv`: Telegram ID каждого администратора в первой колонке, по одному на строку. Основная проверка `is_admin` читает этот файл.
5. Выполняйте запуск из `classroom_bot`, поскольку Google-учётные файлы читаются относительно рабочей папки.

| Переменная | Назначение |
| --- | --- |
| TELEGRAM_BOT_TOKEN | Токен Telegram-бота |
| GOOGLE_CALENDAR_ID | ID календаря бронирования |
| ADMIN_GROUP_ID | ID Telegram-группы для уведомлений администраторов |
| ADMIN_USER_ID | ID основного администратора для отдельных проверок текущей реализации; не заменяет CSV |
| MAX_BOT_TOKEN | Необязательный токен для модулей MAX |

```powershell
.venv\Scripts\python.exe bot.py
```

При первой авторизации Google откроется браузер; после выдачи доступа приложение сохранит `token.pickle`. Используйте собственные учётные данные и календарь с правом изменения событий.

Отдельная точка входа MAX — `max_bot.py`; запуск аналогичен `bot.py` и требует MAX_BOT_TOKEN. Она предназначена для разработки и проверки частично реализованного сценария. Одновременная запись двух процессов в общий JSON требует устранения риска потери данных.

## Структура проекта

```text
classroom_bot/            код ботов и зависимости
docs/
  bpmn/                  As-Is, To-Be, анализ и потоки данных
  architecture/          C4 Level 1 и Level 2
  data/                  ER, сущности и обоснование 3НФ
  requirements/          FR, NFR и Use Cases
  adr/                   архитектурные решения
  reports/               отчёт о практической работе
README.md
```

## Документация практической работы

Предлагаемый объём первого релиза и сценарий его приёмки: [границы версии 0.1.0](docs/requirements/first_release_scope.md). Документ по задаче #14 ожидает согласования команды и отделяет первый выпуск от полного целевого решения.

| Этап | Артефакты |
| --- | --- |
| 1 Анализ предметной области | [As-Is и узкие места](docs/bpmn/as_is_analysis.md), [схема As-Is](docs/bpmn/as_is.png) |
| 1 Целевой процесс | [To-Be, роли, автоматизация и потоки данных](docs/bpmn/to_be_description.md), [схема To-Be](docs/bpmn/to_be.png) |
| 1 Функциональные требования | [FR-01–FR-10](docs/requirements/functional.md), [Use Cases PNG](docs/requirements/use_cases.png), [PlantUML](docs/requirements/use_cases.puml) |
| 2 Контекст системы | [C4 Level 1 PNG](docs/architecture/context_diagram.png), [PlantUML](docs/architecture/context_diagram.puml) |
| 2 Основные компоненты | [C4 Level 2 PNG](docs/architecture/container_diagram.png), [PlantUML](docs/architecture/container_diagram.puml) |
| 2 Модель данных | [ER PNG](docs/data/er_diagram.png), [PlantUML](docs/data/er_diagram.puml), [сущности, ограничения и 3НФ](docs/data/model_description.md) |
| 3 Качество и решения | [NFR-01–NFR-13 и метрики](docs/requirements/non_functional.md), [ADR-001](docs/adr/001_architecture_style.md) |
| 4 Отчёт | [Практическая работа Word](docs/reports/architecture_report.docx) |

C4 и ER относятся к целевому состоянию. ADR пока предложен, метрики NFR являются проектными целями. Все диаграммы с описаниями, FR, NFR и ADR включены в отчёт. Процессы представлены в упрощённой дорожечной нотации; её использование вместо BPMN 2.0 требует согласования с преподавателем. Подробнее: [архитектура](docs/architecture/README.md).

## Команда и задачи

| Участник | Роль | GitHub |
| --- | --- | --- |
| Кузнецова Карина | Руководитель | [koren-feyhoa](https://github.com/koren-feyhoa) |
| Шпильберг Натан | Разработчик, архитектор | [Natan-Raf](https://github.com/Natan-Raf) |
| Зарецкая Варвара | Аналитик | [vza1rets](https://github.com/vza1rets) |
| Войцехович Елена | Тестировщик | [evoj1](https://github.com/evoj1) |

В работе над проектом используется модель ветвления GitHub Flow
##[Трекер задач](https://github.com/koren-feyhoa/chat-bot-SibCoding/issues).
