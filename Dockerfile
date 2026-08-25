# Use official lightweight Python image
FROM python:3.10-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to leverage Docker caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project code into the container
COPY . .

# Expose Streamlit's default port
EXPOSE 8501

# Run the Streamlit app
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]