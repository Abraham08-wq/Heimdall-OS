# syntax=docker/dockerfile:1

# ── deps: install dependencies only (cached separately from source changes) ──
FROM node:20-alpine AS deps
WORKDIR /app
RUN apk add --no-cache libc6-compat
COPY package.json package-lock.json* ./
RUN npm ci

# ── builder: build the Next.js app ───────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# FIXED (fix_login.sh): these ARG/ENV lines MUST come before `RUN npm run build`.
# Next.js inlines NEXT_PUBLIC_* variables into the compiled JavaScript at build
# time — they are read from `process.env` while webpack is bundling, not at
# container runtime. Without these two lines here, docker-compose.yml's
# `build.args: NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL}` has nothing to land
# on inside the image, so the value never reaches `next build` and the compiled
# bundle silently falls back to whatever default is hardcoded in the source
# (this is exactly how the login page ended up calling http://localhost:8000
# directly instead of going through Traefik).
#
# Putting them here (rather than only in the final `runner` stage) also fixes
# Docker's build cache: a value change now correctly invalidates this layer and
# every layer after it, instead of silently reusing an old cached build result
# from before the value changed (which is what caused `CACHED [builder 5/5]
# RUN npm run build` to wrongly reuse a stale build).
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ARG BACKEND_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV BACKEND_URL=$BACKEND_URL
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ── runner: minimal production image ─────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs
RUN apk add --no-cache curl

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=5 \
  CMD curl -f http://127.0.0.1:3000/ || exit 1

CMD ["node", "server.js"]
