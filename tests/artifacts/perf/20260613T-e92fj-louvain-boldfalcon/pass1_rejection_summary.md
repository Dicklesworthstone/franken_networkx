# br-r37-c1-e92fj Pass 1 - Louvain Raw-Kernel Gate

## Verdict

Evidence-only. The existing raw `_fnx.louvain_communities` binding is not parity-safe for a guarded simple unweighted route.

No production code was changed.

## Corpus

- Graphs: `path_12`, `cycle_18`, `barbell_4_2`, `karate`, `ws_150`, `ws_300`
- Seeds: `0`, `1`, `7`
- Construction: NetworkX and fnx graphs are built from the same explicit node and edge insertion sequence.
- Encoding: result list order is preserved; community contents are sorted only for stable JSON because NetworkX returns sets.

## Golden

- Golden JSON: `louvain_pass1_golden.json`
- SHA256: `93a1ee03fa7c1ed7c9c258ab98a96fa77b7f0a61c17ba364383e30331054b027`
- Verification: `sha256sum -c louvain_pass1_golden.sha256` passed.

## Parity

- Public fnx wrapper vs NetworkX: `18/18` records passed.
- Raw `_fnx.louvain_communities` vs NetworkX: `3/18` records passed, `15/18` failed.
- Raw failures include ordering-only mismatches on small path/cycle cases and partition-shape mismatches on karate/ws graphs.

## Baseline

Hyperfine command shape includes Python startup and graph construction.

| Case | Variant | Mean seconds | Notes |
| --- | --- | ---: | --- |
| `ws_150`, loops 5 | public | `0.28141766372` | parity-safe |
| `ws_150`, loops 5 | raw | `0.32036230892` | not parity-safe |
| `ws_150`, loops 5 | nx | `0.36843292192` | oracle |
| `ws_300`, loops 3 | public | `0.32590726858` | parity-safe |
| `ws_300`, loops 3 | raw | `0.28467203018` | not parity-safe |
| `ws_300`, loops 3 | nx | `0.31092153968` | oracle |

cProfile in-process `ws_300`, seed 1, loops 3:

- Public wrapper: `0.02999864867s/call`; top cumulative path is `community.py:louvain_communities` -> NetworkX `louvain.py:louvain_communities`, with `_networkx_graph_for_parity` also visible.
- Raw binding: `0.00062624600s/call`; top cumulative native call is `franken_networkx._fnx.louvain_communities`.

## Isomorphism Proof

- Ordering preserved: public yes on this corpus; raw no.
- Tie-breaking unchanged: public yes under fixed seeds; raw no.
- Floating-point: no production change. Raw uses the Rust f64 path and currently diverges.
- RNG seeds: fixed at `0`, `1`, and `7`; raw seeded outputs still diverge from NetworkX.
- Golden outputs: `sha256sum -c louvain_pass1_golden.sha256` passed.

## Next Primitive

Do not add a Python wrapper route yet. The next lever belongs in the raw Rust Louvain kernel: align NetworkX seed shuffle/order, level coarsening, modularity threshold, and final partition ordering until the raw corpus is byte-equivalent.
