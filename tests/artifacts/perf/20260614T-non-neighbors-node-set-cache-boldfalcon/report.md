# br-r37-c1-khm0p non_neighbors cached node-set fast path

## Target

- Umbrella: `br-r37-c1-04z53`
- Child bead: `br-r37-c1-khm0p`
- Hotspot: `franken_networkx.non_neighbors` for exact `DiGraph` / `Graph`
- Profile-backed residual: directed `non_neighbors` on `n=5000`, degree `8`, node `0`.

## Baseline

Current-head rch scout before source edits:

- FNX `DiGraph` median: `128.60989995533602 us`
- NetworkX `DiGraph` median: `81.54581603594125 us`
- Digest: `67d7931a705e5fca73b5f0582c8aec56e43acabee47f8534670b196d52c6df69`
- Profile: `python/franken_networkx/__init__.py:43944(non_neighbors)` dominated; each call rebuilt the all-node set from native node keys and the neighbor set before subtracting.

## Lever

One Python routing lever:

- Add a `nodes_seq` keyed `_cached_native_node_key_set`.
- For exact plain `DiGraph` / `Graph` with no NetworkX-private storage, copy that cached node set, `difference_update` the native row-key view, then `discard(node)`.
- Keep subclasses, private-storage graphs, and multigraphs on the prior fallback path.

## Isomorphism Proof

- Public output is a set; ordering and tie-breaking are not observable.
- Floating-point and RNG are not involved.
- Directed semantics still subtract successors only, matching NetworkX `graph._adj[node].keys()`.
- Missing-node error parity is preserved by the native row lookup after the upfront `hash(node)`.
- Golden SHA: `41779f04b5b574369e60d6a56b2258e53868bb2051aca1816a05aed5101a7315`.
- A/B digest old-equivalent vs new: `e896991062b969e5923053bf632b372ee3a037a1dae2e0ce0bb87ec9c901855e`.

## Results

Sequential rch harness, same case (`n=5000`, degree `8`, node `0`, loops `3000`, repeats `15`):

- FNX after median: `51.1270610052937 us`
- NetworkX reference median: `75.50090733760347 us`
- After/reference ratio: FNX is `1.4767x` faster than NetworkX.
- Baseline-to-after per-call speedup: `2.5155x`.

Hyperfine process-level A/B, old-equivalent vs new public function (`3000` calls per process, graph construction included):

- Old mean: `668.73540032 ms`
- New mean: `512.89280112 ms`
- Ratio: `1.3039x` faster.

After-profile:

- `3000` calls in `0.147s`.
- `non_neighbors` cumulative time: `0.086s`.
- Remaining dominant cost is `set.copy` (`0.072s`), which is the required result-set materialization.

## Score

- Impact: `2.5155` per-call speedup (`1.3039` process-level hyperfine with construction included)
- Confidence: `4`
- Effort: `1`
- Score: `10.06` per-call (`5.22` by process-level hyperfine)
- Verdict: keep.
