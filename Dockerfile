# Use a lightweight python base image
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies (e.g., build-essential, git if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Install python dependencies
# Note: we install pywebview, but it won't be used since we set GUI_MODE=server
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set environment variables
ENV GUI_MODE=server
ENV FLASK_HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

# Expose the port Flask runs on
EXPOSE 5000

# Start the Flask app
CMD ["python", "app.py"]
