# Isomorphism Proof: Top-Level adjacency_data Native Delegate

Bead: `br-r37-c1-9kpev`

## Scope

The retained code path gates on exact `Graph` / `DiGraph` class identity and delegates only those simple graph cases to `_fnx.adjacency_data_simple`. Multigraphs, subclasses, filtered views, and all other objects keep the existing Python loop.

## Ordering

- Node order: the native helper iterates `nodes_ordered()`, matching the public wrapper's `G.nodes(data=True)` insertion order for exact FNX graph classes.
- Adjacency order: the native helper iterates the same inner neighbor/successor order used by the graph storage. The golden fixtures build FNX and NetworkX from identical explicit insertion sequences, so the emitted adjacency order is byte-stable.
- Attribute overwrite order: each node/edge attr dict is copied, then the `id_` field is set last. This matches the Python `{**attrs, id_: value}` spread rule, including overwriting an existing attr with the same name.

## Fallbacks And Errors

- `attrs is None` is normalized before the fast path, preserving NetworkX's accepted `None` override.
- The `id_ == key` uniqueness error is raised before delegation, matching the old wrapper.
- Multigraphs fall through, preserving `key` handling and parallel-edge order.
- Subclasses and filtered views fall through, preserving Python-visible filtering and overrides.

## Floating Point And RNG

`adjacency_data` performs no numeric comparisons, arithmetic, or RNG. Floating-point edge attributes are copied as Python objects. The benchmark script uses deterministic `random.Random(seed)` only to build fixtures; it is not part of the API behavior.

## Golden SHA

Baseline and after FNX outputs are byte-identical and equal to the NetworkX oracle:

- Graph: `51f3618da12dae4e6385a1276766f735a3a0bfff34581672c9cc7d7626ccefe9`
- DiGraph: `3f96a2a9cb3040e532335e6a3af467f735284da8093ad3119fb3523fb5db17db`
