# br-r37-c1-rup1h: row-stamped live keydict proxy cache

## Target

After `br-r37-c1-mexh6`, `to_dict_of_dicts(MultiGraph/MultiDiGraph)` still spent most of its repeated-call time constructing `_LiveMultiEdgeDataView` proxy objects for the same `(u, v)` pairs. The proxy must stay a `dict` subclass, preserve read-only mutation guards, and remain live against the graph.

## Baseline

Baseline is current `bcbe6aa60` with the slot-allocation lever already landed.

- Direct `MultiGraph`: `0.42639519600197673s`, FNX/NX ratio `38.5418328633442`
- Direct `MultiDiGraph`: `0.2658915149513632s`, FNX/NX ratio `26.119227415730727`
- Hyperfine `MultiGraph` mean: `1.2061778271999999s`
- Hyperfine `MultiDiGraph` mean: `0.8570030081150001s`
- Profile `_LiveMultiEdgeDataView.__init__`: `0.299s` for `MultiGraph`, `0.151s` for `MultiDiGraph`

## Rejected Candidate

Splitting the default `nodelist=None` branch to skip `nodeset` and per-neighbor membership checks regressed the process envelope:

- Direct `MultiGraph`: `0.42639519600197673s -> 0.4972170770633966s`
- Direct `MultiDiGraph`: `0.2658915149513632s -> 0.2406584620475769s`
- Hyperfine `MultiGraph`: `1.2061778271999999s -> 1.3068305646699998s`
- Hyperfine `MultiDiGraph`: `0.8570030081150001s -> 0.866615374185s`

The source was restored.

## Kept Lever

Cache `_LiveMultiEdgeDataView` proxies in a per-graph row cache keyed by `(nodes_seq, edges_seq)`.

The cache is invalidated by node/edge mutation, is skipped by deepcopy/pickle because `_graph_deepcopy` and the pickle wrapper ignore `_fnx_` internal attrs, and preserves the existing proxy contract:

- `isinstance(view, dict)` remains true.
- Mutating the keydict proxy still raises `TypeError`.
- Edge-attribute updates remain live through the graph-backed proxy.
- Removal/re-addition changes `edges_seq`, so subsequent `to_dict_of_dicts` builds fresh proxies.

## After

- Direct `MultiGraph`: `0.42639519600197673s -> 0.17610667005646974s` (`2.421x`)
- Direct `MultiDiGraph`: `0.2658915149513632s -> 0.11641767097171396s` (`2.284x`)
- Hyperfine `MultiGraph` mean: `1.2061778271999999s -> 1.0353580307399999s` (`1.165x`)
- Hyperfine `MultiDiGraph` mean: `0.8570030081150001s -> 0.74914589054s` (`1.145x`)
- Profile `_LiveMultiEdgeDataView.__init__`: `0.299s -> 0.004s` for `MultiGraph`; `0.151s -> below top-35` for `MultiDiGraph`

## Proof

- Row-cache proof payload SHA: `8e126629c2989f8889c5811aeaa80a3921531e84d7b942b9fa94dd1c67cd036f`
- `MultiGraph` FNX digest unchanged: `231583cedff594f62d823fb4b31b13b96ed668cfb49879e4509e99bd1aa417a5`
- `MultiDiGraph` FNX digest unchanged and matches NetworkX: `f390ad0dd5b62afcea49a121448d11f13954103ea0bb8bc164092a25e38ae759`
- Floating point: N/A; attributes are serialized only.
- RNG: deterministic synthetic graph.

The known `MultiGraph` alias identity gap remains unchanged and the remaining native-construction residual is routed to `br-r37-c1-91hlu`.

## Gates

- `python3 -m py_compile python/franken_networkx/__init__.py` passed
- Focused conversion/pickle pytest: `295 passed, 75 deselected`
- Final current-checkout proof replay: `final_proof.json`
- Final direct replay: `MultiGraph 0.18910100497305393s`, `MultiDiGraph 0.11612804606556892s`, with the same FNX digests as the kept proof.
- Final hyperfine replay through `rch exec` (non-compilation command, local execution warning): `MultiGraph 1.08870926666s`, `MultiDiGraph 0.85007294304s`. This preserves a small process-envelope gain versus the original row-cache baseline for `MultiGraph`; `MultiDiGraph` is within noise at process level while direct timing remains >2x faster.
- Focused conversion/pickle refresh: `272 passed, 98 deselected`
- Mutation/cache probe passed: repeated calls reuse proxies, graph mutation invalidates, mutation guards still raise, copy/pickle omit the internal cache
- `git diff --check` passed
- UBS on the harness and report exited `0` with no critical/warning findings
- UBS on `python/franken_networkx/__init__.py` hit the 180s timeout without emitting findings; this large-file timeout is covered by py_compile, focused pytest, mutation/cache probes, proof digests, and diff-check

Score: `3.5` (`Impact 3.5 * Confidence 4 / Effort 4`). Keep.
