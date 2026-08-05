# syntax=docker/dockerfile:1
#
# Imagem única usada por dois componentes Kubernetes (mesma imagem, comando
# diferente — ver k8s/backend.yaml e k8s/worker.yaml):
#   - `backend`: `uvicorn app.main:app` (API HTTP, ver CMD abaixo).
#   - `worker`: `python -m app.workers.ai_worker` (consumidor da fila de
#     geração de rascunhos via IA, SPEC-003), sobrescrito via `command` no
#     Deployment do worker.
#
# Build a partir da raiz do monorepo:
#   docker build -f docker/backend.Dockerfile -t sdd-blog-cms-backend:local backend/

FROM python:3.12-slim AS builder

WORKDIR /build

# build-essential só existe nesta stage (descartada no estágio final) — rede
# de segurança para dependências com extensão nativa (cryptography, bcrypt,
# asyncmy) em plataformas sem wheel pré-compilada no PyPI.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Só as dependências de produção (`[project.dependencies]`) — nunca o extra
# `dev` (pytest/mypy/ruff/black), que não pertence à imagem publicada.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser
EXPOSE 8000

# Best-effort para uso local (`docker run` isolado, fora do cluster) — em
# Kubernetes quem decide se o pod está saudável são as probes do próprio
# Deployment (`k8s/backend.yaml`), não este HEALTHCHECK.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
