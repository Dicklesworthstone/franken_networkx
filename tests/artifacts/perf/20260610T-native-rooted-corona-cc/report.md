# perf(rooted_product + corona_product): native fast path

br-r37-c1-oq85m

## Problem
`rooted_product` (4.1–4.8×) and `corona_product` (3.9–4.2×) built the result with
a pure-Python loop of `P.add_edge((g,h),(g2,h2))`, re-canonicalising both
product-tuple keys per edge (the tuple-key construction tax). They are the last
two products still on that path (cartesian/tensor/strong/lexicographic/modular
are already native).

## Lever (one)
Two native kernels, each canonicalising every product tuple ONCE and assembling
the edge set in Rust:
- **rooted_product_fast(g, h, root)**: result nodes are all `(g,h)` tuples
  (`product_node_tuples`). Edges = H-copy edges within each G-node + G-edges
  joining the `root`-copies (root resolved to its H index).
- **corona_product_fast(g, h)**: result mixes G's ORIGINAL nodes with `(g,h)`
  tuples, so the node table is built explicitly (G names ++ tuples). Edges = G's
  original edges + per-G-node H-copy edges + each G-node joined to all its
  H-copy nodes.
Routed from the wrappers, gated simple/no-attr/no-self-loop (H-multigraph for
corona falls back). The product parity tests compare canonicalised (sorted)
edges, so native insertion order need not match nx.

Touched: `crates/fnx-python/src/algorithms.rs` (+2 bindings),
`python/franken_networkx/__init__.py` (2 wrapper routes).

## Proof (nx-exact)
`harness_proof.py`: 30 cases — corona + rooted (×2 roots) over path×cycle,
complete×path, gnp×gnp ×4 seeds, string-labelled, no-G-edges, no-H-edges, empty.
Canonical nodes + canonical (sorted) edges **== nx, 0 mismatches**.
Golden sha256 (== nx):
`747a530227df19974cd0ff144d6ddf96f894b1765bd147eaef2e18abec81afe3`
pytest -k "rooted/corona/product": **156 passed**.

## Timing (warm interleaved min-of-4, backend disabled, path(a)×cycle(b))
| product | input | baseline fnx | nx | base ratio | new fnx | new ratio | self-speedup |
|---------|-------|-------------:|---:|-----------:|--------:|----------:|-------------:|
| rooted | 60×40 | 13.6 ms | 3.4 ms | 4.76× | 3.0 ms | **0.86×** | 4.5× |
| corona | 60×40 | 19.9 ms | 4.1 ms | 3.93× | 2.9 ms | **0.69×** | 6.9× |
| rooted | 100×60 | 31.3 ms | 7.9 ms | 4.12× | 6.4 ms | **0.81×** | 4.9× |
| corona | 100×60 | 48.4 ms | 12.7 ms | 4.19× | 9.0 ms | **0.71×** | 5.4× |

3.9–4.8× slower → 0.69–0.86× (faster than nx), 4.5–6.9× self-speedup. With this
the entire graph-product family (cartesian/tensor/strong/lexicographic/modular/
rooted/corona) is native and at-or-faster than nx.

## Score
Impact: high (4.5–6.9× self-speedup → faster than nx on the last two products).
Confidence: high (byte-identical canonical golden sha, 0/30 incl. mixed-node
corona/string/edge cases, 156 tests). Effort: moderate (2 self-contained native
kernels + bindings + wrapper routes). Score >> 2.0.
