#!/bin/sh
# MemoryVault container entrypoint.
#
# Environment:
#   MEMORYVAULT_DATA   directory holding the SQLite vault   (default /data)
#   MEMORYVAULT_DOCS   directory indexed into the vault     (default /docs)
#   MEMORYVAULT_API_HOST / MEMORYVAULT_API_PORT             bind address

set -e

DATA_DIR="${MEMORYVAULT_DATA:-/data}"
DOCS_DIR="${MEMORYVAULT_DOCS:-/docs}"
export MEMORYVAULT_HOME="$DATA_DIR"

mkdir -p "$DATA_DIR"

DB="$DATA_DIR/memoryvault.db"

case "$1" in
    serve)
        # Index the mounted documents once at startup, then serve the API
        # with the bundled dashboard. All state stays in $DATA_DIR.
        memoryvault --db "$DB" index "$DOCS_DIR" || true
        exec memoryvault --db "$DB" serve
        ;;
    index|search|stats|watch|graph|timeline|duplicates|tags|show|scan)
        exec memoryvault --db "$DB" "$@"
        ;;
    *)
        exec "$@"
        ;;
esac
