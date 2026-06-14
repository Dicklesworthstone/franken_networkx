# br-r37-c1-2a00r Pass 2 Design Gate

Verdict: Pass 3 should implement the single combined `nodes_seq` + `edges_seq`
guard-token getter. Do not pivot this bead to `_native_edges_data_key` or any
materializer/cache work in Pass 3.

## Inputs

- Measured artifacts: `baseline_report.md`, `baseline_profile.txt`,
  `baseline_direct.json`, `baseline_hyperfine.json`, `baseline_golden.json`,
  and `golden.sha256` in this directory.
- Graveyard discipline: start from the measured symptom, ship one lever at a
  narrow drop-in interface, name the baseline comparator, and reject clever
  structures when constants/cache behavior are not proven. Relevant canonical
  anchors: `/data/projects/alien_cs_graveyard/alien_cs_graveyard.md:13-22`,
  `:54-57`, `:5801`, `:5823-5826`, `:5961-5977`; summary anchors:
  `/data/projects/alien_cs_graveyard/high_level_summary_of_frankensuite_planned_and_implemented_features_and_concepts.md:2261-2271`,
  `:2397-2401`.

## Hotspot Evidence

- Direct medians on the 5000-node / 40000-edge DiGraph corpus:
  - `edges`: FNX `21.289696ms`, NetworkX `4.827199ms`, FNX/NX `4.410x`.
  - `edges(data=True)`: FNX `13.073435ms`, NetworkX `8.844711ms`, FNX/NX
    `1.478x`.
  - `edges(data="w")`: FNX `50.199544ms`, NetworkX `9.619154ms`, FNX/NX
    `5.219x`.
  - `out_edges(data=True)`: FNX `0.708348ms`, NetworkX `12.991989ms`,
    FNX/NX `0.055x`.
  - `edges.data("w")`: FNX `30.261039ms`, NetworkX `18.245394ms`, FNX/NX
    `1.659x`.
- cProfile split:
  - `_FailFastEdgeIterator` `_gen`: `0.728392959s` over `3,200,080`
    primitive calls, the per-edge guarded drain loop.
  - `_native_edges_data_key`: `0.969s` over `40` calls, a larger but narrower
    residual for the `data="w"` consumers only.
- Golden baseline:
  - Bundle SHA: `7f1f79e081e71ab0e4030308a1df76f3419b7a14bc8ee8a3d58ef2aa693aeeea`.
  - File SHA: `6b4ccd83d4948aaa685270ba125eb6b0a250d676a4bf7f8dc5c64d96e4613684`.
  - FNX and NetworkX edge outputs are byte-equal for all timed cases.

Interpretation: `_native_edges_data_key` is real, but it is a separate
materializer residual. The guard loop is the common per-edge tax paid by
guarded `edges()` / `edges(data=True)` / data-view drains, and the bead's
remaining scoped item is explicitly the combined guard token. Pivoting now
would leave the `edges()` `4.410x` gap untouched and would mix proof surfaces.

## Rejected Alternatives

1. Pivot Pass 3 to `_native_edges_data_key`.
   - Rejected for this pass, not forever. It targets only `data="w"` /
     `edges.data("w")` and requires separate materializer/cache proof work.
     Re-profile after the guard-token lever; if `data_key` remains dominant,
     file or continue a distinct one-lever pass for it.
2. Mix guard-token and materializer changes.
   - Rejected. The one-lever rule would lose causal attribution and combine
     distinct behavior surfaces: mutation guards vs. value materialization.
3. Loosen or remove the mutation guard.
   - Rejected. Current FNX guard behavior is part of the captured baseline,
     including the isolated-node mutation difference from NetworkX.
4. Use a lossy 64-bit hash/mix of `(nodes_seq, edges_seq)`.
   - Rejected. Use an exact combined token, such as a 128-bit Python integer
     packing `(nodes_seq << 64) | edges_seq`, so the new path has the same
     wraparound envelope as the existing counters and no extra collision risk.
5. Broaden into MultiGraph edge storage or `edge_py_attrs` re-keying.
   - Rejected. Those are separate residuals and higher-risk surfaces.

## Selected One Lever

Add one exact combined structural guard-token getter and route
`_FailFastEdgeIterator(..., guard_edge_count=True)` through one token read and
one comparison per yielded item.

Required behavior of the getter:

- Represents the exact pair `(nodes_seq, edges_seq)` with no lossy hashing.
- Has no side effects and does not inspect edge data.
- Is available only on native FNX graph classes; NetworkX-private-storage or
  missing-getter cases keep the existing fallback path.

Python routing rule:

- For `guard_edge_count=True`, prefer the combined token when present and the
  graph is not using NetworkX private storage.
