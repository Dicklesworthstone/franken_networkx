# Negative-Evidence Ledger — copy() data-structure bound + sweep false-losses

- Agent: `BlackThrush` · 2026-06-20 · Base origin/main `1226171f1`
- Outcome: **no ship** (reverted); recorded as negative evidence + methodology.

## 1. MultiGraph / MultiDiGraph `copy()` — String-keyed inner-clone bound

Confirmed losses (warm min-of-15, 5 warmup):

| copy() | no-attr | with-attr |
| --- | ---: | ---: |
| Graph | 13.4x WIN | 4.25x WIN |
| DiGraph | 3.78x WIN | 2.36x WIN |
| MultiGraph | 0.82x | 0.64x |
| MultiDiGraph | 0.54x | 0.44x |

Simple Graph/DiGraph copy WINS big (integer-CSR inner clone). The MultiGraph
family loses because `MultiDiGraph`/`MultiGraph` store adjacency as fully
String-keyed nested `IndexMap<String, IndexMap<String, IndexSet<usize>>>` for BOTH
successors and predecessors, plus `edges: IndexMap<EdgeKey, IndexMap<usize,
AttrMap>>` — so `clone_with_fresh_policy` deep-clones the edge set THREE times
over (succ + pred + edges), each String-keyed, even for attr-less graphs. That
clone is the whole gap; a Rust clone ends up slower than nx's Python dict copy.

### Rejected lever: transpose `reorder_pred_rows_for_nx_copy_walk`

The MultiDiGraph copy walk reorders pred rows via per-edge `get_index_of`
lookups + per-row sort (String-keyed; the DiGraph version is pure-integer). I
rewrote it as a single O(|V|+|E|) transpose walk (append `u` to `v`'s pred order
while walking successors in order) — byte-identical pred order, asymptotically
better. **Parity 0/500** (node/succ/pred order + edges/keys/attrs). But it
delivered **NO measured copy win** (MDG 0.54x→0.57x, hub-heavy 0.52x→0.52x):
reorder is never the bottleneck, the 3× inner clone is. Reverted to avoid churn
in shared `fnx-classes/digraph.rs` for zero measured benefit.

**Next route:** the real lever is migrating `MultiDiGraph`/`MultiGraph` to
integer-CSR adjacency rows (as DiGraph already did under br-r37-c1-d58s8), so the
copy clones integer Vecs instead of String IndexMaps — a large data-structure
change, not a binding tweak.

## 2. Quick-sweep FALSE losses (methodology)

A low-warmup sweep (reps=7, 2 warmup) reported several losses that are actually
big WINS under warm min-of-15 / 5-warmup measurement:

| function | quick sweep | warm truth |
| --- | ---: | ---: |
| `onion_layers` | 0.19x | **6.4–9.5x WIN** |
| `k_core` | 0.52x | **32x WIN** |
| `core_number` | (n/a) | **9.6x WIN** |

Lesson (reinforces the gauntlet methodology): single-shot / low-warmup sweeps
LIE under host noise and cold BLAS/alloc. Always re-confirm a candidate loss
with warm min-of-N (≥15 reps, ≥5 warmup) BEFORE investing in a fix. Real,
stable losses that survived re-measurement: `simple_cycles` (0.57x, delegated —
order-blocked by Johnson's-algorithm iteration order) and the `copy()` family
above.
