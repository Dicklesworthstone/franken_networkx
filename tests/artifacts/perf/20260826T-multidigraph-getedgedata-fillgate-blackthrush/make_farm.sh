#!/bin/bash
# Build a shadow franken_networkx package whose ONLY difference from the repo's
# is which _fnx.abi3.so it carries.  Everything else is a symlink to the repo
# tree, so the 2.7MB Python wrapper is byte-identical across arms and the ONLY
# thing the A/B varies is the compiled extension.
#
# The .so is extracted from the wheel rather than installed: br-r37-c1 notes
# that every maturin wheel is broken at import because .gitignore's `core.*`
# pattern drops core.py from it.  Taking only the ELF sidesteps that entirely.
set -euo pipefail

FARM="$1"      # destination package parent dir
WHEEL="$2"     # wheel to take _fnx.abi3.so from
SRC=/data/projects/franken_networkx/python/franken_networkx

rm -rf "$FARM"
mkdir -p "$FARM/franken_networkx"

# Symlink every entry of the real package except the extension module.
for entry in "$SRC"/*; do
    base="$(basename "$entry")"
    [ "$base" = "_fnx.abi3.so" ] && continue
    [ "$base" = "__pycache__" ] && continue
    ln -s "$entry" "$FARM/franken_networkx/$base"
done

# Real copy of this arm's ELF.
TMP="$(mktemp -d)"
unzip -q -o "$WHEEL" -d "$TMP"
cp "$TMP/franken_networkx/_fnx.abi3.so" "$FARM/franken_networkx/_fnx.abi3.so"
rm -rf "$TMP"

echo "farm=$FARM"
sha256sum "$FARM/franken_networkx/_fnx.abi3.so"
