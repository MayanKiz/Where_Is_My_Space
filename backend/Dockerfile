FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System libs used by OpenCV video decoding / ffmpeg backends.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# Default: run the API. The worker is launched as a separate Railway service
# using the same image with command: python -m app.worker --mode all
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
