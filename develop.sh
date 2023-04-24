#!/usr/bin/env bash

IMAGE="badgetracker"

docker run -it --rm \
    --expose 8080 \
    -e GOOGLE_APPLICATION_CREDENTIALS="/app/etc/service_account.json" \
    -e PORT=8080 \
    -p 8080:8080 \
    -w /app \
    -v "$(pwd):/app" \
    "${IMAGE}"