FROM python:3.12-slim-bookworm AS builder

ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0

# install goga from local source into venv
COPY pyproject.toml /tmp/goga/
COPY goga/ /tmp/goga/goga/

RUN pip install --no-cache-dir /tmp/goga && \
    rm -rf /tmp/goga

FROM ghcr.io/umputun/ralphex:latest

RUN apk add --no-cache gcompat

COPY --from=builder /usr/local/lib/python3.12/site-packages /opt/goga/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/goga /opt/goga/bin/goga

RUN python3 -m venv /opt/goga && \
    sed -i "s|/usr/local/bin/python3.12|/usr/bin/python3.12|" /opt/goga/pyvenv.cfg && \
    sed -i "s|/usr/local|/opt/goga|" /opt/goga/bin/goga && \
    chown -R app:app /opt/goga

# add venv and ralphex binary to PATH
ENV PATH="/opt/goga/bin:/srv:${PATH}"

USER app

ENTRYPOINT ["goga"]
CMD ["goga"]
