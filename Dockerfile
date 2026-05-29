FROM python:3.12-slim-bookworm AS builder

ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0

COPY pyproject.toml /tmp/goga/
COPY goga/ /tmp/goga/goga/

RUN pip install --no-cache-dir /tmp/goga && \
    rm -rf /tmp/goga

FROM ghcr.io/umputun/ralphex:latest AS ralphex-source

FROM python:3.12-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git jq ripgrep fzf openssh-client bash make gcc g++ curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ralphex-source /srv/ralphex /srv/ralphex
RUN chmod +x /srv/ralphex

COPY --from=builder /usr/local/lib/python3.12/site-packages /opt/goga/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/goga /opt/goga/bin/goga

RUN useradd -m -s /bin/bash goga && \
    python3 -m venv /opt/goga && \
    sed -i "s|/usr/local|/opt/goga|" /opt/goga/bin/goga && \
    chown -R goga:goga /opt/goga

ENV PATH="/opt/goga/bin:/srv:${PATH}"
ENV RALPHEX_DOCKER=1

WORKDIR /workspace

USER goga

ENTRYPOINT ["goga"]
CMD ["goga"]
