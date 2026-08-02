# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

FROM python:3.12.13-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
RUN python -m pip install --root-user-action=ignore uv==0.12.1
COPY pyproject.toml uv.lock README.md ./
COPY revai ./revai
RUN uv export --frozen --no-dev --no-emit-project --no-hashes --output-file /tmp/requirements.txt \
    && python -m pip wheel --wheel-dir /wheels --requirement /tmp/requirements.txt \
    && uv build --wheel --out-dir /wheels

FROM python:3.12.13-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    REVAI_ENVIRONMENT=production \
    REVAI_HOST=0.0.0.0 \
    REVAI_PORT=8799 \
    REVAI_DATA_DIR=/data

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 revai \
    && useradd --uid 10001 --gid revai --create-home --home-dir /home/revai revai

COPY --from=builder /wheels /wheels
RUN python -m pip install --root-user-action=ignore /wheels/*.whl && rm -rf /wheels

RUN mkdir --parents /data && chown revai:revai /data
USER 10001:10001
WORKDIR /data

EXPOSE 8799
VOLUME ["/data"]
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8799/api/health', timeout=2).read()"]

CMD ["revai", "serve", "--no-reload"]
