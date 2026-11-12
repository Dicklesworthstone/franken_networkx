# post-ad827 routing and br-r37-c1-p4vaj

## Current-head routing

Fresh rch sweeps after `ad8276627` found no generator gap: all generator rows
were digest-clean and faster than NetworkX except `random_powerlaw_tree`, which
was still slightly faster (`0.9729x` FNX/NX).

Construction exposed the next digest-clean gap:

- `plain_edges_int`: FNX `0.09201724000740796s`, NX
  `0.07492342400655616s`, ratio `1.228150491351757`
- `multigraph_str_keys`: FNX `0.2315471100009745s`, NX
  `0.1896293350000633s`, ratio `1.2210511100558215`

The larger absolute gap was `multigraph_str_keys`. cProfile showed:

- `1.432s` in `_multi_add_edges_from`
- `250000` Python `add_edge` calls
- native batch probes returning immediately

## p4vaj baseline

Golden SHA:

- baseline: `2f618152b0368e463aee43f739f620ed9b8f5debc95e1ad221049fcac153bde2`

Baseline direct timing for 50k `(int, int, str)` keyed edges:

- FNX median: `0.2270639479975216s`
- FNX mean: `0.22732855414090278s`
- NX median: `0.1552442820102442s`
- output digest: `3ac012d38df7f93d58f4c4722f330040b2a1a2a46bfeed839c9f096d7fd9b5e4`

Baseline hyperfine:

- `1.55501070432s +/- 0.04380833708940676s`

## rejected candidates

Candidate 1 routed public keyed batches to the existing
`_native_add_keyed_edges_no_data` set-op primitive. It removed the Python loop
but did not move timing reliably, so it was rejected.

Candidate 2 added a narrower exact-int-node/exact-string-key safe-Rust
collector. It preserved behavior but failed the paired hyperfine gate.

Golden SHA unchanged:

- candidate2: `2f618152b0368e463aee43f739f620ed9b8f5debc95e1ad221049fcac153bde2`

Direct timing improved:

- median: `0.2270639479975216s -> 0.2203008719952777s`
- mean: `0.22732855414090278s -> 0.21321325871810717s`

Profile improved:

- baseline: `2000066` calls in `1.444s`
- candidate2: `46` calls in `1.067s`

Paired hyperfine rejected the source change:

- parent: `1.4770299351199998s +/- 0.03540166987066849s`
- candidate2: `1.53290935352s +/- 0.05171216458269922s`
- hyperfine summary: parent ran `1.04 +/- 0.04x` faster

Verdict: reject and keep no source hunk. The next route is deeper storage work:
avoid per-edge `edge_py_keys` display-key mirroring / public-key representation
cost for exact string-key multigraph construction, instead of adding another
wrapper-level route to the existing keyed batch.
