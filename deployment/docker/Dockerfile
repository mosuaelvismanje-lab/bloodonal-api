# deployment/docker/Dockerfile

FROM python:3.11-slim

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy app source
COPY app ./app

# Expose FastAPI on port 8080
EXPOSE 8080

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
