# quotient_graph default edge bucket benchmark

Bead: `br-r37-c1-f9gp2`

Target: `franken_networkx.quotient_graph` default simple undirected path.

Profile-backed baseline:

- Workload: deterministic sparse `Graph` with 3000 nodes, block size 10, 9000 random extra edges, default `edge_relation`, default `edge_data`, default `weight="weight"`.
- Baseline cProfile: `quotient_graph` spent `50.402s` cumulative under profiling, with `edge_relation` at `26.108s` and `has_edge` at `29.555s`.
- Baseline direct sample: FNX `13.891540272015845s`, NetworkX `2.264723750005942s`.
- Baseline hyperfine: `14.456043538793333s +/- 0.3069310495244863s`.

Lever:

- Build a node-to-block index once for the default simple undirected path.
- Scan source edges once and bucket cross-block integer/default weights by block pair.
- Add quotient edges in first-insertion block-pair order.
- Keep directed graphs, multigraphs, custom `edge_relation`, custom `edge_data`, explicit `create_using`, and non-integer explicit weights on the prior exact path.

After:

- Direct FNX sample: `6.937076761008939s`.
- Direct speedup: `2.002506351103925x`.
- NetworkX after sample: `2.265047003980726s`.
- Hyperfine after: `7.548245371766666s +/- 0.15910832077723788s`.
- Hyperfine speedup: `1.9151528370903896x`.
- After cProfile: `edge_relation` and `has_edge` disappeared from the top 40; the shifted hotspot is default node-data subgraph/density work.

Keep score:

- Impact: 4
- Confidence: 5
- Effort: 2
- Score: `10.0`

Artifacts:

- `baseline_bench.jsonl`
- `after_bench.jsonl`
- `baseline_cprofile.txt`
- `after_cprofile.txt`
- `hyperfine_baseline.json`
- `hyperfine_after.json`
