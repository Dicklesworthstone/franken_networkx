# perf(weisfeiler_lehman hash): key-only adjacency snapshot

br-r37-c1-wlnak

## Problem
`weisfeiler_lehman_graph_hash` and `weisfeiler_lehman_subgraph_hashes` (de-delegated,
running nx's exact WL loop) snapshotted adjacency with
`{node: list(nbrs) for node, nbrs in G.adjacency()}`. `G.adjacency()`
materialises an attr-bearing `{nbr: attrs}` dict per node — profiled at **2.6 ms,
~36% of the 7 ms WL runtime** — but WL only needs the neighbour KEYS. Result:
**1.48–1.68× slower than nx**, growing with graph size.

## Lever (one)
Snapshot via `_native_adjacency_keys()` (key-only rows, one native pass, ~0.6 ms)
instead of `G.adjacency()`. The WL neighbour aggregate sorts the neighbour labels
(`"".join(sorted(labels[m] for m in adj[node]))`), so adjacency/row order is
irrelevant — the blake2b hashes are byte-identical. Falls back to `G.adjacency()`
if the native binding is absent. Same lever as `all_triangles`.

Touched: `python/franken_networkx/__init__.py` (both WL functions; the gated
attribute-free `type(G) is Graph` fast path). Python-only.

## Proof (nx-exact)
`harness_proof.py`: 40 cases — gnp n∈{30,80,150} × p∈{0.05,0.1,0.3} × 4 seeds,
iterations∈{1,2,5}, string labels + self-loop. **0 mismatches vs nx** on BOTH
`weisfeiler_lehman_graph_hash` (hex digest) and
`weisfeiler_lehman_subgraph_hashes` (per-node hash lists). Golden sha256 (== nx):
`6a2b5c66d8f16061c0144e4289088aa7ae37ce21cf6ca971192f471e69adbeb5`
pytest -k weisfeiler: **32 passed**.

## Timing (warm interleaved min-of-8, backend disabled, gnp)
| n    | hash baseline | nx       | base ratio | hash new | new ratio | self-speedup |
|------|--------------:|---------:|-----------:|---------:|----------:|-------------:|
| 600  |    7.30 ms    |  4.92 ms |   1.48×    |  5.12 ms |   1.04×   |    1.43×     |
| 1000 |   15.92 ms    | 10.15 ms |   1.57×    | 10.22 ms |   1.03×   |    1.56×     |
| 1500 |   26.80 ms    | 16.01 ms |   1.67×    | 16.07 ms |   1.05×   |    1.67×     |

subgraph_hashes tracks identically (1.47–1.68× → ~1.05×). 1.43–1.67× self-speedup,
both functions now at nx parity; the win grows with edge count (the eliminated
attr-materialisation is O(E)).

## Score
Impact: high (1.43–1.67× self-speedup → parity on two WL hashing functions,
growing). Confidence: very high (byte-identical golden sha, 0/40 incl.
iterations/string/self-loop, 32 tests). Effort: very low (swap one snapshot call,
Python-only). Score >> 2.0.
