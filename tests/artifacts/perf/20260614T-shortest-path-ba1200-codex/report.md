# br-r37-c1-04z53.81 shortest_path indexed bidirectional BFS

## Target

- Bead: `br-r37-c1-04z53.81`
- Hotspot: `franken_networkx.shortest_path(graph, 0, 900)` on `barabasi_albert_graph(1200, 4, seed=11)`
- Profile-backed residual: public wrapper overhead remained, but the largest frame was the native bidirectional BFS kernel.

## Baseline

- Golden SHA: `67e3d70817e4424b458f7d1540b4a97db6bd6b484fa5b5ddada30663339d513f`
- Case digest: `b1f776746489abca9976b74a385449eeebb941eae20d2b1a21b3d2bf056e1513`
- Direct FNX median: `0.808660618000431s` for 50k calls (`16.17321236000862us/call`)
- Direct NetworkX median: `0.5989574349950999s` for 50k calls (`11.979148699901998us/call`)
- Hyperfine FNX mean: `1.0933775765s +/- 0.030595091886407917s`
- Hyperfine NetworkX mean: `0.8547404089s +/- 0.019344331956672175s`
- Profile: 20k calls in `0.414s`; native bidirectional kernel `0.303s`.

## Alien Primitive

- Mapped graveyard section: GraphBLAS BFS, where BFS is repeated boolean-frontier traversal over sparse adjacency rows.
- Local implementation form: keep the existing safe-Rust adjacency-row substrate and use indexed frontiers, seen vectors, and parent arrays instead of string/hash-map frontier state.
- Fallback: no separate fallback path is needed because the indexed kernel uses the same graph storage and returns `None` for the same missing/no-path cases; the Python binding keeps existing exception conversion.

## Lever

One lever only:

- Add index-space `Graph` and `DiGraph` bidirectional meta kernels.
- Preserve NetworkX smaller-frontier choice, row scan order, first-meet check order, and meet-node display-parent metadata.
- Reconstruct Python display objects from row-key and pred-row-key mirrors after the indexed path is found.

## Isomorphism Proof

- Ordering preserved: yes; BA, grid, directed, and string tie cases byte-compare exact returned paths against NetworkX.
- Tie-breaking unchanged: yes; frontier choice, row order, and first-meet order mirror the existing meta kernel.
- Floating point: N/A; unweighted BFS path only.
- RNG: shortest-path call has no RNG; graph construction uses a fixed seed.
- Golden SHA: `67e3d70817e4424b458f7d1540b4a97db6bd6b484fa5b5ddada30663339d513f`
- Case digest: `b1f776746489abca9976b74a385449eeebb941eae20d2b1a21b3d2bf056e1513`

## Results

- Direct FNX candidate median: `0.19218891399214044s` for 50k calls (`3.843778279842809us/call`)
- Direct speedup: `4.2076x`
- `rch exec -- hyperfine` FNX mean: `0.46151251748s +/- 0.022147372531976652s`
- Hyperfine speedup versus baseline FNX: `2.3691x`
- NetworkX control in candidate hyperfine: `0.85408282858s +/- 0.036705270430972964s`
- Candidate FNX is `1.85x` faster than NetworkX on the same process-level harness.
- After-profile: 20k calls in `0.152s`; native bidirectional kernel `0.050s`.

## Score

- Direct score: `Impact 4.2076 * Confidence 4 / Effort 1 = 16.83`
- Hyperfine score: `Impact 2.3691 * Confidence 4 / Effort 1 = 9.48`
- Verdict: keep.

## Validation

- `.venv/bin/python -m pytest tests/python/test_bidi_efficiency_directed.py tests/python/test_shortest_path.py tests/python/test_traversal_tree_parity.py tests/python/test_shortest_path_conformance_matrix.py tests/python/test_shortest_path_variants_parity.py -q`: `185 passed`
- `rch exec -- cargo check -p fnx-python --lib`: passed with pre-existing warnings.
- Broad `pytest tests/python -k "shortest_path or bidirectional"` was blocked during collection by missing optional `pandas`, before selected tests ran.
- `rustfmt --edition 2024 --check` on touched Rust files is blocked by pre-existing formatting drift outside this hunk (`br-r37-c1-uk5bq`).
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings` is blocked by pre-existing `fnx-generators` unused-result errors (`br-r37-c1-sp6z3`).
- `timeout 120 ubs ...` completed Python scanning and then timed out during Rust scanning with no finding emitted.
