# br-r37-c1-nt3co safe-Rust geometric grid

Agent: BoldFalcon
Date: 2026-06-13
Lever: replace the Python/SciPy radius-query path in the geometric generators with an owned safe-Rust uniform-grid candidate index.

## Profile-backed target

The cc-filed perf bead identified the remaining geometric-generator gap after prior constant-factor work:
`soft_random_geometric_graph` still spent its time in radius-pair enumeration and SciPy import/spatial plumbing, while parity required preserving sorted `i < j` candidate order so soft edge RNG draws happen in the same sequence.

Focused profile, `soft_random_geometric_graph(n=800, radius=0.05, dim=2, loops=3)`:

| build | calls | total cumulative time | dominant frames |
| --- | ---: | ---: | --- |
| baseline | 970,049 | 0.459s | SciPy import/spatial path, generator wrapper |
| candidate | 385,421 | 0.110s | Python probability/RNG loop; native edge-index helper remains below the residual Python loop |

The residual after the lever is the expected soft-graph probability/RNG loop, not the candidate index.

## Benchmarks

All timings used `hyperfine` via `rch exec` from the same detached worktree, with `n=800`, `loops=7`, `--warmup 2`, and 8 measured runs.

The parent/candidate timing table was refreshed against measured parent `3e6fadbe5`. The final push rebase also includes later view-cache parent `949644159`; that parent does not change the geometric radius-query lever, golden outputs, or benchmark harness.

| case | baseline mean | candidate mean | speedup | upstream NetworkX mean | candidate vs nx |
| --- | ---: | ---: | ---: | ---: | ---: |
| `random_geometric_graph` | 0.505427923s | 0.286572345s | 1.763701x | 0.566213763s | 1.975814x |
| `soft_random_geometric_graph` | 0.619037150s | 0.399068731s | 1.551204x | 0.714285300s | 1.789880x |
| `thresholded_random_geometric_graph` | 0.552861472s | 0.329095184s | 1.679944x | 0.649903727s | 1.974820x |

Score: Impact 1.68 x Confidence 4 / Effort 2 = 3.36, so the lever clears the >=2.0 keep threshold.

## Golden-output proof

Golden files:

- `baseline_golden.json`
- `candidate_golden.json`

SHA256:

```text
23c087a133189903a7a5593256ed89962c3062fba3d167cfac5781b36b43f928
```

`baseline_golden.json` and `candidate_golden.json` are byte-identical. The focused parity probe hash is:

```text
38aa0101d23199543a765153cc03c1a685b4763e5eee512d01a2598eb7a770a8
```

The parity probe covers:

- `random_geometric_graph`, `soft_random_geometric_graph`, and `thresholded_random_geometric_graph`
- `geometric_edges`
- `p = 1`, `p = 2`, `p = inf`, `0 < p < 1`, `p = 0`, and `p < 0`
- zero and negative radius cases
- arbitrary node labels for edge-order mapping

## Isomorphism proof

Ordering is preserved because the Rust index returns sorted `(i, j)` integer pairs with `i < j`. The Python wrapper maps those indices through the existing node list in the original order, matching the prior `combinations(nodes, 2)` contract and NetworkX-observable edge order.

Tie-breaking is unchanged because geometric radius enumeration has no independent tie-break decision. Candidate order is sorted before exposure to Python, so equal-distance or same-cell pairs do not depend on hash-map iteration order.

Floating-point behavior is preserved by routing only cases whose observed semantics match the native predicate. For `p >= 1`, the Rust predicate applies the same radius comparison over the same coordinates; for `p = 2`, it uses the algebraically equivalent squared-distance comparison. For `p = inf`, it uses the Chebyshev max-coordinate predicate. For `0 < p < 1`, the path falls back to the existing Python arithmetic. For `p <= 0`, the wrapper returns no pairs, matching the observed NetworkX/SciPy candidate behavior captured in the parity probe.

RNG behavior is unchanged. Position and weight generation stay in Python. For `soft_random_geometric_graph`, random edge draws still occur only after candidate enumeration, and the candidate sequence is the same sorted `i < j` sequence as the baseline, so the draw stream is consumed in the same order.

Fallback behavior is preserved. Unsupported, non-finite, inconsistent-dimension, and non-sequence positions return `None` from Rust and use the existing Python path.

## Validation

- `rch exec -- cargo check -p fnx-python --lib`: passed. Pre-existing `fnx-generators` unused-return warnings remained.
- Focused Python parity: `222 passed in 1.03s` for the geometric/classic generator suites.
- `python3 -m py_compile` on the touched Python files and benchmark harness: passed.
- `ubs --only=rust crates/fnx-python/src/lib.rs`: no critical findings; existing large-file warning inventory remains.
- `ubs --only=python python/franken_networkx/__init__.py tests/artifacts/perf/20260613T-nt3co-safe-grid-boldfalcon/bench_geometric_grid.py`: timed out after 120s without findings output.
- `cargo clippy -p fnx-python --lib -- -D warnings`: blocked by pre-existing `fnx-generators` warnings outside this lever.
- `rustfmt --edition 2024 --check crates/fnx-python/src/lib.rs`: blocked by pre-existing formatting drift in existing binding files/regions.
