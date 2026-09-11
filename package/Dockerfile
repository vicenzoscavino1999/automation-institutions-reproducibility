# syntax=docker/dockerfile:1
FROM --platform=linux/amd64 python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOOK_REPRO_ROOT=/opt/book-repro \
    BOOK_REPRO_CONTAINER=1 \
    BOOK_REPRO_BASE_DIGEST=sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
WORKDIR /opt/book-repro

FROM python-base AS runtime
ENV BOOK_REPRO_IMAGE_ROLE=runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends time \
    && rm -rf /var/lib/apt/lists/*
COPY locks/requirements-linux-amd64.txt /opt/book-repro/locks/requirements-linux-amd64.txt
COPY vendor/wheels-linux-amd64 /opt/book-repro/vendor/wheels-linux-amd64
RUN python -m pip install --no-index --find-links /opt/book-repro/vendor/wheels-linux-amd64 \
        --require-hashes -r /opt/book-repro/locks/requirements-linux-amd64.txt
COPY . /opt/book-repro
RUN python -m pip install --no-index --no-build-isolation --no-deps --editable /opt/book-repro
CMD ["python", "-m", "book_repro", "check-env"]

FROM runtime AS docs
ENV BOOK_REPRO_IMAGE_ROLE=docs
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        latexmk \
        lmodern \
        poppler-utils \
        texlive-fonts-recommended \
        texlive-latex-base \
        texlive-latex-extra \
        texlive-latex-recommended \
    && rm -rf /var/lib/apt/lists/*
CMD ["python", "-m", "book_repro", "check-env"]
