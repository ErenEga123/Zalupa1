# Reader System MVP

Production-minded MVP monorepo with FastAPI backend, aiogram Telegram bot, PostgreSQL metadata store, disk-based book storage, and installable PWA reader with offline cache + sync.

## Structure

- `backend/` FastAPI app (API, processing queue, OPDS, web app/PWA)
- `bot/` aiogram Telegram bot
- `database/` SQL/bootstrap assets
- `library/books/` persistent book storage by UUID
- `temp/` temporary uploads/processing
- `docker-compose.yml`
- `.env.example`

## Run

1. Copy env file:

```bash
cp .env.example .env
```

2. Fill required values (`BOT_TOKEN`, `JWT_SECRET`, OAuth/SMTP vars if used).
3. Start stack:

```bash
docker compose up --build
```

4. Open:
- API health: `http://localhost:8000/health`
- PWA app: `http://localhost:8000/app`
- OPDS root: `http://localhost:8000/opds`

## Main API groups

- `/health`
- `/opds`
- `/opds/books`
- `/app`
- `/api/v1/auth/*`
- `/api/v1/library`
- `/api/v1/books/*`
- `/api/v1/progress`
- `/api/v1/users/*`
- `/api/v1/favorites`
- `/api/v1/subscriptions`

## End-to-end flow

1. Telegram user uploads EPUB/FB2/PDF.
2. Bot sends multipart upload to backend `/api/v1/books/upload`.
3. Backend stores file at `library/books/{book_id}/original.{ext}`, creates DB rows, enqueues processing task.
4. Internal DB-backed queue runner picks tasks and processes chapters/pages into `library/books/{book_id}/processed/`.
5. Web app lists book in `/api/v1/library` and reads only via processed endpoints:
   - `GET /api/v1/books/{id}/chapters`
   - `GET /api/v1/books/{id}/chapter/{chapter_id}`
6. Service worker + IndexedDB cache app shell, chapters, metadata, progress, and pending sync queue.
7. Progress sync uses timestamp conflict control at `POST /api/v1/progress`; stale writes are rejected with authoritative server state.

## Auth

- Telegram login verification endpoint: `POST /api/v1/auth/telegram`
- Google OAuth authorization-code exchange: `POST /api/v1/auth/google`
- Email magic link request/consume:
  - `POST /api/v1/auth/magic/request`
  - `POST /api/v1/auth/magic/consume`
- JWT access + refresh token lifecycle:
  - `POST /api/v1/auth/refresh`

## Processing + queue behavior

- Task statuses: `pending`, `processing`, `ready`, `failed`
- Retry attempts tracked by `attempt_count` with max attempts (default 3)
- On restart, in-flight `processing` tasks reset to `pending` and resumed
- Errors preserved in `processing_tasks.error_message`

## Storage design

- UUID per book (metadata key)
- `library/books/{book_id}/original.{ext}`
- `library/books/{book_id}/processed/*`
- optional cover at `library/books/{book_id}/cover.jpg`
- Metadata and access rules in PostgreSQL, chapter/page content on disk

## Tests

Run inside backend container or locally in `backend/`:

```bash
pytest -q
```

Included tests cover health, config, startup init, extraction, duplicate handling, access control, progress anti-regression, concurrent-ish progress ordering behavior, upload size limits, invalid EPUB handling, auth behavior, processing transitions/retry, and queue resume semantics.
