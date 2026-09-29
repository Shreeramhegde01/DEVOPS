# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install Flask
RUN pip install --no-cache-dir flask==3.0.3

# Copy the application into the container at /app
COPY app.py /app/

# Expose port 5000
EXPOSE 5000

# Run app.py when the container launches (exec form - no shell is needed, so the profile can deny shells)
CMD ["python", "app.py"]
