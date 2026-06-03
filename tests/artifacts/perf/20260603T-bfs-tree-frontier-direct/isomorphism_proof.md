# Isomorphism Proof

Bead: `br-r37-c1-epg5e`

## Change

`_FailFastEdgeIterator` now uses native graph mutation sequence counters when it can prove the graph is a native FrankenNetworkX graph without NetworkX private-storage overrides.

Fallback behavior is unchanged for graphs with private storage or without `nodes_seq` / `edges_seq`.

## Ordering

Ordering is unchanged. The iterator still consumes the same materialized edge iterable in the same order. The change only replaces the mutation check that runs after `next(self._iterator)`.

Golden observed-output SHA stayed:

```text
5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64
```

## Tie-Breaking

No graph algorithm or view materialization tie-breaker changed. `_DiGraphEdgeView._materialize()` still uses the same native edge order, and the iterator does not sort or filter.

## Floating-Point

N/A. The edge-view guard does not read or compute floating-point values.

## RNG

N/A for the implementation. The benchmark graph seed remained fixed at `42`.

## Mutation / Fail-Fast Contract

For native graphs, `nodes_seq` and `edges_seq` are monotonic counters bumped by native node/edge mutations. Comparing those counters preserves the fail-fast `RuntimeError("dictionary changed size during iteration")` contract for node and edge mutations while avoiding per-edge `len()` and `number_of_edges()` calls.

For private NetworkX storage overrides, the iterator keeps the previous count-based guard because Rust counters cannot represent arbitrary Python-private storage mutations.

Focused validation:

- Edge-view mutation tests: `4 passed, 427 deselected`.
- Edge iteration/order/liveness tests: `29 passed`.

## Golden Output

Baseline FNX observed output:

```text
5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64
```

After FNX observed output:

```text
5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64
```
