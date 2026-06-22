# Use a slim Python image for a smaller footprint
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Set PYTHONPATH to include the app directory
ENV PYTHONPATH=/app

# Copy the requirements file and install dependencies
RUN mkdir -p /var/app/config
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Command to run the application
CMD ["python", "main.py"]