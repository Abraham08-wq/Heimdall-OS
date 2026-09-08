# =============================================================================
# ProjectXY Frontend — Multi-stage Docker Build
# Node 20 LTS, Next.js standalone, non-root execution
# =============================================================================

# Stage 1: Install ALL dependencies (including devDeps needed for build)
FROM node:20-alpine AS deps
WORKDIR /app

RUN apk add --no-cache libc6-compat
COPY package.json package-lock.json* ./
# Install ALL deps (incl. devDeps) — needed for TypeScript, tailwindcss, postcss
RUN npm ci

# Stage 2: Build application
FROM node:20-alpine AS builder
WORKDIR /app

ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=${BACKEND_URL}
ENV NEXT_TELEMETRY_DISABLED=1
# Disable ESLint during Docker build to prevent lint-only warnings from failing
ENV NEXT_DISABLE_ESLINT=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Run build; ESLint warnings are non-fatal, TypeScript errors are fatal
RUN npm run build

# Stage 3: Production runner — minimal image, only standalone output
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Security: non-root user
RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs
# Ensure curl is available for the Docker HEALTHCHECK (run as root)
RUN apk add --no-cache curl

# Copy standalone build (output: standalone) — no node_modules needed at runtime
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
USER nextjs
EXPOSE 3000

# Health check — Traefik uses this
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://127.0.0.1:3000/healthz >/dev/null || exit 1

CMD ["node", "server.js"]
