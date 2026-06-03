# Alien Recommendation Card

## Primitive

Deforestation and projection pushdown over the owned adjacency relation.

## Harvest note

The no-gaps directive points performance work toward safe-Rust owned kernels instead of foreign acceleration. For this graph API bead, the useful analogous primitive is to keep projection over graph storage in Rust and avoid constructing Python adjacency wrapper layers when the operation only needs `(u, v, data)` triples.

## Application

`to_edgelist(G)` for exact `Graph` and `DiGraph` now projects directly from ordered native edge storage into Python tuples with live attribute dictionaries. This removes an intermediate Python edge-view traversal from the profiled path while preserving the observable materialized fnx result.

## Next frontier

The remaining upstream gap is architectural at the API surface: NetworkX returns a cheap `EdgeDataView` for `to_edgelist`. A future one-lever bead should profile and replace fnx's eager view call with a lazy view-compatible return while preserving existing set algebra and guard semantics or explicitly repairing the compatibility contract.
