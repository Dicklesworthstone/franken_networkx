# Harnesses behind the 2026-08-15 dunder-wrapper and node-key rows (SnowyValley)

Every row this directory backs was measured with BOTH ARMS IN ONE INVOCATION on
one machine. None of them was dispatched to an rch worker — rch compiled, it
never timed anything.

    same_host   = thinkstation1
    rch_worker  = none (both arms in-process on same_host)
    governor    = powersave      runtime_isa = avx2,avx,sse4_2
    affinity    = taskset -c 40-47 (8 cpus)   PYTHONHASHSEED=0
    incumbent   = live networkx 3.6.1, imported in the same process

**Why these files are here rather than in a scratch directory.** A row that
names its harness is only checkable if the harness can be run. Two findings from
2026-08-15 make that mandatory: frankenlibc measured one primitive on ONE worker
with two separately-sanctioned harnesses and got `5.9459x` and `12.385414x`, and
this repo independently found `(u,v) in G.edges()` reading `0.4254x` under
`scripts/balanced_square_ab.py` and `0.8502x` under `ab_wrapper_ablation.py` on
the same ELF minutes apart — **both admissible, both nulls passing**
(`br-r37-c1-y4r63`). A passing A/A null certifies stationarity within one
harness's run and says nothing about whether two harnesses measure the same
thing, so the harness identity is part of the claim.

**Deletion condition:** when the rebind-ablation pattern below is folded into a
single parameterised harness under `scripts/` that supersedes these files, this
directory goes with them.

## The ablation pattern

Four of these harnesses answer the same shape of question — *what did the Python
wrapper cost?* — after the wrapper was deleted. They rebuild the OLD arm
in-process by re-applying the wrapper function over the new native slot, rebind
the class attribute OUTSIDE every timed slot, and run the same balanced
`ABBAABBA` square with per-arm A/A nulls that `scripts/balanced_square_ab.py`
uses. That is what makes a self-delta measurable on ONE build.

| harness | sha256 | row it backs |
|---|---|---|
| `ab_wrapper_ablation.py` | `12a4b53cd798e03804a830b263e31edbd1b6fe356bd41b7abc460241cac89c05` | `x in G.edges` wrapper, 1.1190x / 1.2303x / 1.2562x (`br-r37-c1-dtrpe`) |
| `ab_len_wrapper.py` | `13d5689bb37f8daf405be0947ee0622f4a4b988802a7b7fa00839ce822f02c32` | `len(G)` 0.4074x -> 2.0225x (`br-r37-c1-l7ww9`) |
| `ab_iter_wrapper.py` | `3280cde827b3d852d1df75c732c639b4138d242ab04ad73822705b11707f92c1` | `iter(G)` 1.7680x 8-node / 1.0072x 2000-node (`br-r37-c1-l7ww9`) |
| `ab_multi_contains.py` | `15b30094e139678578d3ee9e802b455729bdc51bcb1376ff75c66874e3862431` | `(u,v) in MG.edges` walk -> native, 6.9979x / 7.1365x (`br-r37-c1-6fs77`) |
| `ab_memo_miss_cost.py` | `353df9cc5248cd31078355be89ee98a5a04d17c28c4785ac595ddd5560ac1294` | present-key memo MISS cost, 0.8378x (`br-r37-c1-6n9vm`) |
| `ab_view_sweep2.py` | `665a9ff38f2a08ec6d4c17c1e793f4f1bb7e3d449decb8ea371b5e0de2eb809e` | the 20-row view-surface ranking that chose the targets |
| `ab_absent_sweep.py` | `e8a07256722d55c316a82e046571aa92aaf3a5dfd0cd5300d69fa5e39124e753` | absent-key rows: has_node 0.6610x, `n in G` 0.8797x, mixed 0.7575x |

## Instruction-count probes

These are callgrind, not wall clock, and are recorded as attribution — never as
a verdict. Ir moved the wrong way at least once today: the endpoint lookaside
removed 101 Ir/call and was **1.27x slower** in wall clock.

| probe | sha256 | what it establishes |
|---|---|---|
| `ir_probe_has_node.py` | `5d7a004bda246d55985b9d24d52b203e3bac8708dbed7381b40c7f87c9dcab08` | canonicalisation is 77.4% of `has_node`'s 437.4 Ir/call — the interning HOLD's 30% condition |
| `ir_probe_edges_contains.py` | `5d69e89c7be2c03b40efc9bce20be3eac0bff0b4e69310118329571b34e8f89d` | `(u,v) in G.edges()` breakdown, 796.3 -> 696.0 Ir/call under the reverted lookaside |
| `ir_slope_edges_contains.py` | `5d659b0483163fff690ccd030f45a83a3ffed679e8dc1b414080d93fc5c5c5cc` | whole-program Ir SLOPE, comparable BETWEEN libraries: nx 1327.0, fnx wrapped 2451.4, fnx native 1336.7 Ir/probe |

Every Ir figure above was validated by running at two rep counts and requiring
per-call Ir to be flat, which is what says the toggle bounds the collected
extent rather than trailing off into module import.

## Running them

    PYTHONPATH=<a package dir holding the .so under test> PYTHONHASHSEED=0 \
      OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 taskset -c 40-47 \
      python3 ab_len_wrapper.py

Each prints its own ELF SHA-256 from inside the process. Point `PYTHONPATH` at a
COPY of the package, not the repo tree: peers rebuild `python/franken_networkx/`
mid-session, and a mid-run swap was observed on 2026-08-15 (two callgrind runs
of one probe reported different ELF SHAs).
