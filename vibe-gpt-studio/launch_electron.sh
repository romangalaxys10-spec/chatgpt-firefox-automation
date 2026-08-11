#!/bin/bash
# Launch the Desktop Chat Studio as an Electron app from this folder.
# Paths are script-relative so the app runs from any clone location.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ELECTRON="$DIR/node_modules/electron/dist/electron"
if [ ! -x "$ELECTRON" ]; then
  echo "Electron binary not found at $ELECTRON" >&2
  echo "Run 'npm install' first, then retry." >&2
  exit 1
fi
"$ELECTRON" "$DIR" --no-sandbox --disable-setuid-sandbox &
