# SaveBot

> Русская версия: [README.ru.md](README.ru.md) (поддерживается синхронно с этим файлом).

A Telegram bot that turns links (Instagram/TikTok/YouTube/Pinterest/Threads/any web page) and
screenshots into a searchable personal AI library. Send it something interesting; later, describe
it in your own words and get it back.

Product principle: **CAPTURE → UNDERSTAND → ORGANIZE → RETRIEVE**. This is not a downloader — the
bot rarely stores the original media, it stores *understanding* of the content plus a link back to
the source.

## Architecture

```
Telegram (aiogram 3)
   │  handlers do only: validate, dedup-check, write a `saved_items` row (status=pending),
   │  enqueue a job, show a status message
   ▼
Redis (arq queue)
   ▼
Worker (arq)
   │  extraction -> AI classification -> embedding -> DB update -> edit the Telegram status
   │  message into the final card
   ▼
PostgreSQL + pgvector (all queries scoped by user_id)
```

- **Bot** (`app/bot`): aiogram 3 handlers/middlewares/keyboards/i18n. Handlers never block on
  network/AI calls — they persist minimal state and hand off to the queue.
- **Extractors** (`app/extractors`): one `ContentExtractor` per platform behind a common interface,
  using oEmbed where available and OpenGraph/JSON-LD/HTML meta otherwise. See "Platform
  limitations" below — no scraping-behind-login, no CAPTCHA/DRM bypass.
- **AI abstraction** (`app/services/ai`): `LLMProvider` / `EmbeddingProvider` / `VisionProvider`
  Protocols selected at runtime via `AI_PROVIDER` / `EMBEDDING_PROVIDER` / `VISION_PROVIDER`. OpenAI
  is the fully-functional reference implementation (chat + vision + embeddings); an Anthropic
  provider covers chat + vision to prove the abstraction isn't vendor-locked (Anthropic has no
  embeddings endpoint, so embeddings must come from another provider).
- **Search** (`app/services/search`): hybrid ranking — Postgres full-text search (lexical) +
  pgvector cosine similarity (semantic) + a soft metadata boost + a recency/usage decay, combined
  via a weighted formula (`app/core/config.py: SearchWeights`). An optional LLM step turns a
  free-text query into structured filters (`SearchFilter`); if that call fails, search still runs
  on the raw query.
- **Security** (`app/services/security`): every outbound fetch (link previews, image downloads)
  goes through `safe_http.safe_get`, which blocks non-http(s) schemes, resolves and rejects
  loopback/private/link-local/reserved IPs (SSRF/metadata-endpoint protection), caps redirects,
  enforces a response-size cap while streaming, and enforces a timeout.
