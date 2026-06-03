# br-r37-c1-71x9k Isomorphism Proof

Target: simple `Graph.add_edges_from` for plain two-tuples with no global or per-edge attributes.

Invariant surface:
- Ordering: preserve input edge iteration order, first-seen node display object, `nodes()`, `edges(data=True)`, and `degree()` order.
- Tie-breaking: no algorithm tie-break policy is touched; generator RNG and target selection stay in Python.
- Floating point: no floating-point arithmetic is introduced or changed.
- RNG: `barabasi_albert_graph`, `watts_strogatz_graph`, and `grid_2d_graph` keep the same Python code paths and seeds.
- Error behavior: malformed edge arity, non-tuple/list edge normalization, unhashable endpoints, `None` endpoints, and attr-bearing edges stay on the existing validated wrapper/raw paths.
- Mutation counters: final `nodes_seq` and `edges_seq` for covered fnx golden cases must match the baseline golden SHA.

Baseline SHA: `eee5746a4fea40a998cfa51d04f010f442af719ae3aa865a9968246432625c48`.
After SHA: `eee5746a4fea40a998cfa51d04f010f442af719ae3aa865a9968246432625c48`.

Measured proof:
- Golden SHA before: `eee5746a4fea40a998cfa51d04f010f442af719ae3aa865a9968246432625c48`.
- Golden SHA after: `eee5746a4fea40a998cfa51d04f010f442af719ae3aa865a9968246432625c48`.
- Raw int add_edges_from repeat-9 mean: `0.0949432891082122s -> 0.048759241219765194s`.
- Raw tuple-node add_edges_from repeat-9 mean: `0.1852558033375923s -> 0.12628128544181688s`.
- Barabasi-Albert repeat-9 mean, guarded tiny batches: `0.029665256776044972s -> 0.03285678822107406s` (hyperfine neutral).
- Grid 2D repeat-9 mean: `0.04977919488899513s -> 0.03599850533161467s`.
- Hyperfine raw-int, 5 builds per run: `813.9 ms +/- 35.4 ms -> 530.1 ms +/- 21.7 ms`.
- Hyperfine raw-tuple, 3 builds per run: `906.9 ms +/- 32.0 ms -> 647.9 ms +/- 12.7 ms`.
- Hyperfine BA, 5 builds per run: `444.5 ms +/- 19.7 ms -> 443.0 ms +/- 18.7 ms`.
- Hyperfine grid, 5 builds per run: `490.5 ms +/- 22.3 ms -> 447.7 ms +/- 17.5 ms`.
- cProfile raw-int Rust binding cumulative: `2.032s -> 0.884s` over 30 builds.

Score: Impact 4 x Confidence 4 / Effort 3 = 5.3, keep.
