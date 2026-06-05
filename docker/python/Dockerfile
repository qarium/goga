ARG GOGA_TAG
FROM qarium/goga:${GOGA_TAG}

ARG LANG_VERSION

USER root

RUN if [ "$LANG_VERSION" != "3.12" ]; then \
      curl -LsSf https://astral.sh/uv/install.sh | sh && \
      /root/.local/bin/uv python install ${LANG_VERSION} && \
      UV_BIN=$(find /root/.local/share/uv/python -name "python${LANG_VERSION}" -type f -printf '%h\n' | head -1) && \
      echo "PATH=${UV_BIN}:\${PATH}" >> /etc/bash.bashrc && \
      ln -sf "${UV_BIN}/python${LANG_VERSION}" /usr/local/bin/python${LANG_VERSION} && \
      ln -sf "${UV_BIN}/pip${LANG_VERSION}" /usr/local/bin/pip${LANG_VERSION} 2>/dev/null || true; \
    fi

USER goga
