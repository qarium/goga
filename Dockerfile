FROM ghcr.io/umputun/ralphex:latest

ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0

# install goga from local source into venv
COPY pyproject.toml /tmp/goga/
COPY goga/ /tmp/goga/goga/
RUN apk add --no-cache python3-dev gcc musl-dev && \
    python3 -m venv /opt/goga && \
    /opt/goga/bin/pip install --no-cache-dir /tmp/goga && \
    rm -rf /tmp/goga && \
    apk del python3-dev gcc musl-dev && \
    chown -R app:app /opt/goga

# add venv and ralphex binary to PATH
ENV PATH="/opt/goga/bin:/srv:${PATH}"

USER app

ENTRYPOINT ["goga"]
CMD ["goga"]
