# br-r37-c1-e92fj pass 15: public native Louvain route kept

## Candidate

Route `fnx.community.louvain_communities` to `_fnx._raw_louvain_communities`
for the proven simple unweighted surface:

- concrete `fnx.Graph`
- integer non-negative seed representable by the native `u64` seed bridge
- string `weight` whose attribute is absent from every edge
- finite numeric `resolution` and non-negative finite `threshold`
- `max_level is None` or a positive integer
- non-empty graph with no self-loops

Everything outside that guard stays on the previous NetworkX parity path. The
native Louvain algorithm itself is unchanged in this pass.

## Baseline

- Build: `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- Profile: `baseline_profile_public_ws300.txt`
- Golden: `baseline_golden.json`
- Golden SHA: `1dd7f298d9cbd2c83a3722c6abf2e73216c3dc897171cfbfcfa492ab142e8d28`
- Hyperfine public `ws300`, repeat 20: mean `0.68320988156s`, median `0.64959633866s`
- Hyperfine raw comparator `ws300`, repeat 20: mean `0.34130422202s`, median `0.33806630532s`
- In-process loop public mean: `0.015386754200153518s`
- In-process loop raw mean: `0.002741247849917272s`

The public profile showed the route cost was dominated by `_networkx_graph_for_parity`
plus NetworkX's Python Louvain loop.

## Candidate Results

- Golden: `candidate_route_golden.json`
- Golden SHA: `1dd7f298d9cbd2c83a3722c6abf2e73216c3dc897171cfbfcfa492ab142e8d28`
- Hyperfine public `ws300`, repeat 20: mean `0.35787979248s`, median `0.35258236118s`
- In-process loop public mean: `0.003287754749908345s`
- Partition digest unchanged: `541d40853e2d6abc0ef40ad863edfaad96d1e4dc64020ee31029c05af34b3ad8`

Speedups:

- Process hyperfine: `1.91x` (`0.68320988156s -> 0.35787979248s`)
- In-process public loop: `4.68x` (`0.015386754200153518s -> 0.003287754749908345s`)

## Isomorphism Proof

- Ordering preserved: the pass-14 native kernel already matches NetworkX/public
  partition order on the fixed Louvain corpus; pass 15 only routes the public
  wrapper to that kernel under the proven simple surface.
- Tie-breaking unchanged: native gain comparison, RNG shuffle, and output
  conversion are unchanged from pass 14.
- Floating-point: no formula or accumulation order changed in this pass.
- RNG seeds: only exact integer seeds in the native seed range are routed; `None`,
  bools, arbitrary random-state objects, negative integers, and oversized
  integers stay on NetworkX.
- Golden outputs: `sha256sum -c baseline_golden.sha256` and
  `sha256sum -c candidate_route_golden.sha256` passed.

## Validation

- `rch exec -- python -m compileall -q python/franken_networkx/community.py ...`: passed.
- `pytest tests/python/test_community_extras.py -k 'louvain' -q`: passed, 6 tests.
- `pytest tests/python/test_community_conformance_matrix.py -k 'louvain' -q`: passed, 3 tests.
- `pytest test_review_mode_regression_lock.py::test_fnx_community_louvain_communities_uses_fnx_wrapper test_parity_conformance.py::TestCommunityParity::test_louvain_communities -q`: passed, 2 tests.
- `rch exec -- cargo check -p fnx-python --lib`: passed. It still reports
  pre-existing `fnx-generators` unused-result warnings outside this Python hunk.
- `git diff --check`: passed.

## Score

Impact `5` x Confidence `5` / Effort `2` = `12.5`.

The route removes the final `br-r37-c1-e92fj` public Louvain gap for the
profiled simple unweighted seeded surface while preserving the fallback for
unproven seed/weight/self-loop surfaces.
