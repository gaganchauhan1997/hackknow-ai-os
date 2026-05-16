# =============================================================
# HackKnow AI OS — production container
# =============================================================
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-browsers

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ffmpeg ca-certificates build-essential \
    libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
 && python -m playwright install --with-deps chromium

COPY . /app

EXPOSE 8787

# default CMD runs the FastAPI server
CMD ["python", "-m", "server.api"]
