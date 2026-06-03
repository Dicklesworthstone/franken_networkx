# br-r37-c1-04z53.30 Benchmark Report

## Target

- Profile-backed bead: `br-r37-c1-04z53.30`
- Hot path: `ego_graph(Graph, 0, radius=2)` on BA(3000, 4, seed=42)
- Baseline profile: 9 `ego_graph` calls took 0.344s cumulative; wrapper `Graph.add_edges_from` took 0.147s cumulative, raw `Graph.add_edges_from` took 0.083s, and `EdgeDataView._materialize` took 0.067s.

## Candidate Lever

Exact simple-Graph native filtered copy for empty-edge-data ego subgraphs. The candidate bypassed Python `EdgeDataView._materialize()` and generic `add_edges_from` for eligible empty-edge copies, with fallback for attr-bearing edges.

## Baseline

- Direct rch sample: mean `0.03052246606287857s`, median `0.029286545992363244s`.
- NetworkX oracle sample: mean `0.024068877199897542s`, median `0.022783827007515356s`.
- Hyperfine via rch: mean `0.6168774760771429s`, median `0.6052672812200001s`, stddev `0.017484444187302432s`.
- Golden digest: `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.

## Candidate Result

- Direct rch sample: mean `0.03164971126631523s`, median `0.03150239502429031s`.
- Hyperfine via rch: mean `0.6682278137428571s`, median `0.6809540886000001s`, stddev `0.026845224728997755s`.
- Profile via rch: sample mean improved from `0.0414389081124682s` to `0.03368763999767705s`, but the direct and hyperfine wall-clock gates regressed.
- Golden digest: `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.

## Delta

- Direct sample mean: `0.03052246606287857s -> 0.03164971126631523s`, 3.69 percent slower.
- Hyperfine process mean: `0.6168774760771429s -> 0.6682278137428571s`, 8.32 percent slower.

## Verdict

Rejected. Score 1.0, below the required `>= 2.0` threshold. Candidate source and tests were manually removed; no code from this lever is kept.
