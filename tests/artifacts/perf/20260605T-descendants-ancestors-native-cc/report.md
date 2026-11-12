# perf: descendants/ancestors undirected -> native reachability kernel

Found via a single-pair/small-output sweep on a large graph (the conversion/
PyO3-tax signature): `descendants` was 5.11x slower than nx at n=400.

## Lever
The native bindings `_fnx.descendants` / `_fnx.ancestors` (algorithms.rs) already
handle BOTH directed (successor/predecessor reachability) AND undirected
(component BFS via `bfs_edges`). But the Python wrappers in `__init__.py` only
routed the *directed* case to the native kernel; the *undirected* case fell to a
Python-level BFS over `G[n]` (the lazy AtlasView), paying a per-neighbor PyO3
crossing for every edge. Route the undirected case through the existing native
kernel too — one line each, no Rust change (the kernel was already correct).

The wrapper keeps its up-front `hash(source)` (unhashable -> TypeError parity)
and `source not in G` check (NetworkXError with the wrapper's exact message,
which differs from the native kernel's `repr()`-based message for str keys), so
error parity is preserved; the native kernel only runs for an in-graph source.

## Correctness (byte-exact)
`parity_proof.py`: 80 random graphs (40 undirected gnp + 40 directed gnp),
every node as source, BOTH descendants and ancestors vs networkx = 3720 cases,
**0 mismatches** (sorted reachable sets). Missing-node error message parity
verified for both functions (NetworkXError, identical text).
golden_sha256 = `f0bba7b6806d74abb537373e8f230338ef04a619111026026525fe4fb9a34a58`

## Perf (warm min-of-8)
- n=1000: OLD Python BFS 2.130ms -> NEW native 0.239ms = **8.90x** self; now
  0.58x vs nx (i.e. ~1.7x faster than nx, was 5.1x slower)
- n=3000: OLD 9.378ms -> NEW 0.753ms = **12.45x** self; 0.58x vs nx

One lever, behavior-identical (sets are order-invariant), no FP/RNG.
