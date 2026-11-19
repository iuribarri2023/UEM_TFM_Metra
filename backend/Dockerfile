FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
RUN useradd -r -u 10001 market && mkdir -p /data/assets && chown -R 10001:10001 /data/assets
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER 10001
EXPOSE 8000
CMD ["gunicorn","-w","1","--threads","4","--access-logfile","-","--error-logfile","-","-b","0.0.0.0:8000","--timeout","120","wsgi:app"]
