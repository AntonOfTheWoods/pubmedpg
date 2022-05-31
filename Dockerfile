# syntax=docker/dockerfile:1
FROM python:3.10.4

LABEL maintainer="Anton Melser <anton@melser.org>"

WORKDIR /app/

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
  git make build-essential wget curl libgflags-dev libsnappy-dev \
  && apt-get -y clean

RUN /usr/local/bin/python -m pip install --upgrade pip

# Install Poetry
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | POETRY_HOME=/opt/poetry python && \
  cd /usr/local/bin && \
  ln -s /opt/poetry/bin/poetry && \
  poetry config virtualenvs.create false

COPY ./pyproject.toml ./poetry.lock* /app/

# Allow installing dev dependencies to run tests
ARG INSTALL_DEV=false
RUN bash -c "if [ $INSTALL_DEV == 'true' ] ; then poetry install --no-root ; else poetry install --no-root --no-dev ; fi"

RUN apt-get remove -y --purge \
  git make build-essential wget curl libgflags-dev libsnappy-dev \
  zlib1g-dev libbz2-dev liblz4-dev libzstd-dev librocksdb-dev libmagic-dev \
  && apt-get -y autoremove && apt-get -y clean \
  && rm -rf /var/lib/apt/lists/*

COPY ./src /app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
