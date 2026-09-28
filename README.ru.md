# SaveBot

> Русская версия `README.md`. Актуальность поддерживается вручную при каждом изменении
> английской версии — если заметишь расхождение, дай знать.

Telegram-бот, который превращает ссылки (Instagram/TikTok/YouTube/Pinterest/Threads/любая
веб-страница) и скриншоты в персональную AI-библиотеку с поиском. Отправляешь боту что-то
интересное; позже описываешь это своими словами — и получаешь обратно.

Продуктовый принцип: **CAPTURE → UNDERSTAND → ORGANIZE → RETRIEVE** (сохранить → понять →
организовать → найти). Это не даунлоадер — бот почти никогда не хранит сам оригинальный
медиафайл, он хранит *понимание* содержимого плюс ссылку на источник.

## Архитектура

```
Telegram (aiogram 3)
   │  хендлеры делают только: валидацию, проверку на дубликат, создают строку
   │  `saved_items` (status=pending), ставят задачу в очередь, показывают статус-сообщение
   ▼
Redis (очередь arq)
   ▼
Worker (arq)
   │  извлечение -> AI-классификация -> embedding -> запись в БД -> редактирование
   │  статус-сообщения в Telegram в финальную карточку
   ▼
PostgreSQL + pgvector (все запросы scoped по user_id)
```

- **Bot** (`app/bot`): хендлеры/middleware/клавиатуры/i18n на aiogram 3. Хендлеры никогда не
  блокируются на сетевых/AI-вызовах — они сохраняют минимальное состояние и передают работу в
  очередь.
- **Extractors** (`app/extractors`): один `ContentExtractor` на платформу за общим интерфейсом,
  используется oEmbed там, где доступен, иначе OpenGraph/JSON-LD/HTML meta. См. «Ограничения по
  платформам» ниже — никакого обхода логина, CAPTCHA или DRM.
- **AI-абстракция** (`app/services/ai`): протоколы `LLMProvider` / `EmbeddingProvider` /
  `VisionProvider`, выбираются во время выполнения через `AI_PROVIDER` / `EMBEDDING_PROVIDER` /
  `VISION_PROVIDER`. OpenAI — полностью рабочая референсная реализация (chat + vision +
  embeddings); провайдер Anthropic покрывает chat + vision, доказывая, что абстракция не привязана
  к одному вендору (у Anthropic нет своего embeddings-эндпоинта, поэтому embeddings в этом случае
  должны идти от другого провайдера).
- **Поиск** (`app/services/search`): гибридное ранжирование — полнотекстовый поиск Postgres
  (лексический) + косинусное сходство pgvector (семантический) + мягкий буст по метаданным +
  затухание по свежести/использованию, всё объединяется взвешенной формулой
  (`app/core/config.py: SearchWeights`). Опциональный шаг с LLM превращает запрос на естественном
  языке в структурированные фильтры (`SearchFilter`); если этот вызов падает, поиск всё равно
  работает по исходному тексту запроса.
- **Безопасность** (`app/services/security`): каждый исходящий запрос (превью по ссылке, загрузка
  изображений) идёт через `safe_http.safe_get`, который блокирует не-http(s) схемы, резолвит и
  отклоняет loopback/приватные/link-local/зарезервированные IP (защита от SSRF и от cloud
  metadata-эндпоинтов), ограничивает число редиректов, ограничивает размер ответа прямо во время
  стриминга и всегда применяет таймаут.
