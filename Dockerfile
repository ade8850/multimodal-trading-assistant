FROM python:3.12-slim-bookworm

# Copy UV binary from its official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONPATH=/app

# Create virtual environment using UV
RUN uv venv $VIRTUAL_ENV

# Set working directory
WORKDIR /app

# Copy application files
ADD . /app

# Install dependencies using UV in the virtual environment
RUN uv pip install -r requirements.txt

# Run the application
CMD ["uv", "run", \
    "streamlit", "run", "app.py", \
    "--server.address", "0.0.0.0", "--server.port", "8000", \
    "--logger.level", "debug"]