# ─── Base image ───────────────────────────────────────────────────────────────
# Python 3.11 slim — small footprint, fast build
FROM python:3.11-slim

# ─── System deps ──────────────────────────────────────────────────────────────
# libglib2.0-0 and libgomp1 are needed by numpy/scipy/matplotlib on slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxrender1 \
        libxext6 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# ─── Working directory ────────────────────────────────────────────────────────
WORKDIR /app

# ─── Python deps (cached layer unless requirements change) ────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ─── App source ───────────────────────────────────────────────────────────────
RUN mkdir -p /app/static
COPY . .

# ─── Matplotlib font cache pre-build (avoids runtime warnings) ────────────────
RUN python -c "import matplotlib.font_manager"

# ─── Hugging Face Spaces: run as non-root user ────────────────────────────────
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

# ─── Port & entrypoint ────────────────────────────────────────────────────────
# HF Spaces expects the app on port 7860
EXPOSE 7860

ENV PORT=7860 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLCONFIGDIR=/tmp/matplotlib

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]