# perf(reciprocity): integer-CSR kernel + batched binding

br-r37-c1-mzdfp

## Problem
Per-node `reciprocity(G, nodes)` was **2.15x slower than nx** (n=2500 directed:
23.3 ms vs 10.8 ms). Two layers of tax:
1. The Python wrapper looped `_reciprocity_value_for_node(G, node)` **per node** —
   each iteration made 2 raw predecessor/successor binding calls + 2 `set()`
   builds (~2N PyO3 round-trips for N nodes).
2. The native `reciprocity`/`overall_reciprocity` kernels walked
   `digraph.successors(node)` (allocating a `Vec<&str>` of names per node) and
   did a String-keyed `has_edge(succ, node)` lookup per edge.

(`overall_reciprocity` itself was already faster than nx — the gap was the
per-node path.)

## Lever (one)
**Integer-CSR + batch the binding call.** (a) Rewrote both kernels to integer
index space: an edge `(u,v)` is reciprocated iff `v ∈ pred(u)`; mark predecessor
indices in a reusable generation-stamp array and count stamped successors —
`reciprocity(u) = 2·|succ(u) ∩ pred(u)| / (|succ(u)|+|pred(u)|)`. O(E), zero
String hashing/allocation. (b) Routed the wrapper's iterable case to ONE batched
native call instead of the per-node loop. The kernel returns 0.0 for an isolated
node where nx's contract is `None`, so 0.0 is converted back to `None` only for
nodes with zero total degree (O(1) check). Gated to a plain DiGraph with no
nx-private storage; other shapes keep the proven per-node path.

Touched: `crates/fnx-algorithms/src/lib.rs` (`reciprocity`, `overall_reciprocity`),
`python/franken_networkx/__init__.py` (`reciprocity` wrapper).

## Proof (nx-exact)
`harness_proof.py`: 13 cases — gnp directed ×8 seeds, bidirectional-heavy,
self-loops, isolated nodes, string labels, empty. **0 mismatches vs nx** on both
`overall_reciprocity` (float) and per-node `reciprocity` (dict, `None`-for-isolated
normalized). Golden sha256 (== nx):
`92847e295eb886567a825c5017128dc17b506e9cfc8a2e03120787b487a2e475`
pytest -k reciprocity: **133 passed**.

## Timing (warm interleaved min-of-9, backend dispatch disabled, gnp(n,0.02,directed))
| n    | E       | per-node baseline | nx       | base ratio | per-node new | new ratio | self-speedup |
|------|---------|------------------:|---------:|-----------:|-------------:|----------:|-------------:|
| 800  |  12,773 |      2.98 ms      | 1.37 ms  |   2.15×    |   0.96 ms    | **0.70×** |    3.1×      |
| 1500 |  44,801 |      8.88 ms      | 4.13 ms  |   2.13×    |   1.71 ms    | **0.41×** |    5.2×      |
| 2500 | 124,880 |     23.30 ms      | 10.77 ms |   2.15×    |   3.93 ms    | **0.37×** |    5.9×      |

2.1× slower → 0.37–0.70× (faster than nx), 3.1–5.9× self-speedup.

## Score
Impact: high (2.1× gap → faster than nx, 3–6× self-speedup). Confidence: high
(byte-identical golden sha, 0/13 incl. self-loop/isolated/bidirectional, 133
tests). Effort: low (integer kernel + one-call wrapper batch). Score >> 2.0.
