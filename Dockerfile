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

# Python kütüphanelerini yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje kodlarını kopyala
COPY . .

# Servis başlatma komutu (Servis modunda arka planda çalışır)
CMD ["python", "run_service.py"]
