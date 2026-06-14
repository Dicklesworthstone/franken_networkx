# Native Approximation Local Node Connectivity

Bead: `br-r37-c1-59ltl`

## Change

Added one safe-Rust `Graph::neighbors_indices` kernel for
`approximation.local_node_connectivity` on plain undirected `Graph` inputs. The
Python wrapper keeps directed, multigraph, private-storage, negative-cutoff, and
non-integer-cutoff cases on the previous path.

## Proof

- Golden rows: 1,447 random/tie/error cases vs NetworkX.
- Golden SHA unchanged:
  `5570c14bb02516d56bbd566aedfea82e68b7491666b3c4bb515adee9aa28fb4b`.
- Ordering/tie-breaking: same White-Newman level-alternating bidirectional BFS,
  native row order from `neighbors_indices`, exact return/error comparison.
- Floating point: N/A, integer connectivity counts only.
- RNG: fixed graph and pair seeds; algorithm itself deterministic.

## Timing

Focused fixture: `gnp_random_graph(1500, 0.01, seed=3)`, pair `(0, 750)`,
2,000 calls per sample.

| Measure | Baseline FNX | Candidate FNX | Speedup |
| --- | ---: | ---: | ---: |
| Direct median | 0.7301003980s | 0.1357297630s | 5.379x |
| Direct mean | 0.7408585946s | 0.1393732631s | 5.316x |
| Hyperfine median | 1.0671266889s | 0.4313233308s | 2.474x |
| Hyperfine mean | 1.0512246928s | 0.4328995071s | 2.428x |

NetworkX direct median on the same fixture was `0.5775424770s`; candidate FNX is
`0.235x` of that direct median. Candidate hyperfine median was `0.4313233308s`
vs NetworkX `1.1183582763s`, or `0.386x`.

## Verification

- `PYTHONPATH=python pytest tests/python/test_approx_bipartite_parity.py tests/python/test_lnc_msg_wording_parity.py tests/python/test_approximation_signature_parity.py -q`
  - `46 passed`
- `rch exec -- cargo check -p fnx-algorithms -p fnx-python --all-targets`
  - passed; existing `fnx-python` dead-code warnings remain.
- `cargo fmt --check --package fnx-algorithms --package fnx-python`
  - failed on pre-existing rustfmt drift tracked by `br-r37-c1-uk5bq`.
- `rch exec -- cargo clippy -p fnx-algorithms -p fnx-python --all-targets -- -D warnings`
  - new kernel lint fixed; remaining failures are pre-existing `fnx-python`
    lint debt tracked by `br-r37-c1-kmlot`.
- `timeout 90s ubs ...changed files...`
  - timed out with exit 124 after starting Python/Rust scans and emitting no
    findings.
