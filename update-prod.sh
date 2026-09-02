#!/bin/bash
# Deprecated shim. Use scripts/update.sh (backup + health gate + auto-rollback).
exec "$(dirname "$0")/scripts/update.sh" "$@"
