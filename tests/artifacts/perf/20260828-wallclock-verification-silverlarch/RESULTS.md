# Wall-clock verification of this session's landed claims (br-r37-c1-qbj9u, vevfq, p80x1.14)

SilverLarch, 2026-08-28. Every perf claim I landed this session was an INSTRUCTION-COUNT
claim, because `host_quiet_check` refused this host continuously - loadavg ran 15 to 192.
It cleared ("WOULD ATTEMPT", 94.7% aggregate idle), so these rows were re-measured under the
protocol the Ir work could not use.

## Protocol

  * live networkx in the SAME invocation as fnx - not a separate process, not a recorded
    number from an earlier run;
  * arms INTERLEAVED inside one loop, order reversed on odd rounds (ABBA), so monotone
    drift cannot land preferentially on one arm;
  * an A/A NULL: a SEPARATELY BUILT fnx fixture timed through the identical call protocol.
    Timing one object against itself is blind to the ~5% spread between separately built
    fixtures, so the null uses a second graph;
  * 21 rounds, median, pinned to cores 56-63;
  * a row is quotable only if its null sits near 1.0. All eight nulls below did
    (0.932 to 1.033).

## Results, two independent runs

    row                                      run 1      run 2    null 1   null 2   Ir claim
    effective_size(DiGraph, nodes=subset)   443.056x   554.737x   1.032    0.932    1068x
    constraint(DiGraph, nodes=subset)       282.612x   292.622x   1.033    0.979    306.7x
    greedy_color(DiGraph)                     8.196x     8.393x   1.016    1.000    7.512x
    maximum_branching(Graph)                  0.865x     0.867x   0.994    1.010    0.849x

elf_sha256 cd17e9fcc7e470b0, networkx 3.6.1.

## What holds

ALL FOUR ROWS ARE CONFIRMED IN DIRECTION. The three wins are wins and the loss is a loss;
nothing reversed. That matters because Ir has moved OPPOSITE to wall clock in this repo
before - br-r37-c1-p1tvg cut 101 Ir/call and ran 1.27x SLOWER - so direction was not
guaranteed.

Three of the four also agree closely in MAGNITUDE, and are stable across runs:

    constraint          283-293x wall against 306.7x Ir      within ~8%
    greedy_color        8.20-8.39x wall against 7.512x Ir    wall is slightly BETTER
    maximum_branching   0.865-0.867x wall against 0.849x Ir  within ~2%, and very stable

## What does NOT hold: effective_size

The published Ir figure is 1068x. The wall-clock ratio is 443x and 555x on two runs - a huge
win either way, but roughly HALF the instruction-count number, and noticeably noisier than
the other rows (25% spread between runs where constraint moved 3%).

So the 1068x in 86e61d1d3 overstates the real-world speedup by about 2x. The instruction
count was correctly measured; it simply does not translate one-for-one into time here. The
plausible mechanism is an IPC difference - fnx's native path and networkx's Python loop
retire instructions at different rates - but that is a hypothesis, not something measured,
and it is recorded as such.

CORRECTED CLAIM: effective_size(DiGraph, nodes=<iterable>) is ~440-555x against live
networkx in wall clock, not 1068x. The delegated path it replaced is still catastrophic
(networkx's own redundancy loop at ~207 ms per call) and the fix is still overwhelmingly
worth having.

## Caveat on the window

The gate was clear ("WOULD ATTEMPT") when run 1 started. By the end of run 2 it read
"WOULD REFUSE: 2 CPUs over the bound" (25.0% and 23.5%). Both runs' A/A nulls stayed in
band, which is the row-level admission criterion, but the window was closing and the
effective_size spread may partly reflect that. A third run on a fully quiet host would
tighten that row; the other three are stable enough not to need it.

## Reproduce

    PYTHONPATH=python taskset -c 56-63 python3 wall_verify.py
