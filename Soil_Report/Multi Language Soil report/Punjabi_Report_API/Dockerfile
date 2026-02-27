FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y fonts-freefont-ttf && rm -rf /var/lib/apt/lists/*
RUN cp /usr/share/fonts/truetype/freefont/FreeSerif.ttf /app/FreeSerif.ttf

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]