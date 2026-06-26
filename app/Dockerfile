FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей для easyocr
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 8080 7860

CMD python api.py & python gradio_app.py