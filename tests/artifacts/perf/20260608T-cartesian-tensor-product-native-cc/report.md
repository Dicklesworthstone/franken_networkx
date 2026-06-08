# cartesian_product / tensor_product: native fast path (br-r37-c1-prodnative)

## Problem
`cartesian_product` (4.13x slower) and `tensor_product` (3.65x slower) built the
product in pure Python: `P.add_node((g,h))` + `P.add_edge((u,h),(v,h))` one PyO3
call at a time. Each edge re-canonicalizes both tuple endpoints `(g,h)` to the
fnx string key — ~1.8us/edge — so ~48k tuple→string conversions for a 60x60
product dominated (profiled: 44ms of 54ms in add_edges_from).

## Lever (ONE)
Native fast path `cartesian_product_fast` / `tensor_product_fast`: canonicalize
each product tuple node EXACTLY ONCE (node_key_to_string, int-tuple path is Rust),
then assemble all product edges in pure Rust by integer index over the factors'
CSR adjacency (neighbors_indices/successors_indices) and bulk-insert via
extend_nodes/edges_unrecorded. Result PyGraph built zero-copy (inner = native
result, node_key_map = canon→tuple, lazy edge attrs). Wrapper gates to the case
the kernel reproduces exactly: simple (non-multi), matching directedness, no
node/edge attrs to pair, no self-loops — every other shape falls back to the
Python construction.

## Proof (behavior parity — absolute)
- 120 products (cartesian+tensor; directed/undirected x attrs/self-loops/
  multigraph mix — fallback paths included): 0 mismatches across
  class/nodes/edge-set/node-attrs/edge-attrs.
- Golden: simple int-keyed cartesian+tensor fnx == nx.
- `pytest -k "product or cartesian or tensor"`: 78 passed.

## Result (median-of-5, 60x60 factors)
| product   | nx        | fnx (after) | speedup vs nx |
|-----------|-----------|-------------|---------------|
| cartesian | 28.64 ms  | 9.97 ms     | 2.87x         |
| tensor    | 104.93 ms | 24.44 ms    | 4.29x         |

Before: cartesian 4.13x SLOWER, tensor 3.65x SLOWER. After: 2.87x / 4.29x faster.
