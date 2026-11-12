# Image for the "app" service in docker-compose.yml: Python + our two drivers.
FROM python:3.12-slim

WORKDIR /project

# Install dependencies first, in their own layer: Docker caches it, so
# rebuilding after a code change does not re-download the packages.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project in too, so the image also works without the volume mount.
COPY . .

# Default command if you run the container without one.
CMD ["python", "-m", "app.demo"]
