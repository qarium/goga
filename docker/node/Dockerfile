ARG GOGA_TAG
FROM qarium/goga:${GOGA_TAG}

ARG LANG_VERSION

USER root

RUN curl -fsSL "https://deb.nodesource.com/setup_${LANG_VERSION}.x" | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

USER goga
