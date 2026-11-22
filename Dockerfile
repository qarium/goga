ARG AFM_VERSION=2.2.10
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
    git jq ripgrep fzf openssh-client bash make gcc g++ curl ca-certificates sudo \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ralphex-source /srv/ralphex /srv/ralphex
COPY --from=afm-source /usr/local/bin/afm /srv/afm
RUN npm install -g @anthropic-ai/claude-code@2.1.286 @openai/codex@0.159.3 opencode-ai@1.18.34 @qwen-code/qwen-code@0.21.1
RUN chmod +x /srv/ralphex /srv/afm

COPY --from=builder /usr/local/lib/python3.12/site-packages /opt/goga/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/goga /opt/goga/bin/goga

RUN useradd -m -s /bin/bash goga && \
    python3 -m venv /opt/goga && \
    sed -i "s|/usr/local|/opt/goga|" /opt/goga/bin/goga && \
    mkdir -p /home/goga/bin /home/goga/.codex /home/goga/pipeline /home/goga/.afm /home/goga/.local && \
    chown goga:goga /home/goga/bin /home/goga/.codex /home/goga/pipeline /home/goga/.afm /home/goga/.local

# Root-owned venv: tool installs go through `goga install --sudo` — goga may run
# only pip install/uninstall as root, HOME preserved so pip cache and downstream
# discovery stay on /home/goga.
RUN printf '%s\n' \
      'Cmnd_Alias GOGA_PIP = /opt/goga/bin/python -m pip install *, /opt/goga/bin/python3 -m pip install *, /opt/goga/bin/python3.12 -m pip install *, /usr/local/bin/python3.12 -m pip install *, /opt/goga/bin/python -m pip uninstall -y *, /opt/goga/bin/python3 -m pip uninstall -y *, /opt/goga/bin/python3.12 -m pip uninstall -y *, /usr/local/bin/python3.12 -m pip uninstall -y *' \
      'goga ALL=(root) NOPASSWD: GOGA_PIP' \
      'Defaults:goga env_keep += "HOME"' \
      > /etc/sudoers.d/goga && \
    chmod 0440 /etc/sudoers.d/goga && \
    visudo -cf /etc/sudoers.d/goga

COPY scripts/opencode-as-claude.sh /home/goga/bin/opencode-as-claude.sh
COPY scripts/claude-as-claude.sh /home/goga/bin/claude-as-claude.sh
COPY scripts/codex-as-claude.sh /home/goga/bin/codex-as-claude.sh
COPY scripts/cursor-as-claude.sh /home/goga/bin/cursor-as-claude.sh
COPY scripts/qwen-as-claude.sh /home/goga/bin/qwen-as-claude.sh
RUN chmod +x /home/goga/bin/*.sh

ENV PATH="/opt/goga/bin:/srv:/home/goga/bin:/home/goga/.local/bin:${PATH}"
ENV GOGA_DOCKER=1
ENV RALPHEX_DOCKER=1
ENV AFM_IN_DOCKER=1

USER goga

RUN curl -fsSL https://cursor.com/install -o /tmp/cursor-install.sh && \
    bash /tmp/cursor-install.sh && \
    rm -f /tmp/cursor-install.sh
RUN command -v cursor-agent

WORKDIR /workspace

RUN goga connect claude codex opencode qwen cursor

ENTRYPOINT ["goga"]
CMD ["goga"]
