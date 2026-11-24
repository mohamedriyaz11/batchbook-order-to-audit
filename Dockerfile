FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py domain.py reports.py seed.py schema.sql ./
COPY web ./web
ENV BATCHBOOK_DB=/app/data/batchbook.sqlite3
EXPOSE 8000
CMD ["python", "app.py", "--host", "0.0.0.0"]
