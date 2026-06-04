## Recommendation: Maximal Independent Set Indexed Blocking

- Bead: `br-r37-c1-dxm71`
- Profile target: public `maximal_independent_set` on BA(3000, 4, seed=42), `seed=1`.
- Baseline evidence: clean-HEAD build from `/data/tmp/fnx-mis-baseline-20260602T1932`, `baseline_fnx.jsonl`, `profile_baseline_fnx.txt`.
- Symptom: fnx remains slower than NetworkX on the seeded MIS workload; the previous Rust/PyO3 route cloned string nodes and rebuilt Python lists for `random.choice` during the greedy peel.
- Graveyard primitive: flat indexed data layout + bitmap state. The alien catalog's "constants kill you" guidance and memory-efficient indexed-data entries apply directly: replace string-keyed hash/blocking state with dense indices and a `Vec<bool>` bitmap while preserving the interface.
- One lever: use `random._randbelow(len)` to preserve NetworkX's random index draw without cloning candidate nodes into a Python list, then run the greedy loop on node indices with prebuilt adjacency and `Vec<bool>` blocked state.
- Keep score: Impact 2 x Confidence 4 / Effort 1 = 8.0 (threshold >= 2.0).
- Fallback / next lever: public wrapper self-loop pre-scan is now the visible Python-side cost; optimize that separately only after a new bead/profile.
