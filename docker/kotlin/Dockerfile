ARG GOGA_TAG
FROM qarium/goga:${GOGA_TAG}

ARG LANG_VERSION

USER root

RUN ARCH=$(dpkg --print-architecture) && \
    JDK_ARCH=$(case "${ARCH}" in \
      "amd64") echo "x64" ;; \
      "arm64") echo "aarch64" ;; \
    esac) && \
    apt-get update && \
    apt-get install -y --no-install-recommends unzip && \
    rm -rf /var/lib/apt/lists/* && \
    curl -fsSL "https://api.adoptium.net/v3/binary/latest/21/ga/linux/${JDK_ARCH}/jdk/hotspot/normal/eclipse" \
    | tar -xz -C /opt && \
    ln -sf /opt/jdk-21* /opt/jdk-21

ENV JAVA_HOME=/opt/jdk-21
ENV PATH="/opt/jdk-21/bin:${PATH}"

RUN curl -fsSL "https://github.com/JetBrains/kotlin/releases/download/v${LANG_VERSION}/kotlin-compiler-${LANG_VERSION}.zip" \
    -o /tmp/kotlin.zip && \
    unzip /tmp/kotlin.zip -d /opt && \
    rm /tmp/kotlin.zip

ENV PATH="/opt/kotlinc/bin:${PATH}"

USER goga
