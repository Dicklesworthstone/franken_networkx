# zge63 routing and Dijkstra length probe

## Beads

- Closed `br-r37-c1-zge63`: fresh profile evidence no longer supports another ctor wrapper lever.
- Filed `br-r37-c1-1kor1`: weighted Dijkstra length-only kernel/API primitive.

## Fresh profile target

`rch` scoreboard after `br-r37-c1-p34di`:

- `dijkstra weighted`: FNX `10.8ms`, NetworkX `6.8ms`, ratio `1.58x`.
- `Graph(edges) ctor`: FNX `9.4ms`, NetworkX `6.6ms`, ratio `1.41x`.
- `compose`: `1.04x`; `union`: `1.00x`.

This moves the best target away from `zge63` constructor micro-levers.

## Rejected wrapper lever

Candidate: route all-int, finite, string-weight, `cutoff is None`
`single_source_dijkstra_path_length` calls through the existing raw length-only
binding, then coerce integer-valued floats back to `int`.

Behavior proof:

- Public FNX SHA: `fbad62d38556c3e346ac8cc54b38078b5a400ad944ed2784647f637ecfb88cc5`.
- NetworkX SHA: `fbad62d38556c3e346ac8cc54b38078b5a400ad944ed2784647f637ecfb88cc5`.
- Public FNX matched NetworkX ordering, tie-order surface, and integer distance types.
- Raw binding SHA before coercion: `b99bf55f47386413df0c96d7cc79d00a5cad7af9122548a3037f1cb6ec75f09b`; mismatch is float distance type emission.

Benchmark gate:

- Baseline hyperfine mean: `0.3530359213s`.
- Candidate hyperfine mean: `0.3600451607s`.
- Direct proposed microbench matched public output but process-envelope hyperfine regressed.

Verdict: rejected, source restored. Score `0.0`.

## Next primitive

Attack `br-r37-c1-1kor1`: move integer distance emission and cutoff-aware
length-only handling into the Rust/PyO3 Dijkstra API, so the wrapper does not
materialize full paths or repair distance types after the fact.
