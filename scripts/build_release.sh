#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
RELEASE_DIR="${ROOT_DIR}/release"
POSTER_BUILD_DIR="${ROOT_DIR}/poster/graphics/build"
POSTER_TEX_CACHE="${POSTER_BUILD_DIR}/texmf-var"

TALK_HTML="${ROOT_DIR}/talk/dist/index.html"
TALK_PDF="${ROOT_DIR}/talk/dist/index.pdf"
POSTER_PDF="${POSTER_BUILD_DIR}/poster.pdf"

for required_command in install latexmk lualatex pdfinfo quarto; do
  if ! command -v "${required_command}" >/dev/null 2>&1; then
    echo "Missing required command: ${required_command}" >&2
    exit 1
  fi
done

mkdir -p "${RELEASE_DIR}" "${POSTER_BUILD_DIR}" "${POSTER_TEX_CACHE}"

"${ROOT_DIR}/talk/scripts/export_pdf.sh"

(
  cd "${ROOT_DIR}/poster/graphics"
  TEXMFVAR="${POSTER_TEX_CACHE}" \
  TEXMFCACHE="${POSTER_TEX_CACHE}" \
    latexmk \
      -g \
      -lualatex \
      -interaction=nonstopmode \
      -halt-on-error \
      -outdir=build \
      poster.tex
)

for artifact in "${TALK_HTML}" "${TALK_PDF}" "${POSTER_PDF}"; do
  if [[ ! -s "${artifact}" ]]; then
    echo "Missing or empty build artifact: ${artifact}" >&2
    exit 1
  fi
done

talk_pages="$(pdfinfo "${TALK_PDF}" | awk '/^Pages:/ { print $2 }')"
poster_pages="$(pdfinfo "${POSTER_PDF}" | awk '/^Pages:/ { print $2 }')"

if [[ "${talk_pages}" != "13" ]]; then
  echo "Expected 13 talk pages, found ${talk_pages}." >&2
  exit 1
fi

if [[ "${poster_pages}" != "1" ]]; then
  echo "Expected one poster page, found ${poster_pages}." >&2
  exit 1
fi

install -m 0644 \
  "${TALK_HTML}" \
  "${RELEASE_DIR}/LMH-PHYS02-Aharonov-Bohm-talk.html"
install -m 0644 \
  "${TALK_PDF}" \
  "${RELEASE_DIR}/LMH-PHYS02-Aharonov-Bohm-talk.pdf"
install -m 0644 \
  "${POSTER_PDF}" \
  "${RELEASE_DIR}/LMH-PHYS02-Finding-the-W-in-the-Noise-poster.pdf"

echo "Release artifacts:"
find "${RELEASE_DIR}" -maxdepth 1 -type f -printf '  %f\n' | sort
