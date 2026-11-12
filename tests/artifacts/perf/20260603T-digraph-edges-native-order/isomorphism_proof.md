# Isomorphism Proof

Bead: `br-r37-c1-acuub`

Lever: route `_DiGraphEdgeView._materialize()` through `DiGraph._native_edges_no_data()`.

## Ordering

The replaced Python loop was:

```python
for source in self._graph:
    for target in self._graph.succ[source]:
        result.append((source, target))
```

The new Rust helper walks `inner.edges_ordered_borrowed()`, whose contract is node insertion order followed by each node's successor insertion order. That is the same traversal order and matches NetworkX `OutEdgeView` order for the golden graph.

## Data Surface

Only the no-data materialization path changed. `G.edges(data=True)`, attribute lookup, nbunch filtering, and `default` handling remain on the existing Python paths.

## Live View Contract

`_DiGraphEdgeView.__iter__()` still calls `_materialize()` at iteration time. Existing live-view behavior is preserved: a view created before later edge insertion sees the new edges when iterated.

## Tie-Breaks, Floating Point, RNG

There are no algorithmic tie-breaks or floating-point operations in this projection path. The benchmark/golden harness uses a fixed deterministic edge-generation seed (`23`), and the graph data is constructed before timed iteration.

## Golden SHA-256

`golden_before.json` and `golden_after.json` are byte-identical:

```text
837ade831910ce92b5d7c457d17182faf106639046543d061cf3ec16424fbd5f
```

`diff -u golden_before.json golden_after.json` produced no output.

Focused Python parity also passed across empty, singleton, small, medium, and larger deterministic DiGraph shapes, including `edges(data=True)` and live views after mutation.
