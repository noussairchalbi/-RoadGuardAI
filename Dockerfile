# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Dependances systeme : ffmpeg (video), libgl/libglib (opencv)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Telecharge les poids des modeles depuis Hugging Face Hub pendant le build
# (necessite que REPO_ID soit correctement configure dans download_models.py)
RUN python download_models.py

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "roadsafety.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
