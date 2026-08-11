ARG AFM_VERSION=0.5.34
ARG RALPHEX_VERSION=1.6
ARG PYTHON_VERSION=3.12
ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0

FROM python:3.12-slim-bookworm AS builder

ARG SETUPTOOLS_SCM_PRETEND_VERSION

COPY pyproject.toml /tmp/goga/
COPY goga/ /tmp/goga/goga/

RUN pip install --no-cache-dir -U /tmp/goga && \
    rm -rf /tmp/goga

FROM ghcr.io/umputun/ralphex:${RALPHEX_VERSION} AS ralphex-source

ARG RALPHEX_VERSION
RUN git clone --depth 1 --branch v${RALPHEX_VERSION}.0 https://github.com/umputun/ralphex.git /ralphex

FROM akopichin/afm:v${AFM_VERSION} AS afm-source

FROM python:${PYTHON_VERSION}-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git jq ripgrep fzf openssh-client bash make gcc g++ curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ralphex-source /srv/ralphex /srv/ralphex
COPY --from=afm-source /usr/local/bin/afm /srv/afm
RUN npm install -g @anthropic-ai/claude-code@2.1.209 @openai/codex@0.144.4 opencode-ai@1.17.13 @qwen-code/qwen-code@0.21.1
RUN curl https://cursor.com/install -fsS | bash
RUN chmod +x /srv/ralphex /srv/afm

COPY --from=builder /usr/local/lib/python3.12/site-packages /opt/goga/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/goga /opt/goga/bin/goga

RUN useradd -m -s /bin/bash goga && \
    python3 -m venv /opt/goga && \
    sed -i "s|/usr/local|/opt/goga|" /opt/goga/bin/goga && \
    chown -R goga:goga /opt/goga && \
    mkdir -p /home/goga/bin /home/goga/.codex /home/goga/pipeline && \
    chown goga:goga /home/goga/bin /home/goga/.codex /home/goga/pipeline

COPY --from=ralphex-source /ralphex/scripts/codex-as-claude/codex-as-claude.sh /home/goga/bin/codex-as-claude.sh
COPY --from=ralphex-source /ralphex/scripts/opencode/opencode-as-claude.sh /home/goga/bin/opencode-as-claude.sh
COPY scripts/claude-as-claude.sh /home/goga/bin/claude-as-claude.sh
COPY scripts/cursor-as-claude.sh /home/goga/bin/cursor-as-claude.sh
COPY scripts/qwen-as-claude.sh /home/goga/bin/qwen-as-claude.sh
RUN chmod +x /home/goga/bin/*.sh

ENV PATH="/opt/goga/bin:/srv:/home/goga/bin:${PATH}"
ENV GOGA_DOCKER=1
ENV RALPHEX_DOCKER=1
ENV AFM_IN_DOCKER=1

WORKDIR /workspace

USER goga

RUN goga connect claude codex opencode qwen cursor

ENTRYPOINT ["goga"]
CMD ["goga"]
