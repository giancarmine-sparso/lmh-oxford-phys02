#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TALK_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${TALK_DIR}/dist"
OUTPUT_PDF="${DIST_DIR}/index.pdf"
VIDEO_SOURCE="${TALK_DIR}/assets/videos/ConstantShiftScene.mp4"
PRINT_FRAME="${TALK_DIR}/assets/figures/constant-shift-final.png"
TALK_CACHE_DIR="${TALK_DIR}/.quarto/cache"
EXPECTED_PAGES=13

for required_command in quarto ffmpeg pdfinfo; do
  if ! command -v "${required_command}" >/dev/null 2>&1; then
    echo "Missing required command: ${required_command}" >&2
    exit 1
  fi
done

CHROMIUM_BIN=""
for candidate in chromium-browser chromium google-chrome-stable google-chrome; do
  if command -v "${candidate}" >/dev/null 2>&1; then
    CHROMIUM_BIN="$(command -v "${candidate}")"
    break
  fi
done

if [[ -z "${CHROMIUM_BIN}" ]]; then
  echo "Missing Chromium or Google Chrome." >&2
  exit 1
fi

# The literal final frames fade to black. Capture the last complete teaching
# state, with both parallel tangents and the +10 shift annotation visible.
ffmpeg \
  -y \
  -v error \
  -ss 00:00:26.200 \
  -i "${VIDEO_SOURCE}" \
  -frames:v 1 \
  "${PRINT_FRAME}"

cd "${TALK_DIR}"
mkdir -p "${TALK_CACHE_DIR}"
XDG_CACHE_HOME="${TALK_CACHE_DIR}" quarto render index.qmd

"${CHROMIUM_BIN}" \
  --headless \
  --disable-gpu \
  --disable-dev-shm-usage \
  --no-sandbox \
  --run-all-compositor-stages-before-draw \
  --virtual-time-budget=10000 \
  --no-pdf-header-footer \
  --print-to-pdf="${OUTPUT_PDF}" \
  "file://${DIST_DIR}/index.html?view=print"

PAGE_COUNT="$(pdfinfo "${OUTPUT_PDF}" | awk '/^Pages:/ { print $2 }')"
if [[ "${PAGE_COUNT}" != "${EXPECTED_PAGES}" ]]; then
  echo "Expected ${EXPECTED_PAGES} pages, found ${PAGE_COUNT}: ${OUTPUT_PDF}" >&2
  exit 1
fi

echo "Created ${OUTPUT_PDF} (${PAGE_COUNT} pages)."
