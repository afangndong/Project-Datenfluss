# syntax=docker/dockerfile:1.7
# ---------- Stage 1: Build (Wheels bauen, Layer-Cache über BuildKit) ----------
FROM python:3.15-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir /wheels -r requirements.txt

# ---------- Stage 2: Runtime (klein, ohne Build-Tools, non-root) ----------
FROM python:3.15-slim AS runtime
ARG APP_VERSION=1.0.0
ARG GIT_SHA=local
LABEL org.opencontainers.image.title="mini-kos" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} GIT_SHA=${GIT_SHA}

RUN groupadd --system --gid 10001 kos && useradd --system --uid 10001 --gid kos --no-create-home kos
WORKDIR /srv
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl && rm -rf /wheels
COPY app ./app

USER 10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
