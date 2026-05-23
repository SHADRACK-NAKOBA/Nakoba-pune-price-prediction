# ── Stage 1: builder ──────────────────────────────────────────────────────────
# Installs all Python deps and pre-downloads NLTK corpora.
# Nothing from this stage leaks into the final image except site-packages and
# the NLTK data directory.
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt \
 && python -c "\
import nltk; \
[nltk.download(p, download_dir='/build/nltk_data', quiet=True) \
 for p in ('punkt','punkt_tab','averaged_perceptron_tagger', \
           'averaged_perceptron_tagger_eng','stopwords')]"


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
# Minimal image — no compiler toolchain, no root process.
FROM python:3.11-slim AS runtime

# Non-root user
RUN groupadd -r app && useradd -r -g app -d /home/app app \
 && mkdir -p /home/app /app \
 && chown -R app:app /home/app /app

WORKDIR /app

# Copy installed packages from builder (avoids re-running pip at runtime)
COPY --from=builder /usr/local/lib/python3.11/site-packages \
                    /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build/nltk_data /home/app/nltk_data

# Copy application source and trained model artifacts
COPY src/   src/
COPY model/ model/

ENV NLTK_DATA=/home/app/nltk_data \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

RUN chown -R app:app /app /home/app/nltk_data
USER app

EXPOSE 8000

# Health check via the /health endpoint (gives the app 60 s to cold-start)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

CMD ["uvicorn", "src.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info"]
