# Docker development setup

This repository includes Dockerfiles for the backend and frontend plus a `docker-compose.yml` to run a local Postgres, the FastAPI backend, and the Next.js frontend.

Quick start (Linux/Windows with Docker Desktop):

```bash
# build and start services
docker compose up --build

# stop
docker compose down
```

Once the containers are running, editing files on your machine should be reflected automatically in the browser because the backend and frontend source folders are bind-mounted into the containers.

If you change dependencies or Dockerfiles, run:

```bash
docker compose up --build -d
```

For normal code edits, you usually only need to save the file and refresh the page.

If another teammate wants to test the same setup:

```bash
# if they already cloned the repo, update first
git fetch origin
git switch develop
git pull

# then start Docker
docker compose up --build
```

If they are starting from a fresh clone, they only need to make sure Docker Desktop is running and that these files exist locally:
- `backend/.env.local`
- `frontend/.env.local`

Then run `docker compose up --build` from the repository root.

Environment notes:
- The `backend` service reads `backend/.env.local`.
- The `frontend` service reads `frontend/.env.local`.
- `docker-compose.yml` still sets `DATABASE_URL` for the backend container so it can reach the local `db` service.
- The Postgres data is persisted in a Docker volume `db-data`.
- Do not create a root `.env` for this setup unless you intentionally want to override the per-app env files.

Troubleshooting:
- To run migrations manually: run a one-off command against the backend container, e.g. `docker compose run --rm backend alembic upgrade head` (adjust to your migration tooling).
- If you change `backend/.env.local` or `frontend/.env.local`, restart the affected container with `docker compose up -d --force-recreate backend frontend`.