- **Очередь** (`app/workers`, [arq](https://github.com/samuelcolvin/arq)): выбрана вместо
  Celery/Dramatiq, потому что она asyncio-native — воркер использует те же async SQLAlchemy-сессии
  и httpx-клиенты, что и бот, без моста между потоками/процессами. Встроенные ретраи; ручная
  обёртка с экспоненциальным backoff (`_backoff_or_raise`) обрабатывает инфраструктурные сбои
  (кратковременные проблемы с БД/Redis), а ошибки извлечения/AI/embedding перехватываются *внутри*
  пайплайна и никогда не роняют задачу — сохранёнка всё равно сохраняется с той частью данных, что
  успела собраться. `_job_id` при `enqueue_job` даёт идемпотентную постановку задач бесплатно.

## Структура проекта

```
app/
  api/            FastAPI: /health, /ready, /admin/* под токеном
  bot/
    handlers/     start, intake (диспетчер URL/фото/поиска), browse (пагинация),
                  item_actions (избранное/редактирование/удаление), collections, library, settings
    keyboards/    фабрики CallbackData для aiogram
    middlewares/  обработка ошибок, контекст логирования, DB-сессия, авторизация/scoping
                  пользователя, rate limit
    i18n/         таблицы строк ru/en (t(key, locale=...))
    states/       FSM-состояния для флоу редактирования/создания коллекции
    rendering.py  SavedItem -> текст карточки в Telegram + inline-клавиатура (общее для бота и воркера)
    factory.py    Создание Bot, включая прокидывание исходящего прокси (общее для бота и воркера)
  core/           конфиг (pydantic-settings), логирование (structlog), redis, arq pool
  db/
    models/       async-модели SQLAlchemy 2 (users, saved_items, collections, tags, ...)
    repositories/ все запросы scoped по user_id — единственное место, которое трогает SQL
  extractors/     ContentExtractor + реализации по платформам + registry
  schemas/        ContentMetadata / ContentAnalysis / SearchFilter (Pydantic v2)
  services/
    ai/           LLMProvider/EmbeddingProvider/VisionProvider + OpenAI/Anthropic + фабрика
    content/      нормализация URL/определение платформы, оркестрация пайплайна, searchable_text
    search/       сервис гибридного поиска, Redis-хранилище сессии пагинации
    security/     SSRF-safe HTTP-клиент, rate limiting
    storage/      хранилище скриншотов: локальный диск (по умолчанию) или S3-совместимое, за одним интерфейсом
  workers/        arq WorkerSettings + тела задач
docker/proxy/     опциональный контейнер с ssh -D SOCKS5-туннелем (см. «Исходящий прокси» ниже)
migrations/       Alembic (написанная вручную первая схема, включая pgvector и FTS-триггер)
tests/
  unit/           без БД/сети: нормализация URL, схемы, searchable_text, rate limit, SSRF
  integration/    реальный Postgres+pgvector: scoping пользователей, дедупликация, избранное,
                  каскадное удаление, поиск
```

## Запуск

```bash
cp .env.example .env
# минимум нужно заполнить TELEGRAM_BOT_TOKEN и AI_API_KEY
docker compose up -d --build
```

Сервисы: `postgres` (образ с pgvector), `redis`, одноразовая задача `migrate`
(`alembic upgrade head`), `bot`, `worker`, `api`. `bot`/`worker`/`api` ждут успешного завершения
`migrate`. Хранилище скриншотов по умолчанию — общий Docker-volume (без отдельного сервиса);
`minio` опционален — см. «Хранилище объектов» ниже.

```bash
make dev        # docker compose up -d --build, хвост логов bot+worker
make down
make migrate    # alembic upgrade head (в локальном venv, DATABASE_URL указывает на БД)
make migration  # alembic revision --autogenerate -m "..."
make lint        # ruff + mypy
make test-unit
make test-integration   # нужен реальный Postgres с доступным расширением `vector`
```

## Исходящий прокси (VPS без прямого доступа к Telegram/OpenAI)

Некоторые VPS-сети (частый случай у российских провайдеров) не могут достучаться напрямую до
`api.telegram.org`, `api.openai.com` или соцсетей. Если это твой случай: оставь `PROXY_URL` пустым
для обычного деплоя, либо заполни секцию прокси в `.env` и подними профиль `proxy`:

```bash
mkdir -p secrets
cp /path/to/your/tunnel/private_key secrets/proxy_ssh_key
chmod 600 secrets/proxy_ssh_key
# в .env: PROXY_SSH_HOST=, PROXY_SSH_USER=, PROXY_SSH_PORT=, и
# PROXY_URL=socks5://proxy:1080
docker compose --profile proxy up -d --build
```

Это поднимает дополнительный контейнер `proxy` (`docker/proxy/`), который держит `ssh -D`
SOCKS5-туннель (через `autossh`, с автопереподключением) до джамп-хоста, который у тебя уже есть и
с которого есть прямой доступ в интернет. `PROXY_URL` дальше единообразно прокидывает **весь**
исходящий трафик через него — polling Telegram (aiogram, через `aiohttp-socks`), SDK
OpenAI/Anthropic и все экстракторы контента (`safe_http.py`) — одна переменная окружения, без
ручной настройки под каждый сервис отдельно.

Два момента, о которых стоит знать:
- Используй просто `socks5://`, никогда не `socks5h://` — прокси-бэкенд aiogram (`aiohttp-socks`)
  напрочь отвергает суффикс `h`. И он, и SOCKS-транспорт httpx всегда резолвят DNS через сам
  прокси независимо от суффикса, так что ничего не теряется, если его не писать.
- Когда `PROXY_URL` задан, SSRF-проверка в `safe_http.py` пропускает локальный DNS-резолв (этот
  хост может вообще не уметь резолвить такие имена — в этом и есть весь смысл прокси) и вместо
  этого блокирует только явно опасные литеральные цели (loopback/приватные/link-local IP,
  указанные прямо в URL, и имена вроде `localhost`) перед тем как отдать имя хоста прокси для
  удалённого резолва.

### Если сам Docker не может стянуть образы (`docker compose ... --build` падает на pull)

Некоторые VPS-сети блокируют Docker Hub целиком, а не только Telegram/OpenAI — `docker compose up
--build` падает ещё до того, как заработает хоть строчка твоего кода, и контейнер `proxy` тут не
поможет (он сам не соберётся без своего базового образа). Разрываем порочный круг, подняв туннель
не в контейнере, а прямо на **хосте**, и направив на него сам демон Docker:

```bash
sudo apt-get update && sudo apt-get install -y autossh

sudo tee /etc/systemd/system/ssh-socks-proxy.service >/dev/null <<'EOF'
[Unit]
Description=SSH SOCKS5 tunnel for outbound proxy
After=network-online.target
Wants=network-online.target

[Service]
Environment=AUTOSSH_GATETIME=0
Environment=AUTOSSH_POLL=30
ExecStart=/usr/bin/autossh -M 0 -N \
  -o "BatchMode=yes" -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" \
  -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" -o "ExitOnForwardFailure=yes" \
  -D 0.0.0.0:1080 -p <PROXY_SSH_PORT> -i /path/to/secrets/proxy_ssh_key <PROXY_SSH_USER>@<PROXY_SSH_HOST>
Restart=always
RestartSec=5
User=<твой-linux-юзер>

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ssh-socks-proxy
sudo systemctl status ssh-socks-proxy   # должен быть active, без цикла рестартов

# Направляем собственные pull'ы Docker-демона через туннель:
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf >/dev/null <<'EOF'
[Service]
Environment="HTTP_PROXY=socks5://127.0.0.1:1080"
Environment="HTTPS_PROXY=socks5://127.0.0.1:1080"
Environment="NO_PROXY=localhost,127.0.0.1"
EOF
sudo systemctl daemon-reload && sudo systemctl restart docker

docker pull redis:7-alpine   # теперь должно получиться
```

Как только image pull заработал, направь приложение на **тот же самый** туннель на хосте, вместо
контейнерного `proxy` (один туннель, а не два) — в `.env`:

```
PROXY_URL=socks5://host.docker.internal:1080
```

`extra_hosts: host.docker.internal:host-gateway` (уже прописан в `docker-compose.yml` для
`bot`/`worker`/`api`) делает так, что это имя резолвится в адрес хоста из любого контейнера на
Linux. Дальше просто `docker compose up -d --build` (без `--profile proxy` — туннель на хосте
закрывает всё).

## Хранилище объектов (скриншоты)

По умолчанию `STORAGE_BACKEND=local` — скриншоты идут на общий Docker-volume
(`screenshots_data`, примонтирован и в `bot`, и в `worker`), без отдельного сервиса и без образа,
который нужно тянуть. Это стало дефолтом не просто так: `minio/minio` на Docker Hub теперь требует
логин (релицензирование MinIO на AGPL в 2024), а их же замена `quay.io/minio/minio` тоже начала
отдавать 401 на анонимные pull'ы. Вместо охоты за реестрами — для персонального деплоя на одном
VPS хранилищу скриншотов сторонний образ вообще не нужен.

Если тебе реально нужна S3-семантика (например, bot и worker разнесены по разным хостам без общей
файловой системы) — выстави `STORAGE_BACKEND=s3`, заполни `S3_*` в `.env` и подними опциональный
сервис:

```bash
docker compose --profile s3 up -d --build
```

Сервис `minio` в `docker-compose.yml` никуда не делся, смотрит на `quay.io` — если и этот образ к
моменту, когда ты это читаешь, тоже начнёт отдавать 401, просто замени строку `image:` на любой
другой S3-совместимый образ, больше ничего менять не придётся (`app/services/storage/base.py` —
интерфейс, который реализуют оба бэкенда).

## Переменные окружения

Полный список со значениями по умолчанию — в `.env.example`. Обязательные для реального запуска
бота:

| Переменная | Назначение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | от @BotFather |
| `DATABASE_URL` | `postgresql+asyncpg://...` |
| `REDIS_URL` | `redis://...` |
| `AI_PROVIDER` / `AI_API_KEY` / `AI_MODEL` | структурный анализ контента + разбор поисковых запросов |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS` | векторы для семантического поиска |
| `VISION_PROVIDER` / `VISION_MODEL` | понимание скриншотов/фото |

Опционально: `STORAGE_BACKEND` / `LOCAL_STORAGE_PATH` / `S3_*` (см. «Хранилище объектов» выше,
значения по умолчанию менять не нужно), `SENTRY_DSN`, `ADMIN_API_TOKEN` (закрывает `/admin/*` в
FastAPI-приложении), `TELEGRAM_ADMIN_IDS`, `SEARCH_WEIGHT_*` (веса гибридного ранжирования),
`RATE_LIMIT_*`, `PROXY_URL` / `PROXY_SSH_HOST` / `PROXY_SSH_PORT` / `PROXY_SSH_USER` /
`PROXY_SSH_KEY_PATH` (см. «Исходящий прокси» выше).

## Тесты

- `tests/unit` — чистая логика, без внешних сервисов: нормализация/дедупликация URL, определение
  платформы, валидация схем `ContentAnalysis`/`SearchFilter` (контролируемый словарь категорий
  проверяется строго), сборка `searchable_text`, rate limiting на Redis (через `fakeredis`),
  валидация URL от SSRF.
- `tests/integration` — запускаются на реальном PostgreSQL с расширением `vector` (точно как в
  проде; без подмены на sqlite, потому что у JSONB/TSVECTOR/pgvector нет заслуживающих доверия
  аналогов в sqlite). Тесты применяют настоящую Alembic-миграцию и проверяют: определение
  дубликатов, что пользователь никогда не может прочитать/добавить в избранное/удалить чужие
  `saved_items` или `collections`, что гибридный поиск scoped по пользователю и ранжирует
  лексически совпадающий элемент выше несвязанного, и что удаление данных пользователя каскадно
  затрагивает saved items/collections/tags.

  ```bash
  createdb savebot_test && psql savebot_test -c "CREATE EXTENSION vector; CREATE EXTENSION pgcrypto;"
  export DATABASE_URL=postgresql+asyncpg://<user>:<pass>@localhost:5432/savebot_test
  pytest tests/integration -m integration
  ```

Внешние AI/extraction API в тестах никогда не вызываются вживую — извлечение тестируется как
чистые функции через `url_utils`, а AI-провайдеры проверяются только через их Pydantic-контракты,
без реальных запросов.

## Что реализовано (P0 + большая часть P1)

- Авторизация и автоматическая регистрация пользователей в Telegram, онбординг, i18n (по
  умолчанию ru, en подготовлен)
- Приём ссылок для Instagram/TikTok/YouTube/YouTube Shorts/Pinterest/Threads/любой веб-страницы,
  с защищённым от SSRF получением данных и плавной деградацией (при неудачном извлечении ссылка
  всё равно сохраняется)
- Приём скриншотов/фото через vision-модель, хранение на локальном Docker-volume по умолчанию
  (S3-совместимое хранилище опционально)
- AI-классификация по контролируемому словарю категорий + свободные подкатегории/теги/сущности
- Embeddings + хранение в pgvector
- Гибридный (лексический + семантический + метаданные + свежесть) поиск на естественном языке,
  команда `/search` не нужна — любое сообщение, которое не ссылка и не команда, трактуется как
  запрос к библиотеке
- Карточки в Telegram с действиями избранное/коллекция/редактировать/удалить, пагинация по
  результатам
- Определение дубликатов по нормализованным каноническим URL (tracking-параметры вырезаются) с
  подсказкой «ты уже сохранял это»
- Коллекции (создание/добавление/список), свободные заметки на любой сохранёнке (участвуют в
  поиске), полный флоу редактирования (название/категория/теги/заметка)
- `/settings` со сменой языка и полным удалением данных (каскадно везде, с шагом подтверждения)
- `/stats` (всего сохранено, избранное, разбивка по категориям)
- Асинхронный пайплайн на arq с ретраями/backoff, идемпотентной постановкой задач, лимитами на
  конкурентность и rate limit на пользователя, структурированное логирование с контекстом
  request/user/job, хук для Sentry
- Стек Docker Compose, Alembic-миграция (написана вручную, включает индекс pgvector и FTS-триггер),
  наборы unit- и integration-тестов, ruff + mypy без замечаний
- Опциональный исходящий SOCKS5-прокси (`docker compose --profile proxy`) для VPS-сетей без
  прямого доступа к Telegram/OpenAI/соцсетям — единообразно маршрутизирует весь исходящий трафик

Не реализовано (P2, осознанно отложено): подписки/кредиты, рекомендации, шаринг коллекций,
веб-интерфейс.

## Ограничения по платформам (честно, как есть)

- **Instagram**: Meta отключила публичный oEmbed-эндпоинт в 2020 году (теперь нужен одобренный
  app-токен Graph API, который этот MVP не запрашивает). Используется fallback на
  OpenGraph/JSON-LD публичной страницы — работает для подписей/превью у большинства публичных
  постов, у закрытых аккаунтов или контента с возрастным ограничением возвращает намного меньше.
  Ссылка при этом сохраняется в любом случае.
- **TikTok**: полноценный публичный oEmbed (название, автор, превью) — без авторизации, работает
  хорошо.
- **YouTube / Shorts**: публичный oEmbed даёт название/автора/превью. Для полных описаний и
  субтитров-как-транскрипта нужен YouTube Data API v3 (API-ключ) — вне рамок MVP, оставлено как
  задокументированная точка расширения (`YouTubeExtractor`).
- **Pinterest**: недокументированный, но рабочий oEmbed для многих пинов, иначе fallback на
  OpenGraph.
- **Threads**: публичного oEmbed вообще нет; полагается целиком на OpenGraph/JSON-LD, который Meta
  отдаёт в урезанном виде неавторизованным запросам.
- Ничто из вышеперечисленного не обходит логин-стены, CAPTCHA, DRM или paywall — это осознанное
  архитектурное решение (см. докстринги в `app/extractors`). Там, где извлечь реальный контент не
  получилось, бот всё равно сохраняет URL и сообщает пользователю, что часть информации получить не
  удалось.

## Следующие 5 улучшений с максимальным продуктовым эффектом

1. **Reranking (переранжирование) через cross-encoder или LLM-проход по top-K результатов
   гибридного поиска** — текущая линейно-взвешенная формула — хорошая база для MVP, но reranker
   заметно повысит точность на неоднозначных запросах («то место с видом»).
2. **Интеграция YouTube Data API** для описаний и субтитров-как-транскрипта — сейчас сохранёнки с
   YouTube самые слабые по данным (только название/автор/превью).
3. **Фоновая задача повторной обработки** для сохранёнок, завершившихся с
   `processing_status=failed` или без embedding (временные сбои AI/извлечения) — плановый повтор
   через arq cron вместо того, чтобы пользователь сам замечал проблему и пересылал ссылку.
4. **Более умное определение дубликатов** — не только по каноническому URL, например
   дедупликация по схожести embedding, чтобы ловить один и тот же контент, репостнутый с другой
   платформы/URL.
5. **Проактивный дайджест** («ты сохранил 12 штук про Париж — прислать сводку перед поездкой?») —
   это самое чистое выражение замыкания цикла CAPTURE→RETRIEVE без необходимости пользователю
   самому вспоминать, что спросить.
