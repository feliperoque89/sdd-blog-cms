# syntax=docker/dockerfile:1
#
# TEMPLATE — o diretório `frontend/` (Next.js App Router, ver CLAUDE.md)
# ainda não foi scaffoldado neste repositório. Este Dockerfile segue o
# padrão multi-stage recomendado pela documentação do Next.js para builds
# de produção mínimas e é o que a imagem `frontend` do Kubernetes
# (`k8s/frontend.yaml`) espera.
#
# Pré-requisito quando o app for criado: `next.config.js`/`next.config.ts`
# precisa de `output: "standalone"` (gera `.next/standalone`, um servidor
# Node autocontido sem precisar de `node_modules` completo na imagem final).
#
# Build a partir da raiz do monorepo:
#   docker build -f docker/frontend.Dockerfile -t sdd-blog-cms-frontend:local frontend/

FROM node:20-alpine AS deps
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /build
COPY --from=deps /build/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* precisa existir em build-time (fica embutido no bundle
# cliente) — em produção real, injete via --build-arg no passo de CI/CD.
ARG NEXT_PUBLIC_API_URL=http://backend:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:20-alpine AS runtime
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs
WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=builder /build/public ./public
COPY --from=builder --chown=nextjs:nodejs /build/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /build/.next/static ./.next/static

USER nextjs
EXPOSE 3000

CMD ["node", "server.js"]
