#!/usr/bin/env python3
"""Benchmark the onion_layers native-wrapper route for br-r37-c1-l5es6."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import time

import franken_networkx as fnx
import networkx as nx


def _digest(result):
    payload = json.dumps(list(result.items()), separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _build_graphs(n: int, m: int, seed: int):
    source = nx.barabasi_albert_graph(n, m, seed=seed)
    fg = fnx.Graph()
    fg.add_nodes_from(source.nodes())
    fg.add_edges_from(source.edges())
    return fg, source


def _call(mode: str, fg, ng):
    if mode == "nx":
        return nx.onion_layers(ng)
    saved = getattr(fnx, "_raw_onion_layers", None)
    try:
        if mode == "fallback":
            fnx._raw_onion_layers = None
        return fnx.onion_layers(fg)
    finally:
        fnx._raw_onion_layers = saved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fallback", "native", "nx"], required=True)
    parser.add_argument("--nodes", type=int, default=3000)
    parser.add_argument("--m", type=int, default=4)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args()

    fg, ng = _build_graphs(args.nodes, args.m, args.seed)
    samples = []
    result = {}
    for _ in range(args.repeat):
        start = time.perf_counter()
        result = _call(args.mode, fg, ng)
        samples.append(time.perf_counter() - start)
    nx_result = nx.onion_layers(ng)
    digest = _digest(result)
    nx_digest = _digest(nx_result)
    record = {
        "mode": args.mode,
        "nodes": args.nodes,
        "edges": fg.number_of_edges(),
        "repeat": args.repeat,
        "samples_sec": samples,
        "mean_sec": sum(samples) / len(samples),
        "digest": digest,
        "nx_digest": nx_digest,
        "digests_match": hmac.compare_digest(digest, nx_digest),
    }
    print(json.dumps(record, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
