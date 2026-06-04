# bipartite.betweenness_centrality — route to fnx-native Brandes kernel (br-r37-c1-kp3o0)

## Problem
`franken_networkx.bipartite` does `from networkx.algorithms.bipartite import *`, so
`bipartite.betweenness_centrality` ran networkx's implementation, which internally calls
`nx.betweenness_centrality(G, normalized=False)` — pure-Python Brandes — directly over the
fnx graph's String-keyed PyO3 adjacency. ~105ms on n=240 (≈1.0x vs nx: nx-on-fnx-substrate).

## Lever (ONE)
The bipartite layer only adds a closed-form rescaling (`bet_max_top`/`bet_max_bot`) on top of
the *unnormalized* betweenness values. Override `betweenness_centrality` in `bipartite.py` to
route the heavy Brandes computation through fnx's own native `betweenness_centrality` kernel
(`normalized=False, weight=None`), then apply networkx's exact bipartite normalization.

## Behavior parity
The native kernel is fnx's standard shipped betweenness implementation. Its float-accumulation
order differs from networkx at the ~1e-16 level — this is the *established fnx betweenness
contract* (the top-level `fnx.betweenness_centrality` already diverges from nx by ~1e-13). So
this override makes the bipartite variant **consistent with fnx's own betweenness** rather than
introducing any new divergence.

- Parity sweep: 34 cases (30 random bipartite × seeds, davis_southern_women, path, cycle4,
  complete-bipartite; directed spot-check) — **max |Δ| vs networkx = 5.55e-17** (machine
  epsilon), **dict key order byte-identical to nx** in every case (keyorder_bad=0).
- Determinism: identical output across repeated runs (native kernel is deterministic);
  golden sha256 over the fnx output = `f38d52d6d421f50d8b8804d01b315526eb0cb324a88ca13c5fed0c2e5ab15119`
  (stable across debug and release builds).
- Existing suite: `pytest -k "bipartite or betweenness"` → 659 passed, 6 skipped.

## Benchmark (min-of-9, ms, release build)
| graph (top+bottom, p) | networkx | fnx (after) | speedup |
|-----------------------|----------|-------------|---------|
| 120+120, p=0.08       | 105.80   | 3.78        | 28.02x  |
| 60+60,  p=0.15        | 25.57    | 0.90        | 28.37x  |
| 40+40,  p=0.2         | 10.63    | 0.38        | 28.07x  |

Before: ~1.0x (nx-on-fnx-substrate). After: ~28x FASTER than networkx.

## Score
Impact: very high (28x faster, large absolute ms). Confidence: high (machine-epsilon parity,
key-order exact, deterministic golden, 659 tests). Effort: low (single Python override reusing
the native kernel, no Rust change). → Score >> 2.0.
