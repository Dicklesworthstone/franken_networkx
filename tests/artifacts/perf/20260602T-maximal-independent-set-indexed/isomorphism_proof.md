## Change: Maximal Independent Set Indexed Blocking

- Ordering preserved: yes. Candidate indices are initialized from `ordered_nodes` in the same order as the previous `available_nodes` vector, and `retain` preserves relative order after each blocked-node removal.
- Randomness preserved: yes. `random.choice(seq)` chooses `seq[random._randbelow(len(seq))]`; the new path calls `_randbelow` exactly once per previous `choice` call and uses the returned index directly.
- Tie-breaking preserved: yes. Required seed nodes are deduplicated in the same order, candidate filtering preserves prior order, and greedy picks occur at the same candidate positions.
- Floating point: none.
- Error behavior: subset, non-independent seed nodes, directed rejection, self-loop handling, empty graph `IndexError`, negative/large/NaN seed wrapper behavior are unchanged.
- Golden output: clean-HEAD fnx, after fnx, and NetworkX all produced digest `ea0fa182a585f7750142786815e6c267df0a3cf238e1d3d2427ba525de378909` on BA(3000, 4, seed=42), `mis_seed=1`. All three results were independent and maximal.
- Current sampled-call benchmark: clean-HEAD fnx `0.077223609777 s` -> after fnx `0.068566889446 s` (`1.1263x`, `11.21%` faster); NetworkX `0.010454862558 s`.
- Current hyperfine process benchmark: clean-HEAD fnx `0.360840161234 s` -> after fnx `0.347226839474 s` (`1.0392x`, `3.77%` faster).
- Post-change profile: `_fnx.maximal_independent_set` falls from `0.004 s` to `0.003 s` in cProfile; the public wrapper self-loop pre-scan remains the next separate bottleneck.
