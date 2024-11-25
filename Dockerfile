# Use a base image with Python installed
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt .

# Install the dependencies in the container
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files into the container
COPY . .

# Set the environment variable for Python (optional for Flask apps)
ENV PYTHONUNBUFFERED=1

# Command to run the application
CMD ["python", "send-messages.py"]

FROM python:3.9-slim

RUN apt-get update && apt-get install -y libpq-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


