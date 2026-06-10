# perf(strong_product + lexicographic_product): native fast path

br-r37-c1-1ix30

## Problem
`strong_product` and `lexicographic_product` built the result with a pure-Python
loop calling `P.add_edge((g,h),(g2,h2))` per edge — re-canonicalising both
product-tuple keys on every edge (the tuple-key construction tax). `cartesian` and
`tensor` already avoid this via native `_fast` kernels (2-3× faster than nx), but
strong/lexicographic had none. Result: **strong 2.95× slower; lexicographic 4.85×
slower (1.3 s)** at moderate sizes.

## Lever (one)
Generalise the native `graph_product_fast` from a `tensor: bool` to a `kind` enum
(0=cartesian, 1=tensor, 2=strong, 3=lexicographic). Each product node tuple is
canonicalised exactly ONCE; the edge set is assembled in pure Rust by integer
index and bulk-inserted via `extend_edges_unrecorded`:
- **strong** = cartesian ∪ tensor edge sets.
- **lexicographic** = each G-edge fully connects the two H-copies
  (`(gu,hu)-(gv,hv)` for all `hu,hv`) + H-edges within each G-node copy.
Add `strong_product_fast` / `lexicographic_product_fast` bindings; route the
wrappers (gated simple, matching-directedness, no-attr, self-loop-free — else the
Python path). The product parity tests compare **canonicalised (sorted)** edges,
so the native insertion order need not match nx (same as cartesian/tensor).

Touched: `crates/fnx-python/src/algorithms.rs` (graph_product_fast + 2 bindings),
`python/franken_networkx/__init__.py` (_native_graph_product + 2 wrappers).

## Proof (nx-exact)
`harness_proof.py`: 28 cases — strong/lexico/cartesian/tensor × {path×cycle,
complete×path, gnp×gnp, **directed** gnp, string-labelled, empty, single-node}.
Canonical nodes + canonical (sorted) edges with attrs **== nx, 0 mismatches**.
Golden sha256 (== nx):
`5dab41cf71c7e5d7d276e8f883ada2aa1e4c10932881bc76de328c18928703bb`
pytest -k product: **78 passed**.

## Timing (warm interleaved min-of-4, backend disabled)
| product | input | baseline fnx | nx | base ratio | new fnx | new ratio | self-speedup |
|---------|-------|-------------:|---:|-----------:|--------:|----------:|-------------:|
| strong | path(120)×cycle(100) | 217.6 ms | 62.3 ms | 2.95× | 22.6 ms | **0.36×** | 9.6× |
| lexicographic | path(80)×cycle(70) | 1327.9 ms | 277.5 ms | 4.85× | 119.5 ms | **0.43×** | 11.1× |

2.95–4.85× slower → 0.36–0.43× (**2.3–2.8× faster than nx**), 9.6–11.1×
self-speedup.

## Score
Impact: high (9.6–11.1× self-speedup → faster than nx on two product operators;
~1.2 s saved on lexicographic). Confidence: high (byte-identical canonical golden
sha, 0/28 incl. directed/string/edge cases, 78 tests). Effort: moderate (one
generalised native kernel + 2 bindings + 2 wrapper routes). Score >> 2.0.
