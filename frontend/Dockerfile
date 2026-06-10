FROM node:20-alpine

WORKDIR /app

# Lockfile-driven install (package-lock.json must list all dependencies).
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

ENV HOST=0.0.0.0
ENV WATCHPACK_POLLING=true
ENV CHOKIDAR_USEPOLLING=true
ENV NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000

CMD ["sh", "-c", "npx next dev --webpack --hostname 0.0.0.0"]
