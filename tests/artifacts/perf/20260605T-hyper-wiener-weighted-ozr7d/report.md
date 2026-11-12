br-r37-c1-ozr7d: weighted Hyper-Wiener native kernel
=======================================================

Target
------

Baseline profile was dominated by Python parity delegation:
`_call_networkx_for_parity -> nx.hyper_wiener_index ->
all_pairs_dijkstra_path_length -> _dijkstra_multisource`.

Lever
-----

Added one native safe-Rust weighted Hyper-Wiener kernel for the parity-safe
surface: simple undirected graphs with string weight attribute values that are
finite, numeric, and nonnegative. Directed graphs, multigraphs, callable or
non-string weights, negative weights, non-finite weights, and nonnumeric weights
continue to delegate to NetworkX.

Benchmarks
----------

Direct rch bench, weighted 80-node fixture:

- Baseline FNX: 0.0102987118 s mean.
- Baseline NetworkX: 0.0088688105 s mean.
- Baseline ratio: FNX / NetworkX = 1.1612280735, so FNX was slower.
- Final FNX: 0.0047560295 s mean.
- Final NetworkX: 0.0087735064 s mean.
- Final ratio: FNX / NetworkX = 0.5420899357, so FNX is 1.845x faster than
  NetworkX on the hot call.
- FNX self-speedup: 2.165x.

Matched process-level rch hyperfine, weighted 80-node fixture with 30 inner
repeats:

- Baseline FNX: 664.9 ms +/- 36.6 ms.
- Baseline NetworkX: 626.4 ms +/- 29.8 ms.
- Final FNX: 407.8 ms +/- 19.9 ms.
- Final NetworkX: 537.7 ms +/- 15.1 ms.
- FNX self-speedup: 1.630x.
- Process-level position moved from NetworkX 1.06x faster to FNX 1.32x faster.

Proof
-----

- `baseline_proof.jsonl`: 12 cases, 0 failures,
  golden `749835d34930e6e683bcb69d4b6aea8d27f1327bb4bc976e534053849cab834b`.
- `final_proof.jsonl`: 12 cases, 0 failures,
  golden `749835d34930e6e683bcb69d4b6aea8d27f1327bb4bc976e534053849cab834b`.
- Final weighted bench digests matched between FNX and NetworkX.
- Bench fixture scalar value: `1476494.0` for both implementations.
- Post-rebase proof stayed unchanged: 12 cases, 0 failures,
  golden `749835d34930e6e683bcb69d4b6aea8d27f1327bb4bc976e534053849cab834b`.
- Post-rebase direct bench: FNX 0.0044529774 s mean, NetworkX
  0.0095007405 s mean, FNX / NetworkX = 0.4686979320 with matching scalar
  digests.
- Final post-rebase2 direct bench after rebasing over `b5f1b3bbc`: FNX
  0.0044897129 s mean, NetworkX 0.0095109645 s mean, FNX / NetworkX =
  0.4720565264 with matching scalar digests.

Validation
----------

- `rch exec -- cargo check -p fnx-algorithms --all-targets`: pass.
- `rch exec -- cargo check -p fnx-python --all-targets`: pass.
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`:
  pass.
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`: pass.
- `cargo fmt -p fnx-algorithms -p fnx-python --check`: pass.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: pass.
- `pytest tests/python/test_wiener_index_conformance.py -q`: 315 passed.
- Post-rebase `rch exec -- cargo check -p fnx-algorithms --all-targets`: pass.
- Post-rebase `rch exec -- cargo check -p fnx-python --all-targets`: pass.
- Post-rebase `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`:
  pass.
- Post-rebase `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`:
  pass.
- Post-rebase `cargo fmt -p fnx-algorithms -p fnx-python --check`: pass.
- Post-rebase `rch exec -- maturin develop --release --features pyo3/abi3-py310`:
  pass.
- Post-rebase `pytest tests/python/test_wiener_index_conformance.py -q`: 315 passed.
- Final post-rebase2 `rch exec -- cargo check -p fnx-python --all-targets`: pass.
- Final post-rebase2 `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`:
  pass.
- Final post-rebase2 `cargo fmt -p fnx-algorithms -p fnx-python --check`: pass.
- Final post-rebase2 `rch exec -- maturin develop --release --features pyo3/abi3-py310`:
  pass.
- Final post-rebase2 proof: 12 cases, 0 failures, golden
  `749835d34930e6e683bcb69d4b6aea8d27f1327bb4bc976e534053849cab834b`.
- Final post-rebase2 `pytest tests/python/test_wiener_index_conformance.py -q`: 315 passed.
- `timeout 240 ubs <all touched files>`: timed out in the Python scanner after
  completing Rust; no finding was emitted before timeout.
- `timeout 210 ubs <Rust touched files>`: completed with exit 1 due existing
  scanner debt and a false-positive critical on
  `new_group_id != group_of[i]` in the unrelated modularity/community code.
  No Hyper-Wiener weighted lines were reported.

Score
-----

Impact 4.0 x Confidence 4.0 / Effort 2.0 = 8.0. Kept.
