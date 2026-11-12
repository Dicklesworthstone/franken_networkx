# br-r37-c1-gb8sj Pass 15 Report

## Lever

Route `johnson(G, weight)` to `dict(all_pairs_dijkstra_path(G, weight=weight))`
only for exact `franken_networkx.Graph` / `DiGraph` inputs whose string-weight
edge scan proves no negative, non-finite, or non-numeric edge weights.

Fallback remains NetworkX Johnson for:
- negative weights;
- callable or non-string `weight`;
- multigraphs;
- views/subclasses/non-FNX graph inputs;
- non-finite or non-numeric edge weights.

## Isomorphism Proof

Pinned with `PYTHONPATH=python` after the shared venv editable install was
observed changing between scratch worktrees.

Golden corpus:
- inner-dict repro from `br-r37-c1-9l73c`;
- integer tie-order graph;
- directed negative-weight graph;
- custom string weight key;
- callable weight function;
- default unweighted path graph;
- weighted Watts-Strogatz `n=60`.

Baseline and candidate ordered JSON SHA-256:

```text
6f15f4954e339def61bca14f94150db233b6f7f9ede2920d72e19e85633c6f5a
```

Large `ws300_weighted` result digest stayed:

```text
a1214383c688702d481f980f714e78707f2e4cf688974cfe7ab262ceb76b1586
```

Ordering/tie-breaking: preserved by using the existing native all-pairs
Dijkstra path kernel only on the non-negative subset; its inner dictionaries are
already emitted in NetworkX Dijkstra finalize order.

Floating point: no new arithmetic is introduced in the wrapper. The native
Dijkstra path kernel receives the same synced edge attributes as the existing
`all_pairs_dijkstra_path` API.

RNG: not applicable.

## Benchmarks

In-process loop, same prebuilt weighted WS graph (`n=300`, `k=10`, `p=0.2`,
seed `313`, 10 loops):

| Gate | Mean seconds | Best seconds |
| --- | ---: | ---: |
| Baseline `fnx.johnson` delegated to NetworkX | 0.2873568082 | 0.2685782060 |
| Candidate public `fnx.johnson` route | 0.2132126772 | 0.1969167760 |

Speedup:
- mean: `1.35x`;
- best: `1.36x`.

Loop-amplified hyperfine (`loops=5`, 5 runs, pinned `PYTHONPATH=python`):

| Gate | Mean seconds |
| --- | ---: |
| Candidate `fnx.johnson` route | 1.980 |
| Direct `nx.johnson` | 2.442 |

Hyperfine speedup: `1.23x`.

Single-call hyperfine is dominated by Python startup and is retained only as a
sanity artifact.

## Profile Shift

Baseline profile:
- `fnx.johnson -> _call_networkx_for_parity -> networkx.johnson`;
- `networkx._dijkstra_multisource`: `0.771s` cumulative in the captured run;
- FNX-to-NX graph conversion: about `0.009s`.

Candidate profile:
- `fnx.johnson -> all_pairs_dijkstra_path -> _fnx.all_pairs_dijkstra_path`;
- native all-pairs Dijkstra binding: `0.223s` cumulative in the captured run;
- no NetworkX Johnson fallback on the routed case.

## Validation

Commands run:

```text
PYTHONPATH=python rch exec -- python johnson_harness.py golden ...
sha256sum -c baseline_golden.sha256
PYTHONPATH=python rch exec -- python -m pytest ... -q
python -m compileall -q python/franken_networkx johnson_harness.py
rch exec -- cargo check -p fnx-python --lib
git diff --check
timeout 60s ubs python/franken_networkx/__init__.py
```

Results:
- focused Johnson/parity pytest: `19 passed`;
- compileall: passed;
- `cargo check -p fnx-python --lib`: passed, with pre-existing
  `fnx-generators` dependency warnings;
- `git diff --check`: passed;
- UBS timed out after 60 seconds on the large production Python file and
  produced no finding.

## Score

Impact `2` x Confidence `4` / Effort `1` = `8.0`.

The keep threshold is satisfied. This is not the end of the Johnson lane: the
next deeper primitive is a native safe-Rust Johnson CSR kernel for the remaining
negative-weight string-key subset, preserving NetworkX Bellman-Ford potentials
and Dijkstra heap/finalize order.
