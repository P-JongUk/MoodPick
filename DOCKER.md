# Docker development setup

This repository includes Dockerfiles for the backend and frontend plus a `docker-compose.yml` to run a local Postgres, the FastAPI backend, and the Next.js frontend.

Quick start (Linux/Windows with Docker Desktop):

```bash
# build and start services
docker compose up --build

# stop
docker compose down
```

Environment notes:
- The `backend` service reads environment variables from the repository `.env`. Ensure `DATABASE_URL` and any API keys are set; `docker-compose.yml` sets a default `DATABASE_URL` pointing to the `db` service.
- The Postgres data is persisted in a Docker volume `db-data`.

Troubleshooting:
- To run migrations manually: run a one-off command against the backend container, e.g. `docker compose run --rm backend alembic upgrade head` (adjust to your migration tooling).
