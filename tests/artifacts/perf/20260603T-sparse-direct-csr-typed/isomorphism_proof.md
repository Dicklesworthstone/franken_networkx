# Isomorphism Proof: sparse typed arrays read edge attrs once

Bead: `br-r37-c1-04z53.34`

## Change

`adjacency_default_order_typed_arrays` now walks the undirected `Graph` edge store once and reads each edge `AttrMap` once, then emits the symmetric COO entries for `(u, v)` and `(v, u)`. The Python sparse construction path remains unchanged.

## Proof Obligations

- Ordering preserved: matrix row/column coordinates are the same COO multiset as before. The route is still gated to default-nodelist CSR exact `Graph` calls, and focused parity tests compare sorted CSR payloads against NetworkX.
- Tie-breaking unchanged: sparse export has no graph algorithm tie-break. Edge duplicate handling remains simple-Graph unique-edge semantics, and self-loops still emit one diagonal entry.
- Floating point unchanged: each edge weight is read from the same synced `AttrMap` and converted through the same `Int`/`Float`/fallback branches. Each undirected edge now computes the value once and copies the same `f64` to the reverse entry, preserving NaN/value bits for both symmetric entries.
- RNG unchanged: the export path does not use RNG. Benchmark graph generation uses the same seed, `42`.
- Error/fallback behavior unchanged: unsupported weight value kinds still return `None` to the Python fallback, oversized integer weights still return `None`, non-Graph inputs and multigraphs stay on existing fallback paths, and Python attr sync still runs before the native read.

## Golden Output

Baseline FrankenNetworkX digest:

`12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

NetworkX oracle digest:

`12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

After FrankenNetworkX digest:

`12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

Focused sparse parity tests passed: `303 passed`.
