#!/usr/bin/env python3
"""Dump nx LRPlanarity intermediate state for the state-parity harness
(rc-planar-embedding-kernel-07rh8 milestone-1 prerequisite).

Replicates nx's `lr_planarity` body step by step WITHOUT the frees, then
dumps, per corpus graph: every oriented edge's nesting depth / ref / side,
and the post-signing ordered adjacency (ordered_adjs) per node.

Output: /tmp/lr_state_nx.json  (the Rust dumper emits the same shape)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import networkx as nx

from capture_planarity_embedding_oracle import corpus, seeded_randoms

REPO = Path(__file__).resolve().parent.parent
OUT_TXT = Path("/tmp/lr_state_nx.txt")

from networkx.algorithms.planarity import LRPlanarity  # noqa: E402


def dump_graph(name: str, nodes: list[str], edges: list[list[str]]) -> dict:
    g = nx.Graph()
    g.add_nodes_from(nodes)
    g.add_edges_from((u, v) for u, v in edges)

    lp = LRPlanarity(g)

    # lr_planarity body: adjacency lists for dfs, then orientation
    for v in lp.G:
        lp.adjs[v] = list(lp.G[v])
    for v in g:
        if lp.height[v] is None:
            lp.height[v] = 0
            lp.roots.append(v)
            lp.dfs_orientation(v)
    # nesting sort (lr_planarity body)
    for v in lp.DG:
        lp.ordered_adjs[v] = sorted(
            lp.DG[v], key=lambda x: lp.nesting_depth[(v, x)]
        )

    # testing phase
    for v in lp.roots:
        if not lp.dfs_testing(v):
            return {
                "name": name,
                "planar": False,
                "nodes": nodes,
                "build_edges": edges,
                "edges": [],
                "ordered_adjs": {},
            }

    # sign resolution pass (the embedding tail's first loop)
    for e in lp.DG.edges:
        lp.nesting_depth[e] = lp.sign(e) * lp.nesting_depth[e]

    # re-sort with SIGNED nesting (the embedding tail re-sorts again)
    for v in lp.DG:
        lp.ordered_adjs[v] = sorted(
            lp.DG[v], key=lambda x: lp.nesting_depth[(v, x)]
        )

    edge_dump = []
    for tail, head in lp.DG.edges:
        edge_dump.append(
            {
                "tail": str(tail),
                "head": str(head),
                "nesting": lp.nesting_depth[(tail, head)],
                "ref": lp.ref[(tail, head)],
                "side": lp.side[(tail, head)],
            }
        )
    edge_dump.sort(key=lambda e: (e["tail"], e["head"]))

    ordered = {
        str(v): [str(w) for w in lp.ordered_adjs[v]] for v in lp.DG
    }
    return {
        "name": name,
        "planar": True,
        "nodes": nodes,
        "build_edges": edges,
        "roots": [str(r) for r in lp.roots],
        "edges": edge_dump,
        "ordered_adjs": ordered,
    }


def main() -> int:
    corpus_all = {**corpus(), **seeded_randoms()}
    dumps = []
    lines: list[str] = []
    for name in sorted(corpus_all):
        nodes, edges = corpus_all[name]
        dumps.append(dump_graph(name, nodes, edges))

    # line-format companion for the Rust differential harness:
    #   G <name> | N <node> | B <tail> <head> (build order)
    #   E <tail> <head> <nesting> <ref(-1=none)> <side>
    #   A <node> <head> <head> ...   (ordered_adjs in order)
    for entry in dumps:
        lines.append(f"G {entry['name']} planar={str(entry['planar']).lower()}")
        for node in entry["nodes"]:
            lines.append(f"N {node}")
        for edge in entry["build_edges"]:
            lines.append(f"B {edge[0]} {edge[1]}")
        for e in entry["edges"]:
            ref = e["ref"] if e["ref"] is not None else -1
            lines.append(f"E {e['tail']} {e['head']} {e['nesting']} {ref} {e['side']}")
        for node, heads in entry["ordered_adjs"].items():
            lines.append(("A " + node + " " + " ".join(heads)).rstrip())
    out_txt = Path("/tmp/lr_state_nx.txt")
    out_txt.write_text("\n".join(lines) + "\n")
    # repo-committed copy so remote workers (rch) can read it
    repo_txt = REPO / "tests" / "artifacts" / "planarity" / "lr_state_nx.txt"
    repo_txt.parent.mkdir(parents=True, exist_ok=True)
    repo_txt.write_text("\n".join(lines) + "\n")

    # Rust data module for the in-crate differential harness
    mod_path = REPO / "crates" / "fnx-algorithms" / "src" / "lr_state_nx_dump_data.rs"
    escaped = "\n".join(
        '    "' + line.replace("\\", "\\\\").replace('"', '\\"') + '",' for line in lines
    )
    mod_path.write_text(
        "//! Captured nx LRPlanarity state for the state-parity differential\n"
        "//! harness (bead rc-planar-embedding-kernel-07rh8). Regenerate with\n"
        "//! `scripts/dump_lr_state_nx.py` (repo venv, nx 3.6.1) over the\n"
        "//! planarity_embedding_oracle corpus.\n"
        "#![cfg(test)]\n\n"
        "pub const NX_DUMP_LINES: &[&str] = &[\n" + escaped + "\n];\n"
    )
    print(f"wrote {out_txt}, {repo_txt}, {mod_path} ({len(lines)} lines)")
    out = Path("/tmp/lr_state_nx.json")
    out.write_text(json.dumps(dumps, indent=1, sort_keys=True) + "\n")
    print(f"wrote {out} ({len(dumps)} graphs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
