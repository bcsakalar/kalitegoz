FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Mono kayitlarda pyannote diarization istenirse:
#   docker compose build --build-arg WITH_DIARIZATION=1
ARG WITH_DIARIZATION=0
COPY requirements-diarization.txt ./
RUN if [ "$WITH_DIARIZATION" = "1" ]; then pip install --no-cache-dir -r requirements-diarization.txt; fi

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/models

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
