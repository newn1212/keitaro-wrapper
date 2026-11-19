# Keitaro wrapper

Обёртка над рекламным трекером Keitaro: **FastAPI + SQLAlchemy + Alembic**, фронт — HTML + чистый JS (без сборки).

**Что умеет**
1. **Создатель кампаний** — название + гео + оффер (поиск с автокомплитом). Создаёт в Keitaro кампанию с доменом, группой и источником из `.env` и двумя потоками:
   - `Flow 1` — фильтр «страна принимает <гео>» → редирект на `https://google.com`;
   - `Flow 2` — выбранный оффер (100%).
   Если создание потоков упало, кампания в Keitaro удаляется (не остаётся «полуготовых»).
2. **Редактор кампании** — открыть кампанию по ID (или из списка недавних), добавить/удалить офферы в потоке. Доли (%) пересчитываются поровну, сумма всегда 100 (3 оффера → 34/33/33). Доли можно поправить вручную — кнопка «Сохранить» активна, только когда сумма равна 100.

Локальная БД (SQLite) хранит созданные кампании и журнал изменений офферов.

## Запуск

Нужен Python 3.11+.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # Windows: copy .env.example .env
# открыть .env и вставить KEITARO_API_KEY (Keitaro → Профиль → API ключи)

alembic upgrade head        # миграции: создаёт app.db с таблицами
uvicorn app.main:app --reload
```

Открыть http://127.0.0.1:8000 (Swagger: http://127.0.0.1:8000/docs).

Тесты логики долей: `pytest`

## Настройки (`.env`)

| Переменная | Что это |
|---|---|
| `KEITARO_URL` | адрес Keitaro без `/admin`, например `https://tlk.host` |
| `KEITARO_API_KEY` | API-ключ из профиля Keitaro |
| `DOMAIN_NAME`, `GROUP_NAME`, `SOURCE_NAME` | домен, группа и источник для новых кампаний (ищутся по имени через API) |
| `NAME_PREFIX` | необязательно: обязательный префикс названия, например `test_ivanov_` |
| `DATABASE_URL` | по умолчанию `sqlite:///./app.db` |

## Структура

```
app/main.py      — маршруты API и отдача фронта
app/keitaro.py   — клиент Keitaro Admin API (/admin_api/v1)
app/shares.py    — расчёт и проверка долей
app/models.py    — таблицы SQLAlchemy
alembic/         — миграции
static/          — index.html, app.js, style.css
tests/           — pytest
```

## Используемые методы Keitaro API

`GET /offers`, `/domains`, `/groups`, `/traffic_sources`, `POST /campaigns`, `DELETE /campaigns/{id}`,
`GET /campaigns/{id}`, `GET /campaigns/{id}/streams`, `POST /streams`, `GET /streams/{id}`, `PUT /streams/{id}`.
Авторизация — заголовок `Api-Key`. Если Keitaro отклонит какое-то поле, текст ошибки показывается в интерфейсе.

## Что можно доработать
- Статистика кликов по офферам (`POST /report/build`).
- Авторизация самого приложения.
