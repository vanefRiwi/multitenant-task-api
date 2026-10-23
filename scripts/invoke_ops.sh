#!/usr/bin/env bash
# Invoca la Lambda de operaciones y falla si la función lanzó un error.
#   scripts/invoke_ops.sh <nombre-funcion> '{"action": "bootstrap"}'
set -euo pipefail

FUNCTION_NAME="$1"
PAYLOAD="$2"
OUT="$(mktemp)"

META="$(aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --cli-binary-format raw-in-base64-out \
  --cli-read-timeout 310 \
  --payload "$PAYLOAD" \
  "$OUT")"

cat "$OUT"; echo
if echo "$META" | grep -q '"FunctionError"'; then
  echo "La operación $PAYLOAD falló. Revisa CloudWatch Logs de $FUNCTION_NAME." >&2
  exit 1
fi