- For `guard_edge_count=False`, keep the current node-only `nodes_seq` path.
- Keep the count-based fallback unchanged for non-native/private-storage cases.

## EV and Score

Extreme-optimization score:

| Candidate | Impact | Confidence | Effort | Score |
| --- | ---: | ---: | ---: | ---: |
| Combined guard-token getter | 3 | 4 | 2 | 6.0 |
| `_native_edges_data_key` materializer pivot | 4 | 3 | 4 | 3.0 |

Both are above the numerical threshold, but the guard token wins this gate
because it is the current bead's narrow drop-in residual, has lower proof
surface, and attacks the common guarded-drain loop. The materializer pivot is a
follow-up candidate after a fresh post-guard profile.

Alien-graveyard EV for the selected lever:

`EV = (Impact 3 * Confidence 4 * Reuse 3) / (Effort 2 * AdoptionFriction 1) = 18.0`.

Rationale: this is not a new algorithmic structure; it is a cache/constants
wall fix at the Python/Rust boundary with a very narrow API wedge and an
existing deterministic fallback.

## Risk Countermeasure and Fallback

- Primary risk: the one-getter path does not beat the constants of two existing
  property reads on the measured interpreter.
  - Countermeasure: same-harness rch hyperfine and cProfile before/after; reject
    if the measured delta does not clear Score >= 2.0.
- Primary correctness risk: missed mutation detection through token collision or
  changed guard timing.
  - Countermeasure: exact token, no hash; capture the expected token at iterator
    creation, as the current code captures `nodes_seq` / `edges_seq`; compare
    before yielding each item.
- Fallback:
  - Missing getter, private storage, or unsupported graph class uses the current
    `nodes_seq` / `edges_seq` or count-based fallback.
  - If validation fails, revert the source hunk and pivot the next pass to the
    data-key materializer residual with the same golden bundle.

## Behavior-Preservation Obligations

- Ordering: unchanged. The lever must not touch `_native_edges_no_data`,
  `_native_edges_with_data`, `_native_edges_data_key`, or any materializer
  traversal. Edge order remains node-major / successor-insertion order.
- Tie-breaking: unchanged and N/A beyond insertion order.
- Floating point: N/A.
- RNG: N/A; graph construction is deterministic and seed-free.
- Guard semantics:
  - Preserve `RuntimeError("dictionary changed size during iteration")` for
    structural edge mutations after iterator capture.
  - Preserve same-count remove/add structural mutation detection through
    `edges_seq`.
  - Preserve attr-only updates as non-structural.
  - Preserve current FNX behavior where isolated node mutation during a guarded
    edge iterator raises; this is a captured baseline difference from NetworkX,
    not a behavior to repair in this bead.
- Private storage: preserve fallback behavior when `_has_networkx_private_storage`
  is true.
- Golden check: `sha256sum -c golden.sha256` must pass before and after.

## Exact Implementation Surface for Pass 3

Allowed files:

- `python/franken_networkx/__init__.py`
  - Touch only `_FailFastEdgeIterator` guard capture/compare logic.
- `crates/fnx-python/src/digraph.rs`
  - Add the exact combined getter for `PyDiGraph` and `PyMultiDiGraph`.
- `crates/fnx-python/src/lib.rs`
  - Add the same getter for `PyGraph` and `PyMultiGraph` only if Pass 3 keeps
    the shared Python branch polymorphic across graph classes.

Forbidden for Pass 3:

- `_native_edges_data_key`.
- `_native_edges_no_data` / `_native_edges_with_data`.
- `edge_py_attrs` layout, data-key caches, EdgeView materializer semantics,
  MultiGraph storage work, or unrelated cleanup.

## Validation Plan

1. Reuse the Pass 1 golden before editing:
   `cd tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon && sha256sum -c golden.sha256`.
2. Build/install through rch with crate scope:
   `rch exec -- maturin develop --release --features pyo3/abi3-py310`.
3. Re-run the harness golden and confirm the bundle SHA remains
   `7f1f79e081e71ab0e4030308a1df76f3419b7a14bc8ee8a3d58ef2aa693aeeea`.
4. Re-run direct timing and rch hyperfine for the same five cases.
5. Re-run cProfile and confirm `_FailFastEdgeIterator` `_gen` falls materially
   while `_native_edges_data_key` is merely recorded as the next residual.
6. Run focused mutation/order tests through the harness plus targeted Python view
   parity tests. Do not run a concurrent full-workspace build.
7. Run crate-scoped checks on touched Rust:
   `rch exec -- cargo check -p fnx-python --lib`,
   `cargo fmt --check --package fnx-python`, and `ubs` on changed files.
8. Keep and commit only if Score >= 2.0; otherwise reject the hunk and route the
   next pass to the data-key materializer with fresh profile evidence.
