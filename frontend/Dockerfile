FROM node:20-alpine

WORKDIR /app

# copy full source then install dependencies
COPY frontend/ ./

# enable corepack and install dependencies
RUN corepack enable && corepack prepare pnpm@latest --activate
# Allow install even if lockfile is out-of-date to avoid CI-only failure;
# for deterministic builds update `pnpm-lock.yaml` in repo when convenient.
RUN pnpm install --no-frozen-lockfile

ENV HOST=0.0.0.0
EXPOSE 3000

CMD ["sh", "-c", "pnpm dev"]
