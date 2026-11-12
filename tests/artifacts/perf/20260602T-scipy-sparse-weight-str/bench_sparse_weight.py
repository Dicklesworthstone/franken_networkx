from __future__ import annotations

import argparse
import hashlib
import json
import time

import numpy as np


def csr_digest(matrix) -> str:
    csr = matrix.tocsr()
    csr.sort_indices()
    h = hashlib.sha256()
    h.update(str(csr.shape).encode())
    h.update(csr.dtype.str.encode())
    h.update(csr.indptr.tobytes())
    h.update(csr.indices.tobytes())
    h.update(np.ascontiguousarray(csr.data).tobytes())
    return h.hexdigest()


def build_graphs(n: int, deg: int):
    import franken_networkx as fnx
    import networkx as nx

    nx_graph = nx.barabasi_albert_graph(n, deg, seed=1)
    fnx_graph = fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph.nodes())
    fnx_graph.add_edges_from(nx_graph.edges())
    return nx_graph, fnx_graph


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["nx", "old", "native", "golden"], required=True)
    parser.add_argument("--n", type=int, default=8000)
    parser.add_argument("--deg", type=int, default=4)
    parser.add_argument("--iters", type=int, default=8)
    args = parser.parse_args()

    import franken_networkx as fnx
    import networkx as nx

    nx_graph, fnx_graph = build_graphs(args.n, args.deg)
    if args.mode == "old":
        fnx._native_adjacency_arrays = None

    graph = nx_graph if args.mode == "nx" else fnx_graph
    module = nx if args.mode == "nx" else fnx
    digests = []

    started = time.perf_counter()
    for _ in range(args.iters):
        matrix = module.to_scipy_sparse_array(graph, dtype=float, weight="weight")
        digests.append(csr_digest(matrix))
    elapsed = time.perf_counter() - started

    output = {
        "mode": args.mode,
        "n": args.n,
        "deg": args.deg,
        "iters": args.iters,
        "elapsed_sec": elapsed,
        "digest": digests[-1],
        "all_digests_equal": len(set(digests)) == 1,
    }
    if args.mode == "golden":
        old_native = fnx._native_adjacency_arrays
        fnx._native_adjacency_arrays = None
        old_digest = csr_digest(fnx.to_scipy_sparse_array(fnx_graph, dtype=float, weight="weight"))
        fnx._native_adjacency_arrays = old_native
        native_digest = csr_digest(
            fnx.to_scipy_sparse_array(fnx_graph, dtype=float, weight="weight")
        )
        nx_digest = csr_digest(nx.to_scipy_sparse_array(nx_graph, dtype=float, weight="weight"))
        output.update(
            {
                "old_digest": old_digest,
                "native_digest": native_digest,
                "nx_digest": nx_digest,
                "all_paths_equal": old_digest == native_digest == nx_digest,
            }
        )
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
