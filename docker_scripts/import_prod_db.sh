#!/bin/bash

if [ -z "$1" ]; then
    echo Usage: $0 db_dump_file.tar.gz
    exit 1
else
    DB_FILE="$1"
fi

# Load local db info from .docker-compose_db.env
# DB user and DB name need to be the same as they are in production.
source .docker-compose_db.env

# Copy the db dump file to the running database container.
docker compose cp "${DB_FILE}" db:/tmp

# Build command to run inside container.
UNTAR_COMMAND="cd /tmp && tar xf ${DB_FILE}"
# DB_FILE variable value must be passed to docker compose.
docker compose exec -e DB_FILE="${DB_FILE}" db bash -c "${UNTAR_COMMAND}"

# Build command to run inside container.
DB_DIR=`basename "${DB_FILE}" .tar.gz`
PG_COMMAND="pg_restore --verbose --if-exists --clean -U ${POSTGRES_USER} -d ${POSTGRES_DB} /tmp/${DB_DIR}"
# DB_DIR variable value must be passed to docker compose.
docker compose exec -e DB_DIR="${DB_DIR}" db bash -c "${PG_COMMAND}"
