FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

EXPOSE 8000

# Demo-only: run the worker alongside the API in one Render Web Service.
# Render injects PORT; the API must bind to it. The worker is restarted when
# the whole service restarts and will stop whenever the free service sleeps.
CMD ["sh", "-c", "python -m app.worker --mode all & exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
