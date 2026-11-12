# Rejected Lever: `edge_key_lookup_string` PyString Downcast

## Target

- Bead: `br-r37-c1-w1dm8`
- Case: `MultiGraph.add_edge(i, i + 1, key=i)` for `50_000` explicit integer edge keys.
- Baseline sweep: FNX `0.519633617713615s`, NetworkX `0.11434640056437015s`, ratio `4.544x`, digest matched.
- Baseline hyperfine process envelope: `2.454s +/- 0.159s`.
- Baseline cProfile: native `MultiGraph.add_edge` `2.097s` over `250_000` calls.

## Candidate Lever

Mirror the `node_key_to_string` string fast path by changing `edge_key_lookup_string` from `extract::<String>()` to `downcast::<PyString>()` for string keys. This removes Python exception construction on non-string explicit edge keys while preserving canonical strings.

## Result

- After direct target run: FNX `0.7696101895708125s`, NetworkX `0.13038592814700678s`, ratio `5.903x`, digest matched.
- After full construction sweep target row: FNX `0.7858536712758776s`, NetworkX `0.17231141013741894s`, ratio `4.561x`, digest matched.
- After hyperfine process envelope: `2.421s +/- 0.119s`, statistically inside baseline noise.
- After cProfile: native `MultiGraph.add_edge` `1.710s` over `250_000` calls, but the direct end-to-end benchmark did not confirm a real win.

## Decision

Rejected. Score `0.0` because direct target and hyperfine did not confirm a stable improvement. The source hunk was restored and the Python extension was rebuilt from the restored source.

## Next Primitive

Do not repeat string-helper micro-levers. The next construction pass should attack the different memory-layout primitive from the bead notes: integer node interning / contiguous node IDs for the Python-side maps and inner graph substrate, with safe-Rust ordering witnesses and golden output parity.
