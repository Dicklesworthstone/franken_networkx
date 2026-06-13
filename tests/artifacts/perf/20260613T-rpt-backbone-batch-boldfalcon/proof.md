# br-r37-c1-04z53.81 Proof

## Change
- Lever: in `degree_sequence_tree`, replace `add_path(graph, range(backbone_nodes))`
  with bulk `add_nodes_from(range(backbone_nodes))` plus one
  `add_edges_from(zip(range(backbone_nodes - 1), range(1, backbone_nodes)))`.
- Scope: one construction lever only. The random sequence generation and leaf-edge
  batching from the prior pass are unchanged.

## Profile Evidence
- Current-head baseline profile:
  `baseline_profile_fnx.txt`.
- Hot frames for `random_powerlaw_tree(n=300, gamma=3, seed=5, tries=1000)`:
  `degree_sequence_tree` remains the top residual construction frame and
  `add_path` performs 137 Python `Graph.add_edge` calls.
- Candidate profile:
  `candidate_profile_fnx.txt`.
- Mechanism delta:
  total calls `9025 -> 8588`; Python `Graph.add_edge` calls `137 -> 0`;
  `add_path` frame removed; backbone construction now reaches two bulk
  `add_edges_from` calls total for backbone and leaves.

## Benchmarks
- Baseline FNX direct median: `0.001033469001413323s`.
- Candidate FNX direct median: `0.0005983739974908531s`.
- Direct speedup: `1.7271288621279386x`.
- Baseline FNX direct mean: `0.0010914282554272087s`.
- Candidate FNX direct mean: `0.0006236596091184765s`.
- Direct mean speedup: `1.7500383854742632x`.
- Hyperfine command mean: `0.32209217415999997s -> 0.2997860991s`
  (`1.0744066356877986x`).
- Score: `1.7271288621279386 * 4 / 1 = 6.908515448511754`, keep.

## Isomorphism Proof
- Ordering preserved: yes. `add_path(range(backbone_nodes))` creates nodes
  `0..backbone_nodes-1` and then edges `(0,1), (1,2), ...`. The replacement
  inserts nodes in the same `range` order and inserts the same edge pairs from
  the `zip` iterator in the same order.
- Tie-breaking unchanged: yes. `degree_sequence_tree` still sorts the same
  filtered degree list and consumes it with the same `pop()` loop for leaves.
- Floating-point: N/A.
- RNG: unchanged. The change occurs after `random_powerlaw_tree_sequence`
  returns its degree sequence and does not call or inspect the RNG.
- Golden output: baseline and candidate golden files are byte-identical.
  FNX SHA and NetworkX SHA both remain
  `9acb9600008103deee5400c8f4c3b8354aedf03072c9a4c936cdbaa024d92aec`.
- Edge-order check: first and last edge slices in baseline and candidate
  golden output are identical.

## Verification
- `PYTHONPATH=python python3 -m py_compile python/franken_networkx/__init__.py`: passed.
- Focused pytest via rch: `4 passed`.
- Direct Graph/MultiGraph parity probe:
  `14` cases passed; digest
  `783edacc4758c701b26eb7da867be6d9659aa279a15c303484792ba31cd84617`.
- `rch exec -- cargo check -p fnx-python --lib`: passed. The first worker
  failed sync and rch fell open to local execution; the crate-scoped command
  completed successfully.
- Post-rebase golden check after rebasing over `origin/main` commit
  `4e51d79ce`: passed; FNX SHA and NetworkX SHA remain
  `9acb9600008103deee5400c8f4c3b8354aedf03072c9a4c936cdbaa024d92aec`.
- Post-rebase focused pytest via rch: `3 passed`.
- `git diff --check`: passed.
- `cargo fmt -p fnx-python --check`: blocked by pre-existing Rust formatting
  drift in `crates/fnx-python/src/{algorithms.rs,digraph.rs,lib.rs,readwrite.rs}`.
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings`: remote run
  failed on pre-existing `fnx-generators` unused-return warnings at
  `crates/fnx-generators/src/lib.rs:{538,621,666,6218,6758}`.
- `ubs python/franken_networkx/__init__.py`: interrupted after hanging for
  several minutes on the single-file Python scan; no findings were emitted.

## Graveyard Contract
- Mapped primitive: batched/vectorized hot-path construction and cache-local
  construction discipline from the canonical graveyard docs. This targets the
  measured per-edge Python call overhead directly.
- Baseline comparator: current FrankenNetworkX random-powerlaw generator after
  `br-r37-c1-04z53.79`, with NetworkX timing recorded as control.
- Budgeted mode: no runtime fallback or adaptive policy added; if the bulk
  insertion fails to preserve parity, reject the lever.
- Fallback trigger: any golden SHA mismatch, edge-order mismatch, focused parity
  failure, or direct benchmark score below `2.0`.
- Rollback: `git revert <commit>`.
- IP status: no external implementation imported.
