#!/bin/bash

# Define the variables for file paths and reasons
health_files=(
    "/tmp/healthcheck.connectionerror"
    "/tmp/healthcheck.websocketerror"
    "/tmp/healthcheck.heartbeat"
)
reasons=("HTTP Connection Error" "Websocket Connection Error" "Heartbeat Missing")
status=0  # Default status as healthy (exit code 0)
unhealthy_reason="" # Variable to hold the reason for being unhealthy
heartbeat_time="" # Variable to store formatted heartbeat time

# Function to check the health status of each file
check_health_file() {
  local file=$1
  local reason=$2
  local content
  local max_age=180  # Maximum age in seconds for the heartbeat

  # Check if the file exists and is readable
  if [[ ! -r "$file" ]]; then
    echo "$reason: file does not exist or is not readable"
    status=1
    unhealthy_reason="$reason"  # Set the reason for unhealthiness
    return
  fi

  # Special handling for heartbeat file
  if [[ "$file" == "/tmp/healthcheck.heartbeat" ]]; then
    # Read timestamp from the heartbeat file
    timestamp=$(cat "$file")
    current_time=$(date +%s)

    # Format the heartbeat time for display
    heartbeat_time=$(date -d @$timestamp "+%Y-%m-%d %H:%M:%S")

    # Check if the heartbeat is too old
    if (( current_time - timestamp > max_age )); then
      status=1
      unhealthy_reason+="$reason (last heartbeat: $heartbeat_time), "
    fi
    return
  fi

  # For other files, check for unhealthy marker
  content=$(<"$file")
  if [[ "$content" == "Container is Unhealthy" ]]; then
    status=1  # Mark the status as unhealthy
    unhealthy_reason+="$reason, "  # Set the reason for unhealthiness
  fi
}

# Loop over each file and check its health
for i in "${!health_files[@]}"; do
  check_health_file "${health_files[$i]}" "${reasons[$i]}"
done

# Determine final health status
if [[ $status -eq 0 ]]; then
  echo "Container is healthy (last heartbeat: $heartbeat_time)"
else
  unhealthy_reason=${unhealthy_reason%, }
  echo "Container is unhealthy due to: $unhealthy_reason"
fi

exit $status
