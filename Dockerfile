# Stage 0: Base
FROM python:3.14.4-slim-trixie AS base

# Set the working directory
WORKDIR /TwitchDropsMiner

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    UNLINKED_CAMPAIGNS=0 \
    PRIORITY_MODE=1 \
    TDM_DOCKER=true

# Stage 1: Build
FROM base AS build

# Create a Python virtual environment
RUN python -m venv /opt/venv

# Upgrade pip and install Python dependencies
COPY docker/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --progress-bar off -r requirements.txt

# Copy the application code and configure execution permissions
COPY . .
RUN chmod +x docker/docker_entrypoint.sh docker/healthcheck.sh

# Stage 2: Final
FROM base AS final

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        nano \
        libx11-6 \
        tk \
        xvfb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment and application code from the build stage
COPY --from=build /opt/venv /opt/venv
COPY --from=build /TwitchDropsMiner .

# Set the entrypoint and default command
ENTRYPOINT ["./docker/docker_entrypoint.sh"]
CMD ["python", "main.py", "-vvv"]

# Configure the health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=1m --retries=3 \
    CMD ["./docker/healthcheck.sh"]
