# backend/Dockerfile
FROM python:3.12-slim

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# create app user
ENV APP_HOME=/app
RUN mkdir -p $APP_HOME
WORKDIR $APP_HOME

# copy requirements and install
COPY ./requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . .

# create logs directory and ensure permissions
RUN mkdir -p /app/log && chown -R root:root /app

# environment defaults (override at runtime with docker-compose or env)
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
EXPOSE 8000

# run uvicorn (use --host 0.0.0.0 so container is reachable)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
