ARG GOGA_TAG
FROM qarium/goga:${GOGA_TAG}

ARG LANG_VERSION

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      binutils git gnupg2 libc6-dev libcurl4-openssl-dev libedit2 \
      libgcc-11-dev libncurses-dev libpython3-dev libsqlite3-0 libstdc++-11-dev \
      libxml2-dev libz3-dev pkg-config tzdata uuid-dev && \
    rm -rf /var/lib/apt/lists/*

RUN SWIFT_ARCH=$(dpkg --print-architecture) && \
    case "${SWIFT_ARCH}" in \
      "amd64") SWIFT_DIR="ubuntu2204"; SWIFT_FILE="ubuntu22.04" ;; \
      "arm64") SWIFT_DIR="ubuntu2204-aarch64"; SWIFT_FILE="ubuntu22.04-aarch64" ;; \
    esac && \
    curl -fsSL "https://download.swift.org/swift-${LANG_VERSION}-release/${SWIFT_DIR}/swift-${LANG_VERSION}-RELEASE/swift-${LANG_VERSION}-RELEASE-${SWIFT_FILE}.tar.gz" \
    | tar -C /opt -xzf - && \
    SWIFT_BIN="/opt/swift-${LANG_VERSION}-RELEASE-${SWIFT_FILE}/usr/bin" && \
    for bin in "${SWIFT_BIN}"/*; do ln -s "${bin}" /usr/local/bin/; done || \
    (echo "Swift ${LANG_VERSION} may not be available for ${SWIFT_ARCH}" && exit 1)

USER goga