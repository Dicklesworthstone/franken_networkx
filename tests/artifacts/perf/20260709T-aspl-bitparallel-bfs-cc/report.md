# Bit-parallel multi-source BFS for `average_shortest_path_length` — 3.65× vs ORIG

**Agent:** CopperCliff · **Date:** 2026-07-09 · **Crate:** `fnx-algorithms`
**Kernel:** all-pairs unweighted distance-sum behind `average_shortest_path_length`
(+ `_directed`).

## Why this seam

`docs/NEGATIVE_EVIDENCE.md` showed the Python-level "per-edge `add_edge` →
one `add_edges_from`" batch-commit lever mined out (every generator/operator
converted). Re-profiled for a **structurally different primitive class**
(per the alien-graveyard / extreme-optimization brief): a
**SIMD-within-register bit-parallel multi-source BFS** — a data-layout /
succinct-bitset transform on a hot pure-Rust kernel benched in
`crates/fnx-algorithms/benches/algorithm_benchmarks.rs`
(`average_shortest_path_length/grid/{400,900,1600}`).

## The transform

Instead of one BFS per source (`n` sweeps of the whole graph), process
`W*64` sources at once. Each node carries a `[u64; W]` **bitset column**
(`seen`/`frontier`/`next`) where bit `j` means "source #j has reached me". A
frontier expansion becomes a word-parallel `frontier[v] & !seen[w]` over the
column, so **one contiguous edge scan advances up to `W*64` sources**. This
collapses the number of full graph traversals from `n` to `ceil(n/(W*64))`.

- **Compact `u32` CSR built once** (halves hot-loop memory traffic vs `usize`).
- **Lane width `W` (1..=8, i.e. 64..512 sources/batch)** chosen as the widest
  single batch that covers all `n` sources — fewer, wider batches ⇒ fewer
  traversals (the source of the win). Const-generic `W` so the inner loop
  unrolls.
- **Deferred popcount (critical perf lever):** the first cut popcounted per
  *edge* scan (`W × count_ones` per neighbour). On the generic release target
  (no hardware `popcnt`) that dominated — `grid/400` was only 0.93 ms (1.28×).
  Moving the popcount to **once per reached-node per level** (over `next_nodes`,
  not over `|E|`) leaves the `O(|E|)` inner loop as pure word AND/OR and drops
  `grid/400` to 0.327 ms.

## Byte-identical (not an approximation)

The distance SUM is an integer accumulated as `level * popcount(newly_reached)`
over every (source, node) first-reach event, so the result is **bit-for-bit
identical** to the per-source BFS regardless of batch width or reduction order
(integer addition is associative/commutative). Connectivity is exact:
`reached_pairs == n*n` ⟺ every source reaches every node, matching the old
"any source reached `< n` → `INFINITY`" contract.

## Scope: sequential path only (`n < 500`)

Bit-parallel is a **single-threaded algorithmic** win. For `n ≥ 500` the
pre-existing per-source path fans out over rayon, and on a many-core rch worker
that embarrassing parallelism (900–1600-way) beats one wide sequential sweep
(measured: a batch-parallel bit-parallel `grid/1600` ran 6.16 ms ≫ ORIG rayon
1.63 ms). So `n ≥ 500` **keeps the rayon per-source path unchanged — no
regression** — and only `n < 500` takes the bit-parallel path.

## Measurement (per-crate `cargo bench`, `--profile release`)

`CARGO_TARGET_DIR=/data/projects/.rch-targets/networkx-cc rch exec -- cargo bench
-p fnx-algorithms --profile release --bench algorithm_benchmarks`, back-to-back
same-session A/B (stash ORIG → measure → pop → measure NEW), `--sample-size 50
--measurement-time 2.5`:

| benchmark | ORIG | NEW | ratio (ORIG/NEW) |
|---|---|---|---|
| `average_shortest_path_length/grid/400` (n=400, **sequential**) | 1.1946 ms [1.189, 1.201] | **327.38 µs** [326.3, 328.7] | **3.65×** |
| `grid/900` (n=900, fallback path) | 603 µs | 546 µs | ~1.0× (unchanged, within noise) |
| `grid/1600` (n=1600, fallback path) | 1.634 ms | 1.593 ms | ~1.0× (unchanged, within noise) |

Both `grid/400` CIs are <1 % spread. `grid/900` and `grid/1600` take the
unchanged per-source rayon fallback (no regression).

Standalone prototype (single-threaded, `-C target-cpu=native`) showing the win
scales with lower diameter — real motivation for the sibling closeness kernel:

| shape | old per-source BFS | bit-parallel | ratio |
|---|---|---|---|
| grid 20×20 (n=400) | 0.91 ms | 0.31 ms | 2.9× |
| complete 100 (diam 1) | 0.46 ms | 0.04 ms | ~12× |
| random n=1000 avgdeg 8 | 17.9 ms | 1.4 ms | ~13× |
| random n=2000 avgdeg 6 | 75.7 ms | 5.9 ms | ~13× |

## Correctness

- 6 new differential/property tests (`bitpar_aspl_tests`): bit-parallel vs an
  independent `HashMap`-per-source reference, **byte-for-byte via `to_bits`**
  across lane widths `W=1..8`; directed-cycle closed form `C_n → n/2`;
  disconnected / not-strongly-connected → `INFINITY`; trivial graphs → 0.0.
- `895` `fnx-algorithms` tests green.
- Python: `average_shortest_path_length` == networkx exactly (grid 20×20 →
  `13.333333333333334`); `96` distance/shortest-path conformance tests green.
- 3 unrelated Python failures (`write_gexf` / `find_induced_*` / `read_edgelist`
  export classification + coverage-matrix-doc currency) are **pre-existing** and
  from a concurrent agent's (`CyanGrove`) uncommitted `__init__.py` edits, not
  this change. This diff is `crates/fnx-algorithms/src/lib.rs` only.

## General lever

All-pairs unweighted BFS reductions (aspl, closeness, harmonic) whose per-source
result is an integer / order-independent function of `(distance, reached)` can be
bit-parallelised: `W*64` sources per traversal, byte-identical, single-threaded.
Wins where the graph is small enough that the per-source rayon path underutilises
(`n < ~500`) **or** the diameter is low. **Next sibling:**
`closeness_centrality` (benched on `complete(20/50/100)`, all `n < 500`
sequential, diameter-1 = bit-parallel's best case; prototype ~11–17×). Keep
popcount off the `|E|` loop; pick lane width = widest single batch; `u32` CSR
once.
