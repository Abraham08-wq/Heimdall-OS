#!/bin/bash
# Force the lightweight compose profile.

set -e
PROJECTXY_COMPOSE_FILE=docker-compose.lite.yml ./start_services.sh