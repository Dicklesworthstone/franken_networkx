# Mutation partial-error-state batch 2 (Phase B matrix sweep)

## Method
Generalized the baqyi probe recipe to the OTHER mutation families:
14 malformed-mid-bunch cases x 4 classes x full state (error
type+message, node set+attrs, edge set with keys/data). 18 divergences
found; all fixed.

## Bug classes fixed
1. remove_edges_from screened/normalized the whole bunch and SILENTLY
   DROPPED malformed elements while removing everything else (1-tuple
   and unhashable-mid cases removed ALL valid edges and returned
   success; nx raises at the bad element with only the prefix
   removed). Wrapper now scans inline-style: nx error shapes
   reproduced per class (e[:2] subscript TypeError, unpack ValueError,
   the Multi remove_edge() missing-argument TypeError, unhashable
   TypeError), prefix bulk-removed, then raise.
2. remove_nodes_from's whole-bunch hash gate (br-r37-c1-i9whv) raised
   BEFORE removing anything; nx removes the prefix first. Inline scan
   + prefix bulk + raise.
3. add_edge u-before-v: nx creates node u before examining v in ALL
   FOUR classes — bad v (None or unhashable) leaves u behind. Fixed
   the shared Python wrapper (both branches), the PyMultiGraph raw
   binding (kt0vp exposes it directly), and the auto-key wrapper's
   get_edge_data probe (now falls through on TypeError instead of
   pre-empting the partial-state path). Also covers
   update(edges=...) via the add path.

## Proof
Mutation matrix: 18 -> 0 divergences; add_edge matrix sha c8289ec4
0 failures; 48 committed tests; full pytest 21757 passed, 0 failed.
