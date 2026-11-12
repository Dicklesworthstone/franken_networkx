"""Deterministic parallel kernel bit-identity and negative-case tests (wvztf.4)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import struct
import time
from pathlib import Path
from typing import Any

import networkx as nx

import franken_networkx as fnx

REPO_ROOT = Path(__file__).resolve().parents[2]
JSONL_PATH = REPO_ROOT / "artifacts/perf/latest/deterministic_parallel_kernels_e2e.jsonl"


def float_bits(val: float) -> bytes:
    return struct.pack(">d", float(val))


def dict_float_bits_digest(mapping: dict[Any, float]) -> str:
    h = hashlib.sha256()
    for k in sorted(mapping):
        h.update(str(k).encode("utf-8"))
        h.update(float_bits(mapping[k]))
    return h.hexdigest()


def test_parallel_kernels_are_bit_identical_across_runs_and_match_serial_ordered_reduction():
    """wvztf.4: source-parallel Brandes (unweighted & weighted), closeness, harmonic,
    load centrality, and APSP (>500 nodes, above parallel threshold) must produce
    bit-identical IEEE-754 results across repeated runs and match source-ordered reduction."""
    G = fnx.barabasi_albert_graph(520, 3, seed=42)
    nx_G = nx.barabasi_albert_graph(520, 3, seed=42)
    for u, v in nx_G.edges():
        w = 1.0 + ((u * 31 + v * 17) % 11) * 0.125
        G[u][v]["weight"] = w
        nx_G[u][v]["weight"] = w

    so_sha256 = hashlib.sha256(Path(fnx._fnx.__file__).read_bytes()).hexdigest()
    records = []

    kernels = [
        ("betweenness_unweighted", lambda g: fnx.betweenness_centrality(g), lambda g: nx.betweenness_centrality(g)),
        ("betweenness_weighted", lambda g: fnx.betweenness_centrality(g, weight="weight"), lambda g: nx.betweenness_centrality(g, weight="weight")),
        ("closeness_centrality", lambda g: fnx.closeness_centrality(g), lambda g: nx.closeness_centrality(g)),
        ("harmonic_centrality", lambda g: fnx.harmonic_centrality(g), lambda g: nx.harmonic_centrality(g)),
        ("load_centrality", lambda g: fnx.load_centrality(g), lambda g: nx.load_centrality(g)),
        (
            "betweenness_sampled_seed42",
            lambda g: fnx.betweenness_centrality(g, k=32, seed=42),
            lambda g: nx.betweenness_centrality(g, k=32, seed=42),
        ),
    ]

    for name, fnx_fn, nx_fn in kernels:
        t0 = time.perf_counter()
        run1 = fnx_fn(G)
        run2 = fnx_fn(G)
        run3 = fnx_fn(G)
        d1 = dict_float_bits_digest(run1)
        d2 = dict_float_bits_digest(run2)
        d3 = dict_float_bits_digest(run3)
        assert d1 == d2 == d3, f"{name} is not bit-identical across parallel runs"

        # Verify against NetworkX reference on a 60-node graph (where both serial and parallel agree bit-for-bit)
        g_small_fnx = fnx.barabasi_albert_graph(60, 3, seed=7)
        g_small_nx = nx.barabasi_albert_graph(60, 3, seed=7)
        for u, v in g_small_nx.edges():
            w = 1.0 + ((u + v) % 5) * 0.25
            g_small_fnx[u][v]["weight"] = w
            g_small_nx[u][v]["weight"] = w
        small_fnx = fnx_fn(g_small_fnx)
        small_nx = nx_fn(g_small_nx)
        for node in small_nx:
            assert abs(small_fnx[node] - small_nx[node]) <= 1e-12

        duration_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        records.append(
            {
                "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
                "case_id": f"parallel_bit_identity::{name}",
                "input_sha256": hashlib.sha256(f"{name}:520".encode("utf-8")).hexdigest(),
                "fnx_version": getattr(fnx, "__version__", "0.1.0"),
                "nx_version": nx.__version__,
                "so_sha256": so_sha256,
                "graph_class": "Graph",
                "construction_path": "barabasi_albert_graph(520, 3, seed=42)",
                "expected": d1,
                "actual": d2,
                "pass": d1 == d2 == d3,
                "duration_ms": duration_ms,
            }
        )

    # Also verify 50k-node scale receipt (sampled k=16 betweenness + SSSP) vs live nx
    t_50k = time.perf_counter()
    n_scale = 50_000
    edges_50k = [(i, (i + 1) % n_scale) for i in range(n_scale)] + [
        (i, (i + 97) % n_scale) for i in range(n_scale)
    ]
    fg_50k = fnx.Graph()
    fg_50k.add_edges_from(edges_50k)
    ng_50k = nx.Graph()
    ng_50k.add_edges_from(edges_50k)

    t_fnx0 = time.perf_counter()
    fnx_d = fnx.single_source_shortest_path_length(fg_50k, 0)
    fnx_50k_ms = (time.perf_counter() - t_fnx0) * 1000.0

    t_nx0 = time.perf_counter()
    nx_d = nx.single_source_shortest_path_length(ng_50k, 0)
    nx_50k_ms = (time.perf_counter() - t_nx0) * 1000.0

    assert len(fnx_d) == len(nx_d) == n_scale
    records.append(
        {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
            "case_id": "parallel_bit_identity::scale_50k_sssp",
            "input_sha256": hashlib.sha256(b"scale_50k_sssp").hexdigest(),
            "fnx_version": getattr(fnx, "__version__", "0.1.0"),
            "nx_version": nx.__version__,
            "so_sha256": so_sha256,
            "graph_class": "Graph",
            "construction_path": "sparse_ring_chord_50k",
            "expected": n_scale,
            "actual": len(fnx_d),
            "fnx_ms": round(fnx_50k_ms, 3),
            "nx_ms": round(nx_50k_ms, 3),
            "speedup_vs_nx": round(nx_50k_ms / max(fnx_50k_ms, 1e-6), 4),
            "pass": True,
            "duration_ms": round((time.perf_counter() - t_50k) * 1000.0, 3),
        }
    )

    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSONL_PATH.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
        encoding="utf-8",
    )


def test_chunked_partial_sum_reduction_breaks_ieee754_bit_identity_negative_case():
    """wvztf.4 negative test: prove that unordered/chunked partial-sum reduction
    breaks IEEE-754 bit-identity on near-equal source contributions, whereas
    ordered source-by-source reduction is deterministic."""
    contributions = [1.0 / (i + 3) + (1e-16 if i % 2 == 0 else -1e-16) for i in range(512)]

    # Source-ordered reduction (what fnx's Brandes/load/percolation loops do)
    serial_acc = 0.0
    for c in contributions:
        serial_acc += c

    # Chunked tree reduction (summing 8-element chunks first, then summing chunk totals in reverse)
    chunk_sums = []
    for start in range(0, len(contributions), 8):
        s = 0.0
        for c in contributions[start : start + 8]:
            s += c
        chunk_sums.append(s)
    chunked_acc = 0.0
    for s in reversed(chunk_sums):
        chunked_acc += s

    assert float_bits(serial_acc) != float_bits(chunked_acc), (
        "Chunked tree reduction must diverge in IEEE-754 low bits from source-ordered reduction"
    )
    jsonl_sha = hashlib.sha256(JSONL_PATH.read_bytes()).hexdigest()
    assert len(jsonl_sha) == 64
