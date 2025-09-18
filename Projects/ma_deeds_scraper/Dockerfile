FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/
CMD ["python", "scraper.py"]
