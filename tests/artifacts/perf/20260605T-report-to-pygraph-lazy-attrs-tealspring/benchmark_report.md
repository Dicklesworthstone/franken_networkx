# br-r37-c1-blwqo benchmark report

## Lever

Simple `PyGraph` generator bridges now keep node and edge Python attr dict maps
sparse after native graph construction. Empty `PyDict` objects are created only
when a NetworkX-visible live attr mapping is handed out.

The generator kernels, RNG inputs, node canonicalization, edge ordering, and
floating-point paths were unchanged.

## Before and after

All timings are `rch`-backed hyperfine means against raw `_fnx` generator
bindings after release `maturin develop`.

| Case | Baseline mean | After mean | Speedup |
| --- | ---: | ---: | ---: |
| `gnp_700_006` | 5.550710 s | 4.413766 s | 1.26x |
| `barabasi_700_4` | 4.216543 s | 4.126690 s | 1.02x |
| `powerlaw_700_4` | 0.996184 s | 0.858318 s | 1.16x |
| `watts_800_8` | 1.794596 s | 1.491376 s | 1.20x |

Aggregate benchmark mean improved from 12.559034 s to 10.890151 s, a 1.15x
suite-level win. The profile-backed `gnp_700_006` case moved native cumulative
time from 4.643 s to 3.366 s.

## Behavior proof

`baseline_golden.jsonl` and `after_golden.jsonl` are byte-identical:

```text
e3e729a95dd2ec7ca8cc883d961e9645fc5c0b7775d9500d8c94776084fd01b6
```

The golden covers node order, edge order, adjacency rows, degree rows, graph
attrs, node counts, and edge counts. The live attr check covers lazy
materialization identity, mutation persistence, copy/subgraph/to_directed,
weighted defaults, and pickle round trip.

## Score

Impact 4 x Confidence 4 / Effort 2 = 8.0.

The lever clears the required Score >= 2.0 threshold and is kept.

## Next profile-backed target

The after profile still spends 3.366 s inside the raw `_fnx.gnp_random_graph`
call for 80 loops. The next deeper primitive is an integer-adjacency/native-edge
emission path for random simple generators so the generator core can avoid
string-key graph insertion costs before the Python bridge labels nodes.
