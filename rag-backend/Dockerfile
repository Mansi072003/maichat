# Use a slim Python image for a smaller footprint
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Set PYTHONPATH to include the app directory
ENV PYTHONPATH=/app

# Copy the requirements file and install dependencies
RUN mkdir -p /var/app/config
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --default-timeout=1000

# Copy the application code
COPY . .

# Expose the port the app will run on
EXPOSE 8000

# Command to run the application with Gunicorn
CMD ["gunicorn", "main:app", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]