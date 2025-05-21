ARG IMAGE="python:3.12-slim"

FROM ${IMAGE}

RUN --mount=type=bind,source=dist,target=/dist \
    pip3 install $(find /dist -name '*.whl' -print -quit)