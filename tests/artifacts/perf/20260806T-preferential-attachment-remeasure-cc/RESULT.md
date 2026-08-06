# br-r37-c1-3s8x7 — RESULT: NO ADMISSIBLE MEASUREMENT

25 attempts, 0 admitted. See `PROVENANCE.md` for the build under test and for the
disposition, which was written **before** any attempt ran.

## What this is, stated in the three ways it will be misread

- It is **NOT a measured null.** No admitted run exists, so nothing was measured
  in either direction.
- It is **NOT evidence that the `br-r37-c1-padm6` attribution failed to transfer.**
  That prediction — that the native `__contains__` fix removes ~91% of this loss —
  remains untested, not refuted.
- It is **NOT licence to re-publish 0.59x.** That figure predates padm6 and is
  known-stale on its face; the reason this bead exists is that nobody has measured
  the surface since. An exhausted retry budget does not restore a stale number.

## Why it failed, which is a structural finding rather than bad luck

The gate is a **per-CPU maximum, not a mean.** Attempts were refused at 1-minute
loads of 2.73, 2.15 and 1.91 on a 64-way host — idle by any average measure.

More usefully, the failure mode CHANGED partway through. From attempt ~11 onward
the runs stopped failing at the `pre_setup` gate and started **passing it and then
dying mid-suite** on a checkpoint, each time to a single transient core:

| attempt | died during | offending CPU | 1-min load |
| --- | --- | --- | ---: |
| 22 | `[A/A nx] square_clustering n=5000 m=20000` | cpu48 = 35.0% | 2.92 |
| 23 | `[A/A nx] rich_club_coefficient n=5000 m=20000` | cpu8 = 41.9% | 3.00 |
| 24 | `enumerate_all_cliques n=1000 m=4000` | cpu22 = 25.0% | 2.96 |
| 25 | `k_core n=1000 m=4000` | cpu54 = 38.7% | 3.20 |

A different CPU every time, on an otherwise-quiet host. **`class1-frontier` needs
the whole host below the per-CPU threshold for the suite's ENTIRE duration**, and
`preferential_attachment` is at the END of that suite — so it is the row least
likely to be reached, independent of how the machine looks on average.

This is the actionable part: **retrying this suite harder will not fix it.** What
would: a genuinely exclusive host window, or reaching this row through a shorter
suite so the exposure window shrinks. The latter needs a harness change, which is
not something to do casually to a shared measurement instrument, and must not be
done by carving the bench down to the one row being claimed.

## One of the failures was self-inflicted, and is recorded because the trap generalises

Attempts 11 and 12 died at 08:46:35 and 08:46:47, which lines up exactly with two
`rch exec` invocations run as "other work while waiting". **`rch` offloads the
compile but NOT the repo rsync, which is local CPU.** Doing rch work beside a
running harness kills the harness. Subsequent work was suspended whenever load
dropped below ~5 and confined to windows where peers had already made the gate
unreachable.

## Standing state

`br-r37-c1-3s8x7` stays OPEN. The build is already prepared and verified — a fresh
HEAD wheel, ELF `f95dfd10cc09dffffe7f11f9a8d48f8a04fe031f583eb8065d867be606fc002c`,
loaded by `PYTHONPATH` because the installed site-packages copy is NOT the code
under test. A future attempt needs the host window, not new setup.
