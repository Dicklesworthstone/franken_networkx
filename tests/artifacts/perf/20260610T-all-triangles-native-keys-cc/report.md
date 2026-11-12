# perf(all_triangles): key-only adjacency snapshot

br-r37-c1-iowms

## Problem
`_all_triangles_impl` (pure-Python; kept in Python because its yield order
depends on CPython `dict_keys & dict_keys` set-intersection order — a
native-port parity blocker) snapshots adjacency once via
`{node: nbrs for node, nbrs in G.adjacency()}`. For an fnx `Graph`,
`G.adjacency()` routes to the native `_native_adjacency_dict`, which
materialises an attr-bearing `{nbr: attrs}` dict per node — wasted work,
since the triangle enumeration only ever reads `adj[u].keys()`.

## Lever (one)
For an **exact** simple FNX `Graph`, build the snapshot from key-only rows:

```python
_nak = getattr(G, "_native_adjacency_keys", None) if type(G) is Graph else None
if _nak is not None:
    adj = {node: dict.fromkeys(nbrs) for node, nbrs in _nak()}
else:
    adj = {node: nbrs for node, nbrs in G.adjacency()}
```

`_native_adjacency_keys()` is the node-major neighbour-KEY snapshot (same
`(node, [nbr, ...])` source/adjacency order as `adjacency()`, no edge-attr
dicts built). `dict.fromkeys(nbrs).keys()` is a real `dict_keys` whose
hash-table layout depends only on the neighbour KEY objects and their
insertion order — identical to the attr-bearing dict's keys — so the
`keys & keys` set-intersection iteration order (and thus the yielded
triangle stream + tuple orientation) stays byte-identical to nx.

`type(G) is Graph` excludes MultiGraph and all filtered views (subgraph /
edge_subgraph views are `Graph` *subclasses* whose `_native_adjacency_keys()`
returns `{}` because they keep an empty native inner). Those fall back to the
attr-bearing `G.adjacency()` path, which respects the view's live filtered
adjacency. Verified: view triangle output unchanged.

Touched: `python/franken_networkx/__init__.py` (`_all_triangles_impl`).
Python-only — no Rust rebuild (`_native_adjacency_keys` is an already-shipped
binding).

## Proof (nx-exact)
`harness_proof.py`: 64 cases (gnp/ws/ba x 6 seeds + self-loop + string-labels
+ tiny/empty x nbunch{None, single, list}). **0 mismatches vs nx** (full yield
order + tuple orientation).

Golden sha256 (full ordered triangle stream, identical before & after the
lever and identical to nx):
`0a4f30322361f7c45644bfe37007612b26431814bbaff6c6e2cd9f806a2395b9`

Fallback paths verified separately: MultiGraph triangle output == nx;
node-induced subgraph view == nx; edge_subgraph view == nx.

pytest -k triangle: **442 passed**.

## Timing (warm min-of-10, in-process A/B, watts_strogatz(n,6,0.1), harness_ab.py)
| n   | nx (ms) | old `G.adjacency()` | old ratio | new native-keys | new ratio | self-speedup |
|-----|--------:|--------------------:|----------:|----------------:|----------:|-------------:|
| 300 |  0.444  |        0.711        |   1.60x   |      0.572      |   1.29x   |    1.24x     |
| 500 |  0.802  |        1.212        |   1.51x   |      0.995      |   1.24x   |    1.22x     |
| 800 |  1.322  |        1.978        |   1.50x   |      1.614      |   1.22x   |    1.23x     |

1.50-1.60x slower -> 1.22-1.29x slower (~1.23x self-speedup). Residual gap is
the Python triple-loop + per-row PyObject key construction (nx reads native C
dicts); the set-intersection order is the parity blocker that keeps the loop
in Python.

## Score
Impact: moderate (~1.23x self-speedup on triangle enumeration, eliminates
per-node attr-dict materialisation). Confidence: high (0/64 vs nx incl.
self-loop/string-label/nbunch, fallback paths verified, identical golden sha,
442 tests). Effort: very low (one-file Python, no rebuild). Score >= 2.0.
