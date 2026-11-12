# descendants_at_distance — non-integer distance parity fix (br-r37-c1-miu30)

## Bug
`fnx.descendants_at_distance(G, src, 0.5)` returned `{src}` and `(…, 1.9)` returned
layer-1, because the wrapper did `int(distance)` which TRUNCATES `0.5 -> 0` and
`1.9 -> 1`. networkx returns `set()` for these. nx's algorithm is:

    for i, layer in enumerate(nx.bfs_layers(G, source)):
        if i == distance:
            return set(layer)
    return set()

so a layer is returned ONLY when an integer index `i` equals `distance`. Thus `2.0`
matches (`2 == 2.0`) and yields layer 2, but `0.5`/`1.9`/`-1`/non-numeric never equal
any `i` and yield `set()`. Pre-existing (the native kernel and the dadlocal perf rewrite
both preserved the truncation).

## Fix (ONE lever)
Drop the truncation gate and reject any `distance` that is not exactly a non-negative
integer: `if distance_int < 0 or distance != distance_int: return set()`. The
`distance != distance_int` test rejects non-integer numerics (0.5, 1.9, -0.5) while
accepting integer-valued floats (2.0 == 2); `distance_int < 0` rejects exact negatives
and the non-numeric sentinel (where `int()` raised). Source-not-in-graph still raises
NetworkXError as before.

## Behavior parity (isomorphism proof)
- Sweep: 4 graphs (path, digraph, gnp, star) × 18 distances {0, 0.0, 0.5, 1, 1.0, 1.9,
  2, 2.0, 3, 3.0, 5, -1, -0.5, -2.0, True, False, "foo", 100} = **72 cases, 0 mismatches**
  — comparing result value, result type (`set`), and raised-exception type vs networkx.
- Golden sha256: `30a894d2af6ff3dfdea3ec9b1b89a8d4765f33f39d4ddc9de1074bdd5b298538`.
- Existing suite: `pytest -k descendants` → 66 passed.

## Notes
Pure correctness fix (no perf change); the fast local-BFS path from br-r37-c1-dadlocal is
untouched for valid integer distances. Integer-valued floats (2.0) now correctly return
their layer instead of being indistinguishable from int 2 — both already worked; the win
is 0.5/1.9-style fractional inputs now returning set() like nx.
