FROM python:3.11-slim

WORKDIR /app

# Python davranış ayarları ve Zaman Dilimi
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Istanbul

# Sistem bağımlılıkları ve zaman dilimi ayarı
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 🚀 1. CPU-Only PyTorch yükle (CUDA kütüphanelerini atlar, 3.5 GB tasarruf sağlar)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 🚀 2. Kalan bağımlılıkları yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Proje kodlarını kopyala
COPY . .

# Fix Windows CRLF (^M) line endings and make startup script executable
RUN sed -i 's/\r$//' scripts/start.sh && chmod +x scripts/start.sh

# Servis başlatma komutu (ETL Daemon + API Server)
CMD ["bash", "scripts/start.sh"]
