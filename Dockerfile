# Stage 1: Build
FROM python:3.14.2-slim-trixie AS build

# Install system dependencies and build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgirepository1.0-dev \
    python3-gi \
    gobject-introspection \
    gir1.2-gtk-3.0 \
    gir1.2-ayatanaappindicator3-0.1 \
    libcairo2-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /TwitchDropsMiner/

# Copy only the files needed for pip install first to leverage Docker's cache
COPY requirements.txt ./

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --progress-bar off -r requirements.txt

# Copy the rest of the application code
COPY . .

# Make the entrypoint script and healthcheck script executable
RUN chmod +x ./docker_entrypoint.sh && \
    chmod +x ./healthcheck.sh

# Stage 2: Final
FROM python:3.14.2-slim-trixie

# Set the working directory
WORKDIR /TwitchDropsMiner/

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    nano \
    libx11-6 \
    tk \
    xvfb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the application and dependencies from the build stage
COPY --from=build /TwitchDropsMiner /TwitchDropsMiner

# Copy only the necessary files to the final image
COPY --from=build /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

# Environment variables
ENV UNLINKED_CAMPAIGNS=0
ENV PRIORITY_MODE=1
ENV TDM_DOCKER=true

# Set the entrypoint and default command
ENTRYPOINT ["./docker_entrypoint.sh"]

# Healthcheck
HEALTHCHECK --interval=10s --timeout=5s --start-period=1m --retries=3 CMD ["./healthcheck.sh"]

# Default command
CMD ["sh", "-c", "python main.py -vvv"]
