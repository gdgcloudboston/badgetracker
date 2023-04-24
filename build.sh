#!/usr/bin/env bash

IMAGE="badgetracker"

docker build --progress=plain . -t "${IMAGE}"
