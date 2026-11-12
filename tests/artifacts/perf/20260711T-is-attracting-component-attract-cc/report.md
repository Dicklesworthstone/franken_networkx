# br-r37-c1-attract — `is_attracting_component` validity-guarded integer fast path

Status: **SHIP.** 11.68x median self-speedup, byte-identical (all inputs).

## The target

`is_attracting_component(digraph, component)` checks whether a set of nodes is an
attracting component: every out-edge stays inside, and the component is strongly
connected (forward and backward reachability from `component[0]` both cover it). The
old kernel built a `HashSet<&str>` (`comp_set`) and ran the attracting check +
forward/backward reachability over `successors()`/`predecessors()` (`Vec<&str>`
allocs per pop) with `HashSet<&str>` reachability sets.

## The lever

A **validity-guarded integer fast path**: resolve the component names to indices
ONCE; if all are present (the realistic case — `component` is an SCC of the graph),
run the attracting check + reachability on `Vec<bool>` mark arrays +
`successors_indices`/`predecessors_indices`. If ANY name is absent, fall back to the
exact String kernel (`is_attracting_component_string`).

## Byte-identical argument (all inputs)

- **Fallback** covers the only case the integer path cannot represent: the String
  reachability sets store the missing node NAME (incl. a possibly-invalid
  `component[0]` start), so for any absent name the original kernel runs verbatim →
  identical.
- **Fast path** (all names valid): `comp_set.len()` (distinct names) equals the
  distinct marked-index count (`get_node_index` is injective, so distinct valid names
  ↔ distinct indices; duplicates dedup the same in both). The attracting check
  (`successor ∈ comp`) and the reachable SETS (order-independent) are the same, so the
  three counts and the boolean result are unchanged.

Verified in-test with `assert_eq!(is_attracting_component, is_attracting_component_string)`
across: an attracting cycle (all-valid → `true`, fast path), a non-attracting sub-path
(out-edge leaves → `false`, fast path), and a component containing an absent name
(→ String fallback).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib is_attracting_component_attract_ab -- --ignored --nocapture`

A single directed cycle on n=50000 (whole graph is one attracting SCC); the component
is all n nodes. 61 rounds. Ratio = base/cand, **>1 means the integer fast path is
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **11.6819x** | 61/61 | [8.4123, 15.2752] |
| `NULL_int_vs_int` | 1.0333x | 36/61 | [0.7791, 1.3434] |

The lever median (11.68x) clears the NULL floor: candidate p5 (8.41) is ~6x above the
NULL p95 (1.34), and every one of 61 paired rounds won.

## Gates

- clippy `-D warnings`: clean.
- A/B `cargo test --release` ran clean (ATTRACT_AB line confirmed present — not a
  stale binary); parity across 3 components (incl. the fallback path) green.
- pyo3 `is_attracting_component` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `is_attracting_component` +
  `is_attracting_component_string` (runtime fallback / A/B baseline).
