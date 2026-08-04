#!/usr/bin/env python3
"""Differential oracle for the native edge-list reader: fnx vs live nx 3.6.1.

Checks the observable contract the parallel scan must not move:
node insertion order, edge insertion order, adjacency row order, edge data,
and the exact exception type/message on inputs the native path must bail on.

The parallel path only engages above 512 KiB, so every case is run at both
small size (serial chunk) and inflated size (many chunks), and the inflated
variants are padded to land chunk cuts in awkward places.
"""
from __future__ import annotations

import gzip
import os
import sys
import tempfile
import traceback

import networkx as nx

import franken_networkx as fnx

FAIL = 0
CHECKS = 0


def compare(tag, path, **kw):
    """Both engines read `path`; every observable must agree."""
    global FAIL, CHECKS
    CHECKS += 1

    def run(mod):
        try:
            g = mod.read_edgelist(path, **kw)
            return (
                "ok",
                list(g.nodes()),
                list(g.edges()),
                [sorted(map(str, g[n])) for n in g.nodes()],
                sorted((str(u), str(v), tuple(sorted(d.items()))) for u, v, d in g.edges(data=True)),
            )
        except Exception as exc:  # noqa: BLE001 - error surface is part of the contract
            return ("raise", type(exc).__name__, str(exc))

    a, b = run(fnx), run(nx)
    if a != b:
        FAIL += 1
        print(f"  MISMATCH {tag}")
        if a[0] != b[0] or a[0] == "raise":
            print(f"    fnx={a[:3]}")
            print(f"    nx ={b[:3]}")
        else:
            for i, field in enumerate(
                ["status", "nodes", "edges", "adj_rows", "edge_data"]
            ):
                if a[i] != b[i]:
                    print(f"    field {field} differs")
                    if field in ("nodes", "edges"):
                        print(f"      fnx[:6]={a[i][:6]}  len={len(a[i])}")
                        print(f"      nx [:6]={b[i][:6]}  len={len(b[i])}")
                    else:
                        for x, y in zip(a[i], b[i]):
                            if x != y:
                                print(f"      first diff fnx={x} nx={y}")
                                break
    return a == b


def write(text, suffix=".edgelist", gz=False):
    fd, path = tempfile.mkstemp(suffix=suffix + (".gz" if gz else ""))
    os.close(fd)
    data = text.encode()
    if gz:
        with gzip.open(path, "wb") as f:
            f.write(data)
    else:
        with open(path, "wb") as f:
            f.write(data)
    return path


def inflate(body_lines, target_bytes=1_500_000, pad=0):
    """Repeat a line pattern past the parallel threshold with distinct nodes.

    `pad` widens node tokens so chunk cuts land at different offsets within a
    line, exercising boundary handling.
    """
    out = []
    i = 0
    size = 0
    while size < target_bytes:
        for tmpl in body_lines:
            line = tmpl.format(a=f"n{i:0{6 + pad}d}", b=f"n{i + 1:0{6 + pad}d}")
            out.append(line)
            size += len(line) + 1
            i += 1
    return "\n".join(out) + "\n"


print("== small / structural cases (serial chunk) ==")
CASES = {
    "empty": "",
    "only_newlines": "\n\n\n",
    "only_comments": "# a\n# b\n",
    "blank_interior": "a b\n\nc d\n",
    "single_token_lines": "a b\nlonely\nc d\n",
    "no_trailing_newline": "a b\nc d",
    "crlf": "a b\r\nc d\r\n",
    "self_loop": "a a\nb b\na b\n",
    "duplicate_edges": "a b\na b\nb a\n",
    "inline_comment": "a b # note\nc d\n",
    "comment_at_col0_midfile": "a b\n# skip\nc d\n",
    "hash_touching_token": "a b#note\nc d\n",
    "leading_ws": "   a b\n\tc d\n",
    "many_spaces": "a     b\n",
    "utf8_nodes": "é ü\nü 中\n",
    "reverse_order_nodes": "z a\ny b\n",
    "numeric_tokens": "1 2\n10 3\n2 10\n",
}
for tag, body in CASES.items():
    p = write(body)
    compare(f"data=True  {tag}", p)
    compare(f"data=False {tag}", p, data=False)
    os.unlink(p)

print("== bail cases: extra columns / weights ==")
BAIL = {
    "three_tokens": "a b 3\nc d 4\n",
    "dict_data": "a b {'w': 1}\n",
    "underscore_float": "a b 1_0\n",
    "bad_float": "a b notafloat\n",
    "four_tokens": "a b 1 2\n",
}
for tag, body in BAIL.items():
    p = write(body)
    compare(f"data=True  {tag}", p)
    compare(f"data=False {tag}", p, data=False)
    os.unlink(p)

print("== weighted reader ==")
for tag, body in {
    "weights": "a b 1.5\nc d 2\n",
    "weights_dup": "a b 1.5\na b 2.5\n",
    "weights_missing_col": "a b\nc d 2.0\n",
    "weights_selfloop": "a a 3.0\n",
    "weights_exp": "a b 1e3\nc d -2.5E-2\n",
    "weights_inf": "a b inf\nc d -Infinity\n",
}.items():
    p = write(body)
    CHECKS += 1

    def run_w(mod, path=p):
        try:
            g = mod.read_weighted_edgelist(path)
            return ("ok", list(g.nodes()), sorted(
                (str(u), str(v), d.get("weight")) for u, v, d in g.edges(data=True)))
        except Exception as exc:  # noqa: BLE001
            return ("raise", type(exc).__name__, str(exc))

    if run_w(fnx) != run_w(nx):
        FAIL += 1
        print(f"  MISMATCH weighted {tag}")
        print(f"    fnx={run_w(fnx)}")
        print(f"    nx ={run_w(nx)}")
    os.unlink(p)

print("== large / PARALLEL path (>512 KiB, many chunks) ==")
for pad in (0, 1, 2, 3, 7):
    body = inflate(["{a} {b}"], pad=pad)
    p = write(body)
    compare(f"parallel plain pad={pad}", p)
    os.unlink(p)

for tag, tmpl in {
    "with_comments": ["{a} {b}", "# comment line", "{a} {b} # trailing"],
    "with_blanks": ["{a} {b}", "", "   "],
    "with_selfloops": ["{a} {a}", "{a} {b}"],
    "with_dups": ["{a} {b}", "{a} {b}"],
    "single_token": ["{a} {b}", "lonely"],
}.items():
    body = inflate(tmpl)
    p = write(body)
    compare(f"parallel {tag}", p)
    compare(f"parallel {tag} data=False", p, data=False)
    os.unlink(p)

print("== large gzipped (the analytics-pass shape) ==")
body = inflate(["{a} {b}"])
p = write(body, gz=True)
compare("parallel gzipped", p)
os.unlink(p)

print("== large bail mid-file (chunk N must bail the whole parse) ==")
for where in (0.0, 0.5, 0.99):
    lines = inflate(["{a} {b}"]).split("\n")
    idx = min(int(len(lines) * where), len(lines) - 2)
    lines[idx] = "x y 3"
    p = write("\n".join(lines))
    compare(f"parallel bail at {where:.0%}", p)
    os.unlink(p)

print("== real staged graphs ==")
for g in ["facebook_combined", "ca-CondMat", "ca-AstroPh"]:
    path = f"graphs/{g}.txt.gz"
    if os.path.exists(path):
        compare(f"real {g}", path)

print()
print(f"{CHECKS} checks, {FAIL} mismatches")
sys.exit(1 if FAIL else 0)
