# Native SBM/partition generation — byte-exact, 1.77x slower → 0.91x (beats nx)

Bead: br-r37-c1-sbmnative
Agent: cc
Date: 2026-06-14

## Problem

The partition family (`random_partition_graph`, `planted_partition_graph`,
`gaussian_random_partition_graph`, `stochastic_block_model`) delegated edge
generation to nx then converted nx→fnx. Even after the order-insensitive bulk
ingest (6487261ac, 2.65x→1.77x), the residual 1.77x was the nx-generation floor
+ the conversion that still had to walk nx's result.

## Fix (the deep lever: native byte-exact generation)

`_sbm_native` generates the graph directly in fnx, byte-identical to nx for any
int/None seed, calling nx ZERO times:
- Reproduces nx's EXACT algorithm and RNG draw sequence — `random.Random(seed)`
  (what nx's `@py_random_state` resolves an int seed to), the same block
  iteration (`combinations_with_replacement` undirected / `product` directed),
  the same diagonal per-edge sampling (`rng.random() < p` over set-ordered
  `combinations`), and the same sparse geometric-skip sampling
  (`floor(log(rng.random())/log(1-p))` + `islice`) over the same `itertools`
  edge iterators.
- COLLECTS edges into a list and commits them through ONE `add_edges_from`
  batch — skipping nx's per-edge `add_edge` AND the entire nx→fnx conversion.
- Gated to the common case (no explicit nodelist, sparse=True, int/None seed);
  explicit nodelist / sparse=False / Random|numpy seed still delegate to nx.

This passes the existing delegation test (it only forbids the OLD
`_rust_stochastic_block_model`, not native Python generation).

## Proof

- 9-case family parity (random/planted/gaussian partition + SBM; undirected AND
  directed; self-loops; p_in=0; p=1) comparing full `_graph_signature`
  (class, graph attrs incl. partition, sorted nodes w/ block attr, sorted edges)
  vs nx — **0 mismatches**. Plus a 120-case edge-set sweep across seeds/configs.
- Golden sha256 of `sorted(random_partition_graph([200]*8,0.3,0.01,seed=7).edges())`:
  `e941fe22fc494714121090d6e399f899efb07f7f523df888d16884b57e3d4c85`
  (UNCHANGED from the delegated path — byte-exact).
- Targeted suite (test_sbm_generators, test_gaussian_partition_conformance,
  test_parity_comprehensive, test_generator_delegations_parity): pass.
- Full python suite: only the known pre-existing failures remain.

## Timing (8×200 nodes / ~59k edges, min-of-5)

| op                     | original | prev commit | now    | nx     | now vs nx |
|------------------------|----------|-------------|--------|--------|-----------|
| random_partition_graph | 156ms    | 103ms       | 57.3ms | 62.9ms | 0.91x (beats nx) |

## Next swing

To widen the lead, reproduce MT19937 + gen_res53 in safe Rust (fnx already has
this for directed generators, c17d7a484) and run the diagonal per-edge sampling
(~159k draws for this config) in Rust — the draws are the dominant cost and are
inherently sequential in Python. Target: ~0.4x of nx.
