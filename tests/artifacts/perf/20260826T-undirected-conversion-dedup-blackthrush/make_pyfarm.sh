#!/bin/bash
# Farm whose ONLY difference from its twin is python/franken_networkx/__init__.py.
# The extension module is a real copy of the SAME .so in both arms, so the
# in-process ELF sha256 is identical and the binary noise floor is zero by
# construction -- the only thing that can move a row is the Python edit.
set -euo pipefail
FARM="$1"; INIT="$2"; SO="$3"
SRC=/data/projects/franken_networkx/python/franken_networkx
rm -rf "$FARM"; mkdir -p "$FARM/franken_networkx"
for e in "$SRC"/*; do
    b="$(basename "$e")"
    [ "$b" = "_fnx.abi3.so" ] && continue
    [ "$b" = "__pycache__" ] && continue
    [ "$b" = "__init__.py" ] && continue
    ln -s "$e" "$FARM/franken_networkx/$b"
done
cp "$INIT" "$FARM/franken_networkx/__init__.py"
cp "$SO"   "$FARM/franken_networkx/_fnx.abi3.so"
