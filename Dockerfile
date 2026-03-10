FROM node:22-alpine

# Install runtime dependencies in a single layer
RUN apk add --no-cache \
        python3 \
        py3-pip \
        bash \
        git \
        rsync \
        docker-cli \
    && npm install -g gitlab-ci-local \
    && rm -rf /root/.npm /tmp/*

# Install catalyst-ci-test
COPY pyproject.toml /opt/catalyst-ci-test/
COPY src/ /opt/catalyst-ci-test/src/
RUN pip install --no-cache-dir --break-system-packages /opt/catalyst-ci-test

# Tests live in the image so you can run unit tests without a mount
COPY tests/ /opt/catalyst-ci-test/tests/
COPY examples/ /opt/catalyst-ci-test/examples/

# Projects are mounted here at runtime
WORKDIR /workspace

ENTRYPOINT ["bash"]
