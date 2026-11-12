# simulated_annealing_tsp / threshold_accepting_tsp init_cycle="greedy" — CopperCliff 2026-06-28

## Problem
The annealing fast path (_tsp_anneal_prep) bailed to full nx delegation for ANY str init_cycle,
including the common init_cycle="greedy" => 0.66x (N_inner=10) / 0.86x (N_inner=100 default)
on integer-weighted complete graphs.

## Fix (pure Python, __init__.py, br-cc-tspanngreedy)
nx resolves "greedy" via cycle=greedy_tsp(G,weight,source) (deterministic, no RNG) then anneals.
Resolve "greedy" inside _tsp_anneal_prep with the byte-exact greedy_tsp so the explicit-cycle
fast path engages. Greedy computation deferred until AFTER integer+completeness gates pass
(float/incomplete bail pays nothing).

## Measured (integer complete n=40)
N_inner=100 (nx default): SA 1.451x  TA 1.489x   (was ~0.86x)
N_inner=10:               SA 0.86x              (was 0.66x; every config beats old delegation)
Float: unchanged (fast path still bails on non-integer weight).

## Correctness
- 0/1920 == nx (SA+TA, greedy+explicit, int+float, n=3..30, moves 1-1/1-0, source None/explicit, 30 seeds)
- byte-exact because greedy is RNG-free => annealing RNG stream identical
- 118 tsp/approx-parity + 639 tsp/anneal/approx tests pass
