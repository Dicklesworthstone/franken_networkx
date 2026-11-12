# br-r37-c1-04z53.9125 adjacency_spectrum exact-star closed form

## Target

`fnx.adjacency_spectrum(fnx.star_graph(799))`

The baseline in the bead recorded the sorted complex golden SHA
`074becfe8e5addfd61981ce2fe0abdd63e6cbc88e8e094b0904315fa027f3063`,
direct FNX median `31.713 ms/call`, and rch hyperfine mean `488.8 ms` for
five calls.

## After

- Direct after median: `0.9316857100930064 ms/call`.
- Direct after mean: `0.9369813473507141 ms/call`.
- rch hyperfine after mean for five calls: `265.5479386933333 ms`.
- rch hyperfine after median for five calls: `266.39286586000005 ms`.
- Profile after: 200 calls in `0.254 s`; dense adjacency construction and
  `_fnx.symmetric_eigvals_rust` are absent from the star path.

## Proof

- FNX sorted SHA: `074becfe8e5addfd61981ce2fe0abdd63e6cbc88e8e094b0904315fa027f3063`.
- NetworkX sorted SHA: `074becfe8e5addfd61981ce2fe0abdd63e6cbc88e8e094b0904315fa027f3063`.
- FNX raw SHA: `6024e8f1ff1b9c7799a61eb13a51a9d8bceb8859fa1796f96c55cf9123004706`.
- NetworkX raw SHA: `6024e8f1ff1b9c7799a61eb13a51a9d8bceb8859fa1796f96c55cf9123004706`.
- Max sorted absolute delta vs NetworkX: `3.197442310920451e-14`.
- Dtype parity: FNX and NetworkX both return `complex128`.
- Ordering/tie behavior: no public ordering contract is changed; existing tests
  assert dtype plus sorted-value parity. For this center-first star golden case,
  raw order also matches NetworkX.
- Floating point surface: only the existing analytic `sqrt(n - 1)` star formula
  is used before returning `complex128`.
- RNG surface: unchanged; no RNG is used.
- Fallback surface: the guard is exact `Graph`, unweighted, center-first star
  only; weighted, directed, non-star, and empty/error paths fall through to the
  existing routes.

## Commands

```bash
.venv/bin/python - <<'PY'
# generated after_star_n800.json and after_star_n800_profile.txt
PY
```

```bash
rch exec -- .venv/bin/python -m pytest tests/python/test_adjacency_spectrum_native.py -q
```

```bash
rch exec -- hyperfine --warmup 3 --runs 12 --export-json tests/artifacts/perf/20260616T-adjacency-spectrum-star-closedform-coppercliff/after_hyperfine_star_n800.json 'env PYTHONPATH=python .venv/bin/python -c "import franken_networkx as fnx; [fnx.adjacency_spectrum(fnx.star_graph(799)) for _ in range(5)]"'
```

## Score

Impact `34.04` (direct median speedup) x Confidence `0.95` / Effort `1` =
`32.34`. The rch hyperfine command still improves end to end (`488.8 ms` to
`265.55 ms`) despite Python startup/import overhead dominating the command.
