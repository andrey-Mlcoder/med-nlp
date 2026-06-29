FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 8080 7860

CMD python api.py & python gradio_app.py