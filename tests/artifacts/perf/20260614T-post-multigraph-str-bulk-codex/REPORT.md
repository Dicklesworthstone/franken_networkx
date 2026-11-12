# MultiGraph string-key current-head proof

Commit under test: `95ab0859b314630ac83e672195db9dc25a8b50dc`.

Target: stale ready bead `br-r37-c1-04z53.85`, which described the pre-`95ab0859b`
`MultiGraph.add_edges_from([(int, int, str), ...])` residual.

All proof commands used `PYTHONPATH=python` so the worktree package and
`python/franken_networkx/_fnx.abi3.so` were imported instead of an installed
site-packages wheel.

## Current-head proof

- Golden bundle SHA: `e1eb93d52aa8b9b027d2e8233db864d9b64bb2bc24789d78d987821d7deb55c6`
- Golden cases: all FNX/NetworkX digests match.
- Focus case: `unique_path`, 50,000 keyed edges, 9 loops.
- FNX median: `0.12721630500163883s`
- NetworkX median: `0.1900787230115384s`
- FNX/NX ratio: `0.6692821952192745`
- Focus digest: `0d0ae68ef51dfd6f4ce26a212d3b40d015c5383d498a496b5a0df28f6bded2bc`

The old residual is no longer a live performance gap on the worktree extension.
The profile still identifies `_try_add_str_keyed_edges_from_batch` as the
dominant FNX construction cost, but this case is now faster than the NetworkX
control and retains exact node, edge, key, duplicate-key fallback, tie-break,
RNG, and floating-point semantics.

## Beads note

Attempting to close the stale `br-r37-c1-04z53.85` entry exposed a pre-existing
Beads export collision: `br close` rewrote unrelated `.82-.85/.900x` JSONL
records. That accidental tracker export was reverted and is intentionally not
included here.
