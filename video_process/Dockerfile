FROM python:3.10-slim-bookworm

# Docker内でのネットワーク安定性のための設定
ENV DEBIAN_FRONTEND=noninteractive

# リポジトリの署名エラーや通信タイムアウトへの徹底抗戦設定
RUN echo 'Acquire::Retries "20";' > /etc/apt/apt.conf.d/80-retries && \
    echo 'Acquire::http::Timeout "300";' >> /etc/apt/apt.conf.d/80-retries && \
    echo 'Acquire::AllowInsecureRepositories "true";' >> /etc/apt/apt.conf.d/80-retries && \
    echo 'Acquire::AllowDowngradeToInsecureRepositories "true";' >> /etc/apt/apt.conf.d/80-retries && \
    echo 'APT::Get::AllowUnauthenticated "true";' >> /etc/apt/apt.conf.d/80-retries

# インストール実行
# --allow-unauthenticated を付与して署名エラーによる停止を回避
RUN apt-get update --allow-insecure-repositories && \
    apt-get install -y --no-install-recommends --allow-unauthenticated \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pythonパッケージのインストール
RUN pip install --no-cache-dir --default-timeout=100 \
    mediapipe \
    opencv-python-headless \
    numpy \
    tqdm

# スクリプトをコピー
COPY . /app

# 最終的な動画は host の root に書き出す
CMD ["python", "main.py"]
