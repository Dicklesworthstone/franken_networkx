# perf(all_triangles): snapshot adjacency once

br-r37-c1-tri3snap

## Problem
`all_triangles` (pure-Python set-algebra impl, kept in Python because its yield
order depends on CPython `dict_keys & dict_keys` set-intersection order — a
native-port parity blocker) was 7.9x slower than nx. The inner triple loop
re-materialised the `G.adj[u]`/`G.adj[v]` fnx adjacency view on every access,
crossing into Rust O(m*d) times.

## Lever (one)
Snapshot adjacency once: `adj = {node: nbrs for node, nbrs in G.adjacency()}`,
then read `adj[u].keys()`/`adj[v].keys()`. These are still real dict_keys in
G.adj order, so the `keys & keys` intersection iteration order — and thus the
yielded triangle stream — stays byte-identical to nx. Only the repeated
view construction is removed.

Touched: python/franken_networkx/__init__.py (_all_triangles_impl). Python-only.

## Proof (nx-exact)
360 cases: simple/multigraph/self-loop x nbunch{None, single, list} x random
gnp. **0 mismatches vs nx** (full yield order + tuple orientation). Generator
contract preserved (isinstance GeneratorType True); directed raises
NetworkXNotImplemented. pytest -k triangle: 442 passed.

## Timing (warm min-of-8, watts_strogatz(n,6,0.1))
| n   | nx (ms) | fnx before | before ratio | fnx after | after ratio |
|-----|--------:|-----------:|-------------:|----------:|------------:|
| 300 |  0.439  |   ~3.5     |    ~7.9x     |   0.716   |    1.63x    |
| 500 |  0.755  |    7.79    |     7.9x     |   ~1.25   |    1.65x    |
| 800 |  1.289  |    ~10     |    ~7.9x     |   1.955   |    1.52x    |

7.9x slower -> ~1.5-1.65x (~5-6x self-speedup). Residual = adjacency snapshot
build (O(V+E)); rest of the gap is fnx dict-materialisation vs nx native dicts.

## Score
Impact: high (5-6x self-speedup on triangle enumeration). Confidence: high
(0/360 vs nx incl. multigraph/self-loop/nbunch, 442 tests). Effort: low
(one-file Python snapshot). Score >> 2.0.
