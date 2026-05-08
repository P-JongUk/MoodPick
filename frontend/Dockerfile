FROM node:20-alpine

WORKDIR /app

# copy full source then install dependencies
COPY frontend/ ./

# enable corepack and use the same pnpm version for every Docker build
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate
# Allow install even if lockfile is out-of-date to avoid CI-only failure;
# for deterministic builds update `pnpm-lock.yaml` in repo when convenient.
RUN pnpm install --no-frozen-lockfile

ENV HOST=0.0.0.0
ENV WATCHPACK_POLLING=true
ENV CHOKIDAR_USEPOLLING=true
ENV NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000

CMD ["sh", "-c", "pnpm exec next dev --webpack --hostname 0.0.0.0"]
