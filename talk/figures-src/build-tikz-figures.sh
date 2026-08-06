#!/usr/bin/env bash
# Rebuild the slide SVGs from the TikZ sources in ../notes/figures.
#
# Each wrapper here is a standalone document that \inputs the original figure
# and only remaps its colours for the dark deck, so notes and slides never
# drift apart. Text is converted to paths (--no-fonts) so the SVG renders
# identically without shipping fonts.
#
# Usage: ./build-tikz-figures.sh
set -euo pipefail

cd "$(dirname "$0")"

out="../assets/figures"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

build() {
	local wrapper="$1" target="$2"
	echo "==> $wrapper -> $out/$target"
	lualatex -interaction=nonstopmode -halt-on-error \
		-output-directory="$tmp" "$wrapper.tex" >"$tmp/$wrapper.out" 2>&1 ||
		{ tail -30 "$tmp/$wrapper.out"; exit 1; }
	dvisvgm --pdf --no-fonts --exact-bbox \
		--output="$out/$target" "$tmp/$wrapper.pdf" >/dev/null 2>&1
}

build ab-solenoid-slide ab-solenoid.svg

echo "done."
