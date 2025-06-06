# Use an official Python image
FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Copy only requirements first (if you have a requirements.txt, otherwise skip)
# COPY requirements.txt ./
# RUN pip install --no-cache-dir -r requirements.txt

# Install Flask and Gunicorn (and PyQt6 if you want to support GUI in container, but not needed for web)
RUN pip install flask gunicorn

# Install OpenSSL for generating self-signed certs
RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*

# Generate self-signed certificate (valid for 10 years)
RUN mkdir -p /certs && \
    openssl req -x509 -nodes -days 3650 -newkey rsa:4096 \
    -keyout /certs/key.pem -out /certs/cert.pem \
    -subj "/C=CA/ST=Ottawa/L=Ontario/O=MyOrg/CN=localhost"

# Copy all app files (adjust as needed)
COPY . /app

# Ensure ratings.json and ratings.csv exist as files (not directories)
RUN touch /app/ratings.json && \
    if [ ! -s /app/ratings.json ]; then echo "[]" > /app/ratings.json; fi
RUN touch /app/ratings.csv && \
    if [ ! -s /app/ratings.csv ]; then echo "date,rating" > /app/ratings.csv; fi

# Expose HTTPS port
EXPOSE 7331

# Customizable volume mount points for persistent data/config/certs
VOLUME ["/app/" "/certs"]

# Start Gunicorn with SSL context
CMD ["gunicorn", "-b", "0.0.0.0:7331", "--certfile=/certs/cert.pem", "--keyfile=/certs/key.pem", "main_web:app"]

# --- Build and Run Instructions ---
# Build the image (from the directory containing this Dockerfile):
#   docker build -t rateit-app .
#
# Run the container with custom volume mappings for live file access:
# docker run -it --rm -p 7331:7331 \
#   -v ./resource:/app/resource \
#   -v ./archive:/app/archive \
#   -v ./ratings.json:/app/ratings.json \
#   -v ./ratings.csv:/app/ratings.csv \
#   rateit-app
#
# (You can copy /certs/cert.pem and /certs/key.pem from the container to your host for reuse)
#
# The web app will be available at https://localhost:7331/
# (You may need to accept the self-signed certificate in your browser)

# Docker Compose Example (optional):
# services:
#   rateit:
#     build: .
#     ports:
#       - "7331:7331"
#     volumes:
#       - ./resource:/app/resource
#       - ./archive:/app/archive
#       - ./ratings.json:/app/ratings.json
#       - ./ratings.csv:/app/ratings.csv
#       - ./certs:/certs
#     command: gunicorn -b 0.0.0.0:7331 --certfile=/certs/cert.pem --keyfile=/certs/key.pem main_web:app
# Note: Adjust the paths and filenames as needed based on your project structure.
# Note: Ensure your Flask app is set up to handle HTTPS requests properly.
# Note: This Dockerfile assumes you have a Flask app named main_web.py in the current directory.
# Note: If you have a requirements.txt, uncomment the COPY and RUN lines above to install dependencies.
