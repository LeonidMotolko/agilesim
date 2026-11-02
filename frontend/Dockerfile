# syntax=docker/dockerfile:1

# ---- build: compile the static bundle ----
FROM node:22-alpine AS build
WORKDIR /app
# The pnpm version is pinned by "packageManager" in package.json.
RUN corepack enable

# pnpm-lock.yaml is optional until it is committed; the wildcard keeps the COPY valid either way.
COPY package.json pnpm-lock.yaml* ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --no-frozen-lockfile

COPY . .
RUN pnpm build

# ---- runtime: nginx serves the bundle and proxies /api to the backend ----
FROM nginx:stable-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
