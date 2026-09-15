# 1. Use an official lightweight Python base image matching the local environment
FROM python:3.11-slim

# 2. Prevent Python from writing .pyc files and enable unbuffered logging to see print statements in Cloud logs immediately
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the application code
COPY . .

# 6. Expose the default port Cloud Run expects (8080)
ENV PORT=8080
EXPOSE 8080

# 7. Start the FastAPI server using Uvicorn
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
