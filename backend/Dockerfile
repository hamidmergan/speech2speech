FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Not root. The data volume with the SQLite file is written as this user.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data \
    && chown -R app:app /app /data
USER app
ENV HOME=/home/app

EXPOSE 8000

# One web process. Conversations live in SQLite, which takes one writer at a time.
CMD ["python", "-m", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
