# Use a lightweight Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies for matplotlib, reportlab, and fonts
RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libpng-dev \
    libjpeg-dev \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port for FastAPI
EXPOSE 7860

# Command to run the app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]