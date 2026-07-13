# br-r37-c1-voterankidx — voterank: String-keyed O(V·E) kernel → integer-index adjacency + O(V) max pick

Status: **SHIP.** 32.9191x, byte-identical, STRICT gate by a mile.

## The target

`voterank` (influence ranking) runs up to |V| rounds; each round accumulates votes over every edge and selects
the top-scoring node. The kernel kept `vote_power`/`scores` as `HashMap<&str, f64>` and `selected` as
`HashSet<&str>`, so it paid a **String hash on every per-edge vote accumulation and every per-neighbour
decrement across all |V| rounds** — O(|V|·|E|) String hashes. It ALSO **sorted every scored node each round**
(`candidates.sort_by(...).first()`, O(|V| log|V|)) merely to pick the single maximum.

## The lever (two byte-identical fixes)

1. **Integer index.** Build the integer adjacency ONCE (`adj[i]` in `neighbors_iter` order), then run the
   whole loop over `Vec<f64>` (vote_power, score) and `Vec<bool>` (selected) indexed by node index — zero
   String hashing in the hot loop. A `scored`/`touched` scratch reproduces the HashMap's "entry exists" set
   (a node is a candidate iff it received ≥1 vote this round, even if the sum is 0.0).
2. **Sort → max.** Replace the per-round full sort with a single O(|V|) `max_by` (same key: max score, ties by
   min node name).

## Byte-identical argument

Per-node scores accumulate in the same node-index order (outer `0..n`, inner `adj[node]` == `neighbors_iter`
order) → the same f64 sum (ULP-identical). The winner is the same: `sort_by(DESC score, ASC name).first()` ==
`max_by(score, then min name)`. Decay update, `selected`, and `edges_scanned` (counted at the same point) are
unchanged. Verified: the A/B asserts `old_fn(&g) == super::voterank(&g, None)` on the **full `VoterankResult`
(ranked + witness, including `edges_scanned`)** — inline String-keyed kernel vs the shipped index kernel — on a
2000-node graph.

## Median A/B (full function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib voterank_idx_ab -- --ignored --nocapture`

Circulant (2000 nodes, degree 20 → ~20k edges); voterank ranks all |V| nodes → |V| rounds. 61 rounds. Ratio =
String / index, **>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INDEX_vs_string` | **32.9191x** | 61/61 | [28.6845, 38.8395] |
| `NULL_index_vs_index` | 0.9886x | 25/61 | [0.8179, 1.1524] |

Decisive beyond question: candidate p5 (28.68) is ~25x above the null p95 (1.15); all 61 rounds won; null
centred on 1.0. Huge because the String hashing ran O(|V|·|E|) times (|V| rounds × every edge) — eliminating it
plus the per-round sort→max collapse dominates.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `voterank_generic` (serves `voterank` + `voterank_directed`).
- Test-only: `voterank_idx_ab` A/B.

## Notes

- SHARED-FILE DISCIPLINE: a peer had concurrent uncommitted work (`global_node_connectivity`) in the same file.
  Committed ONLY my two hunks via a filtered `git apply --cached`; peer hunks left untouched.
- LEVER: a String-keyed (`HashMap<&str,_>`/`HashSet<&str>`) accumulate-and-select loop that runs O(rounds ×
  edges) → build int adjacency once + Vec-indexed state. The cc String→int vein still has residuals on
  *iterative* multi-round kernels (not just single-pass ones). Also: a per-round `sort().first()` is a max
  pick in disguise — O(n log n) → O(n).
