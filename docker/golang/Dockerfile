ARG GOGA_TAG
FROM qarium/goga:${GOGA_TAG}

ARG LANG_VERSION

USER root

RUN ARCH=$(dpkg --print-architecture) && \
    curl -fsSL "https://go.dev/dl/go${LANG_VERSION}.linux-${ARCH}.tar.gz" \
    | tar -C /usr/local -xzf -

ENV GOPATH=/home/goga/go
ENV PATH="/usr/local/go/bin:${GOPATH}/bin:${PATH}"

RUN mkdir -p ${GOPATH} && chown -R goga:goga ${GOPATH}

USER goga
