# br-r37-c1-lnrxj - k_components complete graph fast path

## Target

`franken_networkx.k_components` delegated every input to NetworkX. The profile-backed gap was dense/high-connectivity graphs where NetworkX's Moody-White path still builds flow auxiliaries even though complete simple graphs have a closed-form k-component lattice.

One lever only: exact `Graph` complete-simple-graph shortcut.

## Baseline

Environment:

- Worktree: `/data/projects/.scratch/franken_networkx-boldfalcon-lnrxj-20260609`
- Base commit: `5cbd89b6966d05cebea62d4532e3c722a09c173c`
- Runtime: scratch venv `/data/projects/.scratch/venvs/fnx-lnrxj-boldfalcon`
- Build: `rch exec -- maturin develop --release --features pyo3/abi3-py310`

Profile, `fnx.k_components(fnx.complete_graph(250))`:

- `3,476,600` calls in `1.064s`
- Top frame: `_call_networkx_for_parity`
- NetworkX `node_connectivity` + auxiliary/residual flow construction dominated the complete-graph case.

Hyperfine via `rch exec -- hyperfine`, `K300`, two calls per run:

- FNX baseline: `1.628396543155s +/- 0.16975944923708639s`
- Genuine NetworkX comparator: `1.660s +/- 0.240s`

## Change

For exact simple undirected `Graph` inputs:

1. Return `{}` for `n < 2`.
2. Require `number_of_edges() == n * (n - 1) // 2`.
3. Require `number_of_selfloops(G) == 0`.
4. Return `{k: [set(nodes)] for k in range(n - 1, 0, -1)}`.

All directed, multigraph, self-loop density trap, and non-complete cases still delegate to NetworkX.

## Isomorphism Proof

- Ordering preserved: complete graph keys descend from `n - 1` to `1`, matching NetworkX reconstruction order.
- Tie-breaking unchanged: complete graph has one maximal component at every emitted k level.
- Container shape preserved: `dict[int, list[set[node]]]`; each level receives a fresh set.
- Floating-point: N/A.
- RNG: N/A.
- Flow function behavior: NetworkX does not call `flow_func` on complete graphs; the fast path also ignores it only under the complete-graph predicate.
- Negative guards: directed inputs still raise `NetworkXNotImplemented`; density-1 self-loop case still delegates and returns `{1: [{0, 1, 2}]}`.

Golden SHA:

- Baseline proof: `9f1b610e89cc3f3c0dc8313df87e6814ffe2808d23208a1ca8d5112a4eea9294`
- After proof: `9f1b610e89cc3f3c0dc8313df87e6814ffe2808d23208a1ca8d5112a4eea9294`

## After

Profile, `fnx.k_components(fnx.complete_graph(250))`:

- `42` calls in `0.002s`
- No NetworkX delegation on the complete-graph path.

Hyperfine via `rch exec -- hyperfine`, `K300`, two calls per run:

- FNX after: `0.3495474418400001s +/- 0.0389991602715707s`
- Same-worker speedup vs FNX baseline: `4.66x`
- Speedup vs genuine NetworkX comparator: `4.75x`

Score:

- Impact `4`
- Confidence `5`
- Effort `2`
- Score `(Impact * Confidence) / Effort = 10.0`

## Alien Primitive Routing

Recommendation card:

- Primitive: certificate/closed-form graph-theory shortcut before expensive flow/cut recursion.
- Source lineage: alien graveyard graph proof contracts and max-flow/min-cut certificate routing; use algorithmic certificates and exact graph-regime predicates before entering generic flow algorithms.
- Fallback: delegate to NetworkX for every input outside the strict complete-simple-graph certificate.
- Next target after re-profile: low-k decomposition or flow-call reduction for non-complete dense components; do not generalize this shortcut without a certificate predicate and golden-output SHA.

## Gates

Passed:

- `python -m py_compile python/franken_networkx/__init__.py tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-k-components-boldfalcon/harness_k_components.py`
- `pytest tests/python/test_tree_kcomponents_assortativity_conformance.py tests/python/test_collection_container_type_parity.py -q` -> `83 passed`
- `rch exec -- cargo check -p fnx-python --all-targets`
- `ubs tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-k-components-boldfalcon/harness_k_components.py` -> no critical/warning issues
- `sha256sum -c tests/artifacts/perf/20260609T-k-components-boldfalcon/proof_files.sha256`

Blocked by pre-existing unrelated Rust drift:

- `cargo fmt -p fnx-python --check` reports formatting diffs in untouched Rust files.
- `cargo clippy -p fnx-python --all-targets --no-deps -- -D warnings` reports existing `collapsible_if` findings in untouched Rust files and dependency warnings in `fnx-generators`.
- `ubs python/franken_networkx/__init__.py` timed out at 180s without emitted findings; this is the known large-wrapper UBS limitation for this repo.
