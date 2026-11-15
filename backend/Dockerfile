FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/app/.cache/huggingface

# PyTorch CPU inference uses OpenMP. Install its runtime library without a
# compiler toolchain; psycopg[binary] and the other Python packages use wheels.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin app \
    && mkdir -p "$HF_HOME" \
    && chown -R app:app /home/app/.cache

WORKDIR /app

COPY agentops_requirements.txt ./agentops_requirements.txt

# Install the CPU wheel first so sentence-transformers does not pull a CUDA
# runtime into this CPU-only service image. The project manifest installs the
# remaining application dependencies and accepts this torch version.
RUN python -m pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        "torch==2.15.0+cpu" \
    && python -m pip install --no-cache-dir -r agentops_requirements.txt

COPY backend/ ./backend/

USER app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
