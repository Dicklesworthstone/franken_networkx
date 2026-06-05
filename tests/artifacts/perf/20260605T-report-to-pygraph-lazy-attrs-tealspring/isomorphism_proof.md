# br-r37-c1-blwqo lazy simple-Graph attrs

## Target

`crates/fnx-python/src/generators.rs::report_to_pygraph` was allocating one empty
`PyDict` per node and per edge for every native simple-Graph generator result.
The kept lever makes those attr dicts sparse until the first NetworkX-visible
dict handout, then caches the `PyDict` so later mutations persist.

No generator algorithm, edge ordering, RNG path, floating-point path, or
canonical Python node-key mapping changed.

## Baseline and profile

Baseline was established before the source edit with `rch`:

```text
rch exec -- maturin develop --release --features pyo3/abi3-py310
rch exec -- hyperfine --warmup 3 --runs 10 --export-json baseline_hyperfine.json \
  'python3 generator_report_bench.py bench --case gnp_700_006 --loops 80' \
  'python3 generator_report_bench.py bench --case barabasi_700_4 --loops 80' \
  'python3 generator_report_bench.py bench --case powerlaw_700_4 --loops 80' \
  'python3 generator_report_bench.py bench --case watts_800_8 --loops 80'
python3 -m cProfile -s cumulative generator_report_bench.py bench --case gnp_700_006 --loops 80
```

The baseline profile showed native `_fnx.gnp_random_graph` conversion dominating
the benchmark: 4.643 s cumulative inside a 5.325 s profile run.

## Behavior proof

Golden command:

```text
python3 generator_report_bench.py golden --output after_golden.jsonl
```

Golden sha256:

```text
baseline_golden.jsonl e3e729a95dd2ec7ca8cc883d961e9645fc5c0b7775d9500d8c94776084fd01b6
after_golden.jsonl    e3e729a95dd2ec7ca8cc883d961e9645fc5c0b7775d9500d8c94776084fd01b6
```

`cmp -s baseline_golden.jsonl after_golden.jsonl` returned 0.

Additional live attr contract checks passed:

- `G.nodes[n]["k"] = v` persists through later node attr access.
- `G[u][v]["k"] = v` persists through reverse lookup and `get_edge_data`.
- `G.edges[data=True]` returns cached live dicts, not throwaway empty dicts.
- `dict(G.adjacency())[u][v]` shares the live edge attr dict.
- `Graph(G)` and `G.subgraph(...)` preserve unmaterialized generator edges.
- `copy.copy(G)`, `G.to_directed()`, and pickle round trips preserve
  unmaterialized generator edges.
- `G.size(weight=...)` treats unmaterialized edge attrs as empty dicts.
- weighted degree treats unmaterialized edge attrs as weight 1.
- `G.clear_edges()` removes all inner edges even when no edge attr dict exists.

## After benchmark

After source edit:

```text
rch exec -- maturin develop --release --features pyo3/abi3-py310
rch exec -- hyperfine --warmup 3 --runs 10 --export-json after_hyperfine.json \
  'python3 generator_report_bench.py bench --case gnp_700_006 --loops 80' \
  'python3 generator_report_bench.py bench --case barabasi_700_4 --loops 80' \
  'python3 generator_report_bench.py bench --case powerlaw_700_4 --loops 80' \
  'python3 generator_report_bench.py bench --case watts_800_8 --loops 80'
```

| Case | Baseline mean | After mean | Ratio |
| --- | ---: | ---: | ---: |
| gnp_700_006 | 5.550710 s | 4.413766 s | 1.26x |
| barabasi_700_4 | 4.216543 s | 4.126690 s | 1.02x |
| powerlaw_700_4 | 0.996184 s | 0.858318 s | 1.16x |
| watts_800_8 | 1.794596 s | 1.491376 s | 1.20x |

Aggregate across the four benchmark cases improved from 12.559 s to 10.890 s,
or 1.15x. The after profile for `gnp_700_006` moved native cumulative time from
4.643 s to 3.366 s and total profile time from 5.325 s to 3.712 s.

Short same-command confirmation run:

| Case | Baseline mean | After mean | Ratio |
| --- | ---: | ---: | ---: |
| gnp_700_006 x40 | 2.892476 s | 2.249891 s | 1.29x |
| powerlaw_700_4 x40 | 0.669171 s | 0.533104 s | 1.26x |

Score: Impact 4 x Confidence 4 / Effort 2 = 8.0, so the lever is kept.

## Validation

```text
cargo fmt -p fnx-python --check
rch exec -- cargo check -p fnx-python --all-targets
rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings
rch exec -- cargo test -p fnx-python
python3 -m pytest tests/python/test_generator_delegations_parity.py -q
ubs crates/fnx-python/src/generators.rs crates/fnx-python/src/lib.rs crates/fnx-python/src/views.rs
```

All commands completed successfully. UBS returned exit 0; its remaining output
was broad pre-existing warning inventory, with no critical issue for this patch.
