# perf(modular_product): native fast path

br-r37-c1-zg16r

## Problem
`modular_product` built the result with a pure-Python loop over all O((VW)²)
distinct product-node pairs, doing a per-pair `has_edge()` and two per-edge
`P.add_edge((g,h),(g2,h2))` — re-canonicalising both product-tuple keys on every
edge (the tuple-key construction tax). **3.1–3.2× slower than nx** (2.4 s at
path(40)×cycle(30)).

## Lever (one)
Native `modular_product_fast`: precompute G's and H's adjacency into flat
boolean bitmatrices, iterate distinct factor-pairs `(gl<gr, hl<hr)` in pure Rust,
and emit `(gl,hl)-(gr,hr)` + `(gl,hr)-(gr,hl)` exactly when
`G-adjacency(gl,gr) == H-adjacency(hl,hr)` (both edges, or both non-edges). Each
product node tuple is canonicalised once (`product_node_tuples`), then edges are
bulk-inserted via `extend_edges_unrecorded`. Gated to the simple, no-attr,
self-loop-free case (else the Python build); the product parity tests compare
canonicalised (sorted) edges, so insertion order need not match nx.

Touched: `crates/fnx-python/src/algorithms.rs` (+`modular_product_fast` binding),
`python/franken_networkx/__init__.py` (`modular_product` route).

## Proof (nx-exact)
`harness_proof.py`: 11 cases — path×cycle, complete×path, gnp×gnp ×4 seeds,
no-G-edges, no-H-edges, string-labelled, empty, single-node. Canonical nodes +
canonical (sorted) edges **== nx, 0 mismatches**.
Golden sha256 (== nx):
`8a49bfa1c4a239d2a6e1a86c1edb7fac5e500fc5b4746bf57a41f530f68a6ff2`
pytest -k "modular/product": **129 passed**.

## Timing (warm interleaved min-of-4, backend disabled, path(a)×cycle(b))
| input | baseline fnx | nx | base ratio | new fnx | new ratio | self-speedup |
|-------|-------------:|---:|-----------:|--------:|----------:|-------------:|
| 25×20 | 348.4 ms | 113.3 ms | 3.10× | 22.3 ms | **0.20×** | 15.6× |
| 30×25 | 886.0 ms | 276.2 ms | 3.22× | 55.0 ms | **0.20×** | 16.1× |
| 40×30 | 2430.0 ms | 764.1 ms | 3.20× | 213.1 ms | **0.28×** | 11.4× |

3.1–3.2× slower → 0.20–0.28× (**3.6–5× faster than nx**), 11.4–16.1×
self-speedup (~2.2 s saved at 40×30).

## Score
Impact: high (11.4–16.1× self-speedup → 3.6–5× faster than nx on an O((VW)²)
product; ~2.2 s saved). Confidence: high (byte-identical canonical golden sha,
0/11 incl. empty-factor/string/edge cases, 129 tests). Effort: moderate (one
self-contained native kernel + binding + wrapper route). Score >> 2.0.
