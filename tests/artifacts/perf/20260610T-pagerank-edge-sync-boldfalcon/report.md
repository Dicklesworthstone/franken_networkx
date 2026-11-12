# perf(pagerank): edge-only DiGraph attr sync

Bead: `br-r37-c1-f2ohl`

## Target

Fresh RCH smoke evidence showed the stale weighted-PageRank vs-NetworkX gap no
longer reproduced on current `origin/main`, but cProfile still showed
`_sync_rust_edge_attrs` rebuilding node attributes before weighted
`_pagerank_scipy`. PageRank reads edge weights only; node attrs must not affect
ordering, tie-breaking, or floating-point output.

## Lever

One lever:

- Route weighted `pagerank` through `_sync_rust_edge_attrs(G, edge_only=True)`.
- Add the missing `PyDiGraph._fnx_sync_edge_attrs_to_inner` sibling so directed
  graphs actually take the edge-only path.

The sparse COO builder and scipy power iteration are unchanged.

## Evidence

RCH-wrapped warmed hyperfine, deterministic weighted `DiGraph`, `n=1400`,
`5600` edges, `80` in-process PageRank calls per command:

| command | baseline mean | after mean | result |
|---|---:|---:|---:|
| FNX weighted pagerank | `1.200341s` | `0.632024s` | `1.90x` self-speedup |
| NetworkX weighted pagerank | `0.817245s` | `0.751759s` | context |

The same benchmark moved FNX from `1.47x` slower than NetworkX to `1.19x`
faster than NetworkX on this metadata-heavy weighted path.

Profile, `n=1400`, `50` calls:

- Baseline total `0.393s`; `_sync_rust_edge_attrs -> _fnx_sync_attrs_to_inner`
  was `0.183s`.
- After total `0.203s`; the full node+edge sync frame is gone from the hot list.

## Proof

Golden proof covers both clean weights and post-construction dirty edge-weight
mutation (`G[u][v]["weight"] = ...`), proving edge-only sync still propagates
Python-visible edge edits into Rust storage.

- `all_close`: `true`
- `max_abs`: `0.0`
- `max_rel`: `0.0`
- Clean FNX/NX SHA: `396217c7634f614499a7ab03828e38e3efb2d788cb9cbf886ac435892ef2dfbd`
- Dirty-edge FNX/NX SHA: `8c73af60d1649f34c6289c65a1355eca3f68cd27e644b5d141a97abb2322e46a`
- Proof payload SHA: `f492b0904dc5f3ae2050b3cf24f4cef43719af0f90e2087b008926c22a1fc695`

Isomorphism notes:

- Ordering: `pagerank` still returns `dict(zip(list(G), x))`; node insertion
  order is unchanged.
- Tie-breaking: no ordering-dependent ties are introduced; matrix rows still
  follow `list(G)`.
- Floating point: the same scipy sparse power iteration path runs; only the
  pre-sync route changes.
- RNG: none; harness graph is deterministic.

## Gates

- `maturin develop --release --features pyo3/abi3-py310` via RCH wrapper: passed
  with existing `fnx-generators` warnings.
- `python -m py_compile python/franken_networkx/__init__.py .../harness_pagerank_edge_sync.py`: passed.
- Focused pagerank pytest: `26 passed, 174 deselected`.
- Focused thread-safety pagerank pytest: `1 passed, 12 deselected`.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed on `ovh-a` with existing `fnx-generators` warnings.
- `cargo fmt --check -p fnx-python`: blocked by pre-existing formatting drift in
  unrelated `algorithms.rs`, `lib.rs`, `readwrite.rs`, plus old blank-line drift
  in `digraph.rs`.
- `rch exec -- cargo clippy -p fnx-python ... -- -D warnings`: blocked first by
  pre-existing `fnx-generators` `unused_must_use` warnings, then by pre-existing
  `collapsible_if` findings in old cache helpers under `digraph.rs`/`lib.rs`.
- Focused UBS on changed files: Rust phase completed; Python analyzer exceeded
  the bounded window and was terminated after ~2.5 minutes without a completed
  report.

## Score

Impact `3` x Confidence `3` / Effort `1` = `9.0`. Kept.

## Next

Reprofile weighted PageRank after this lands. The next likely primitive is a
fused finite-weight validation plus COO construction pass, if fresh profiles show
the separate nonfinite scan and COO builder remain material.
