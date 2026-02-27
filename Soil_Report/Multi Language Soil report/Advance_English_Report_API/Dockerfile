# Use a slim Python base image
FROM python:3.9-slim

# Install system dependencies for Pillow, Matplotlib, Earth Engine, etc.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libjpeg-dev \
       zlib1g-dev \
       libpng-dev \
       libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port FastAPI will run on
EXPOSE 7860

# Start the FastAPI server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]