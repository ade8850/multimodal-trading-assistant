# scheduler.Dockerfile

FROM python:3.12-slim-bookworm

# Copy UV binary from its official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install system dependencies required by Kaleido
RUN apt-get update && apt-get install -y \
    libexpat1 \
    libglib2.0-0 \
    libnss3 \
    libfontconfig1 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONPATH=/app

# Create virtual environment using UV
RUN uv venv $VIRTUAL_ENV

# Create app directory
WORKDIR /app

# Copy application files
COPY . /app

# Install dependencies using UV
RUN uv pip install -r requirements.txt

# Default configuration file location
ENV CONFIG_PATH=/app/config.yaml

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import pathlib; assert pathlib.Path('/app/scheduler.log').exists()"

# Run the scheduler
CMD ["python", "-u", "scheduler.py"]