- **Queue** (`app/workers`, [arq](https://github.com/samuelcolvin/arq)): chosen over Celery/Dramatiq
  because it's asyncio-native — the worker shares the same async SQLAlchemy sessions and httpx
  clients as the bot, no thread/process bridging. Built-in retry; a manual exponential backoff
  wrapper (`_backoff_or_raise`) handles infra failures (DB/Redis blips), while
  extraction/AI/embedding failures are caught *inside* the pipeline and never crash the job — the
  item is still saved with whatever partial data was captured. `_job_id` on `enqueue_job` gives
  idempotent job submission for free.

## Project structure

```
app/
  api/            FastAPI: /health, /ready, token-gated /admin/*
  bot/
    handlers/     start, intake (URL/photo/search dispatch), browse (pagination),
                  item_actions (favorite/edit/delete), collections, library, settings
    keyboards/    aiogram CallbackData factories
    middlewares/  error handling, logging context, DB session, user auth/scoping, rate limit
    i18n/         ru/en string tables (t(key, locale=...))
    states/       FSM states for edit/collection-name flows
    rendering.py  SavedItem -> Telegram card text + inline keyboard (shared by bot & worker)
    factory.py    Bot construction incl. outbound proxy wiring (shared by bot & worker)
  core/           config (pydantic-settings), logging (structlog), redis, arq pool
  db/
    models/       SQLAlchemy 2 async models (users, saved_items, collections, tags, ...)
    repositories/ all queries scoped by user_id here — the only place that touches SQL
  extractors/     ContentExtractor + per-platform implementations + registry
  schemas/        ContentMetadata / ContentAnalysis / SearchFilter (Pydantic v2)
  services/
    ai/           LLMProvider/EmbeddingProvider/VisionProvider + OpenAI/Anthropic + factory
    content/      url normalization/platform detection, pipeline orchestration, searchable_text
    search/       hybrid search service, Redis-backed pagination session store
    security/     SSRF-safe HTTP client, rate limiting
    storage/      S3-compatible (MinIO-friendly) object storage for screenshots
  workers/        arq WorkerSettings + job bodies
docker/proxy/     optional ssh -D SOCKS5 tunnel container (see "Outbound proxy" below)
migrations/       Alembic (hand-written initial schema incl. pgvector + FTS trigger)
tests/
  unit/           no DB/network: URL normalization, schemas, searchable_text, rate limit, SSRF
  integration/    real Postgres+pgvector: user scoping, dedup, favorites, delete cascade, search
```

## Running it

```bash
cp .env.example .env
# fill in TELEGRAM_BOT_TOKEN and AI_API_KEY at minimum
docker compose up -d --build
```

Services: `postgres` (pgvector image), `redis`, `minio` (S3-compatible storage), a one-shot
`migrate` job (`alembic upgrade head`), `bot`, `worker`, `api`. `bot`/`worker`/`api` all wait on
`migrate` completing successfully.

```bash
make dev        # docker compose up -d --build, tails bot+worker logs
make down
make migrate    # alembic upgrade head (inside your local venv, DATABASE_URL pointed at the DB)
make migration  # alembic revision --autogenerate -m "..."
make lint        # ruff + mypy
make test-unit
make test-integration   # needs a real Postgres with the `vector` extension available
```

## Outbound proxy (VPS with no direct route to Telegram/OpenAI)

Some VPS networks (common for RU-hosted providers) can't reach `api.telegram.org`,
`api.openai.com`, or social platforms directly. If that's your case: leave `PROXY_URL` unset for a
normal deploy, or fill in the proxy section of `.env` and bring up the `proxy` profile:

```bash
mkdir -p secrets
cp /path/to/your/tunnel/private_key secrets/proxy_ssh_key
chmod 600 secrets/proxy_ssh_key
# in .env: PROXY_SSH_HOST=, PROXY_SSH_USER=, PROXY_SSH_PORT=, and
# PROXY_URL=socks5://proxy:1080
docker compose --profile proxy up -d --build
```

This starts an extra `proxy` container (`docker/proxy/`) that holds an `ssh -D` SOCKS5 tunnel
(via `autossh`, auto-reconnecting) to a jump host you already control that *does* have direct
internet access. `PROXY_URL` then routes **all** outbound traffic through it uniformly — Telegram
polling (aiogram, via `aiohttp-socks`), the OpenAI/Anthropic SDKs, and every content extractor
(`safe_http.py`) — one env var, no per-service special-casing.

Two things worth knowing:
- Use plain `socks5://`, never `socks5h://` — aiogram's proxy backend (`aiohttp-socks`) rejects
  the `h` suffix outright. Both it and httpx's SOCKS transport always resolve DNS through the
  proxy regardless of the suffix, so nothing is lost by omitting it.
- When `PROXY_URL` is set, `safe_http.py`'s SSRF check skips local DNS resolution (this host may
  not be able to resolve these hostnames at all — that's the whole reason the proxy exists) and
  instead blocks only literal dangerous targets (loopback/private/link-local IPs typed directly in
  the URL, and hostnames like `localhost`) before handing the hostname to the proxy to resolve
  remotely.

### If Docker itself can't pull images (`docker compose ... --build` fails on the pull)

Some VPS networks block Docker Hub entirely, not just Telegram/OpenAI — `docker compose up --build`
fails before any of your code even runs, so the `proxy` *container* above can't help (it can't be
built without pulling its own base image). Break the chicken-and-egg by running the tunnel on the
**host** instead, and pointing the Docker daemon itself at it:

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
User=<your-linux-user>

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ssh-socks-proxy
sudo systemctl status ssh-socks-proxy   # should be active, no restart loop

# Point the Docker daemon's own image pulls through it:
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf >/dev/null <<'EOF'
[Service]
Environment="HTTP_PROXY=socks5://127.0.0.1:1080"
Environment="HTTPS_PROXY=socks5://127.0.0.1:1080"
Environment="NO_PROXY=localhost,127.0.0.1"
EOF
sudo systemctl daemon-reload && sudo systemctl restart docker

docker pull redis:7-alpine   # should now succeed
```

Once image pulls work, point the app at the *same* host tunnel instead of the containerized
`proxy` service (one tunnel, not two) — in `.env`:

```
PROXY_URL=socks5://host.docker.internal:1080
```

`extra_hosts: host.docker.internal:host-gateway` (already in `docker-compose.yml` for
`bot`/`worker`/`api`) makes that hostname resolve to the host from inside any container on Linux.
Then just `docker compose up -d --build` (no `--profile proxy` needed — the host tunnel covers
everything).

## Environment variables

See `.env.example` for the full list with defaults. Required to actually run the bot:

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | from @BotFather |
| `DATABASE_URL` | `postgresql+asyncpg://...` |
| `REDIS_URL` | `redis://...` |
| `AI_PROVIDER` / `AI_API_KEY` / `AI_MODEL` | structured content analysis + search query parsing |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS` | semantic search vectors |
| `VISION_PROVIDER` / `VISION_MODEL` | screenshot/photo understanding |
| `S3_ENDPOINT` / `S3_BUCKET` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` | screenshot storage (MinIO by default) |

Optional: `SENTRY_DSN`, `ADMIN_API_TOKEN` (gates `/admin/*` on the FastAPI app),
`TELEGRAM_ADMIN_IDS`, `SEARCH_WEIGHT_*` (hybrid ranking weights), `RATE_LIMIT_*`,
`PROXY_URL` / `PROXY_SSH_HOST` / `PROXY_SSH_PORT` / `PROXY_SSH_USER` / `PROXY_SSH_KEY_PATH`
(see "Outbound proxy" above).

## Tests

- `tests/unit` — pure logic, no external services: URL normalization/dedup, platform detection,
  `ContentAnalysis`/`SearchFilter` schema validation (controlled category vocabulary is enforced),
  `searchable_text` construction, Redis-backed rate limiting (via `fakeredis`), SSRF URL validation.
- `tests/integration` — run against a real PostgreSQL with the `vector` extension (matches
  production exactly; no sqlite substitution, since JSONB/TSVECTOR/pgvector don't have sqlite
  equivalents worth trusting). They apply the real Alembic migration, then verify: duplicate
  detection, that a user can never read/favorite/delete another user's `saved_items` or
  `collections`, that hybrid search is user-scoped and ranks a lexically-matching item above an
  unrelated one, and that deleting a user's data cascades through saved items/collections/tags.

  ```bash
  createdb savebot_test && psql savebot_test -c "CREATE EXTENSION vector; CREATE EXTENSION pgcrypto;"
  export DATABASE_URL=postgresql+asyncpg://<user>:<pass>@localhost:5432/savebot_test
  pytest tests/integration -m integration
  ```

External AI/extraction APIs are never called in tests — extraction is pure-function tested via
`url_utils`, and AI providers are only exercised through their Pydantic contracts, not live calls.

## What's implemented (P0 + most of P1)

- Telegram auth/user-provisioning, onboarding, i18n (ru default, en scaffolded)
- URL intake for Instagram/TikTok/YouTube/YouTube Shorts/Pinterest/Threads/any web page, with
  SSRF-hardened fetching and graceful degradation (a failed extraction still saves the URL)
- Screenshot/photo intake via vision model, stored in S3-compatible storage
- AI structured classification into a controlled category vocabulary + free subcategory/tags/entities
- Embeddings + pgvector storage
- Hybrid (lexical + semantic + metadata + recency) natural-language search, no `/search` required
  — any non-URL, non-command message is treated as a library query
- Telegram cards with favorite/collection/edit/delete actions, pagination through result sets
- Duplicate detection via normalized canonical URLs (tracking params stripped) with a
  "you already saved this" prompt
- Collections (create/add/list), free-text notes on any item (searchable), full edit flow
  (title/category/tags/note)
- `/settings` with language switch and full data deletion (cascades everywhere, confirmation step)
- `/stats` (totals, favorites, per-category breakdown)
- Async pipeline via arq with retry/backoff, idempotent job submission, per-user concurrency and
  rate limits, structured logging with request/user/job context, Sentry hook
- Docker Compose stack, Alembic migration (hand-written, includes the pgvector index and the FTS
  trigger), unit + integration test suites, ruff + mypy clean
- Optional outbound SOCKS5 proxy (`docker compose --profile proxy`) for VPS networks without a
  direct route to Telegram/OpenAI/social platforms — routes all outbound traffic uniformly

Not built (P2, intentionally deferred): subscriptions/credits, recommendations, collection
sharing, a web UI.

## Platform limitations (be upfront about these)

- **Instagram**: Meta deprecated the public oEmbed endpoint in 2020 (now requires an approved
  Graph API app token, which this MVP doesn't request). Falls back to OpenGraph/JSON-LD on the
  public page — works for captions/thumbnails on most public posts, returns much less for private
  accounts or age-gated content. The link is always saved regardless.
- **TikTok**: full public oEmbed (title, author, thumbnail) — no auth needed, works well.
- **YouTube / Shorts**: public oEmbed gives title/author/thumbnail. Full descriptions and caption
  transcripts need the YouTube Data API v3 (an API key) — out of scope for MVP, left as a documented
  extension point (`YouTubeExtractor`).
- **Pinterest**: undocumented-but-functional oEmbed for many pins, OpenGraph fallback otherwise.
- **Threads**: no public oEmbed at all; relies entirely on OpenGraph/JSON-LD, which Meta serves in
  reduced form to logged-out requests.
- None of the above bypass login walls, CAPTCHAs, DRM, or paywalls — by design (see `app/extractors`
  docstrings). Where extraction can't get real content, the bot still saves the URL and tells the
  user part of the info is missing.

## Next 5 improvements with the highest product leverage

1. **Reranking with a cross-encoder or LLM pass over the top-K hybrid results** — the current
   linear-weighted formula is a solid MVP baseline, but a reranker would meaningfully improve
   precision on ambiguous queries ("that place with the view").
2. **YouTube Data API integration** for descriptions + captions-as-transcript — right now YouTube
   saves are the weakest of the platforms (title/author/thumbnail only).
3. **Background re-processing job** for items that finished with `processing_status=failed` or
   with no embedding (transient AI/extraction failures) — a scheduled arq cron retry rather than
   requiring the user to notice and resend.
4. **Smarter duplicate detection** beyond canonical-URL matching — e.g. embedding-similarity dedup
   to catch the same content reshared from a different platform/URL.
5. **Proactive digest** ("you saved 12 things about Paris — want a summary before your trip?") —
   this is the clearest expression of the CAPTURE→RETRIEVE loop closing without the user having to
   remember to ask.
