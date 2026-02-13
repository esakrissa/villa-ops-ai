FROM node:22-alpine AS base

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy application code
COPY . .

# ─── Development ─────────────────────────────────────────────────────────────
FROM base AS dev

ENV NODE_ENV=development
EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]

# ─── Production build ────────────────────────────────────────────────────────
FROM base AS build

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# Empty string = use relative paths (frontend behind nginx on same domain)
ENV NEXT_PUBLIC_API_URL=""

RUN npm run build

# ─── Production runtime ──────────────────────────────────────────────────────
FROM node:22-alpine AS prod

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built output
COPY --from=build /app/public ./public
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD wget -q --spider http://localhost:3000 || exit 1

# Force HOSTNAME=0.0.0.0 at runtime so Next.js binds to all interfaces.
# ECS Fargate overrides the ENV HOSTNAME with the container's internal hostname,
# which causes Next.js to bind to a specific IP (breaking localhost health checks).
CMD ["sh", "-c", "HOSTNAME=0.0.0.0 exec node server.js"]
