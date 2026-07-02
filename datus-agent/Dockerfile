FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/datus-agent \
    HF_ENDPOINT=https://hf-mirror.com \
    HF_HUB_ENABLE_HF_TRANSFER=0 \
    HF_HUB_DOWNLOAD_TIMEOUT=120 \
    FASTEMBED_CACHE_PATH=/root/.cache/huggingface/fastembed

WORKDIR /app

RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g; s|http://security.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list; \
    fi; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g; s|http://security.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
    fi

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        default-libmysqlclient-dev \
        gcc \
        git \
        libgomp1 \
        libsqlite3-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple

COPY datus-agent/docker-constraints.txt ./docker-constraints.txt
COPY datus-agent/docker-requirements.txt ./docker-requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -c ./docker-constraints.txt -r ./docker-requirements.txt

COPY datus-db-adapters/datus-db-core ./datus-db-adapters/datus-db-core
COPY datus-db-adapters/datus-sqlalchemy ./datus-db-adapters/datus-sqlalchemy
COPY datus-db-adapters/datus-postgresql ./datus-db-adapters/datus-postgresql
COPY datus-db-adapters/datus-mysql ./datus-db-adapters/datus-mysql
COPY datus-db-adapters/datus-starrocks ./datus-db-adapters/datus-starrocks
COPY datus-storage-adapters/datus-storage-base ./datus-storage-adapters/datus-storage-base
COPY datus-storage-adapters/datus-storage-postgresql ./datus-storage-adapters/datus-storage-postgresql

RUN python -m pip install -c ./docker-constraints.txt \
        ./datus-db-adapters/datus-db-core \
        ./datus-db-adapters/datus-sqlalchemy \
        ./datus-db-adapters/datus-postgresql \
        ./datus-db-adapters/datus-mysql \
        ./datus-db-adapters/datus-starrocks \
        ./datus-storage-adapters/datus-storage-base \
        ./datus-storage-adapters/datus-storage-postgresql

COPY datus-agent ./datus-agent

WORKDIR /app/datus-agent

EXPOSE 8000 8010

CMD ["python", "-m", "datus.api.main", "--config", "conf/agent.compose.yml", "--datasource", "ccks_fund", "--host", "0.0.0.0", "--port", "8000"]
