FROM node:20-alpine

WORKDIR /app

# copy package manifests first for efficient caching
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# enable corepack and install dependencies
RUN corepack enable && corepack prepare pnpm@latest --activate
RUN pnpm install --frozen-lockfile

# copy rest of source
COPY frontend/ ./

EXPOSE 3000

CMD ["pnpm", "dev", "--host"]
