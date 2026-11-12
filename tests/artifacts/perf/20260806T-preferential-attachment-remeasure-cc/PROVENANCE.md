# br-r37-c1-3s8x7 — preferential_attachment re-measure, provenance

Agent: SnowyValley (cc). Opened 2026-08-06. Status while this file stands alone
with no RESULT.md beside it: **measurement not yet admitted.**

## Why this re-measure exists

The published `preferential_attachment` loss (0.59x) predates `br-r37-c1-padm6`.
padm6 moved `n in G` from 0.27x to 0.7188x by putting the private-override probe
in native `__contains__`, and padm6 says in writing that this dunder is **91% of
the preferential_attachment loss** — ebunch validation was 153.5 us vs nx's
37.5 us on 300 pairs, out of a 127.5 us total deficit. It closed 2026-08-05 and
the downstream re-measure it asked for was never run.

Mechanism confirmed by reading the source, not assumed:
`_link_prediction_validate_ebunch` (`python/franken_networkx/__init__.py:17452`
and `:17454`) tests each endpoint with `u not in G` / `v not in G` — exactly the
dunder padm6 moved into native code. nx's `_apply_prediction` membership-tests
the same endpoints, so the two sides are structurally comparable.

## THE BUILD UNDER TEST IS NOT THE INSTALLED PACKAGE

**The wheel is loaded by `PYTHONPATH` BECAUSE the installed package is not the
code under test.** This is the detail that decides whether anything below means
anything at all.

`/home/ubuntu/.local/lib/python3.13/site-packages/franken_networkx/__init__.py`
**differs from** `python/franken_networkx/__init__.py` in this checkout. The
Python half of this library is where `preferential_attachment`'s ebunch
validation lives, so benchmarking the default import would have measured an
older branch's Python against HEAD's premise and reported a number about a build
nobody is shipping. The identical trap once published a 0.91x LOSS that was
really 3.1x.

So the measurement does NOT import `franken_networkx` from site-packages. It
builds a fresh wheel from HEAD and puts that first on `PYTHONPATH`:

| item | value |
| --- | --- |
| build | `env -u CARGO_TARGET_DIR maturin build --release --features pyo3/abi3-py310`, TRUE_EXIT=0 |
| extracted to | `<scratch>/head_wheel/franken_networkx/` |
| ELF sha256 | `f95dfd10cc09dffffe7f11f9a8d48f8a04fe031f583eb8065d867be606fc002c` |
| `__init__.py` | byte-identical to `python/franken_networkx/__init__.py` (diff clean) |
| `core.py` | present (the wheel-drops-`core.py` defect did not recur) |
| incumbent | live networkx 3.6.1, imported in the same process |

Both halves are checked, not just the `.so`: a stale `.py` beside a fresh `.so`
is the same failure wearing a different hat.

## Probe

`python3 scripts/perf_harness.py class1-frontier`, row
`preferential_attachment n=1200 pairs=300`.

nx and fnx are interleaved INSIDE one invocation and every row carries dual A/A
nulls, so a single admitted run is decidable on the harness's own three-clause
median gate. There is no across-run yardstick here and therefore none of the
ratio-of-ratios exposure that made `br-r37-c1-vz4v9` unresolvable.

Driver: `<scratch>/measure_pa.sh`, `PYTHONHASHSEED=0`, `taskset -c 0-3`, up to 25
attempts, one harness at a time (the script refuses to start if another
`perf_harness.py` is running — two loops on the same cores never trip each
other's gate and would corrupt both).

## Disposition, fixed in advance

Stated before any admitted number exists, so it cannot be chosen to suit one:

- **If it admits:** report the ratio as measured, in whichever direction it
  falls. A re-measure that comes back still-a-loss is the useful output; the
  91% attribution is a prediction that can be falsified, not a target.
- **If 25 attempts exhaust:** record **NO ADMISSIBLE MEASUREMENT**. That is not
  a measured null, it is not evidence the lever failed to transfer, and it is
  **not** licence to re-publish 0.59x. Those are three different claims and the
  ledger must not blur them.

## Attempt log (host-wide quiescence gate)

The blocker is host exclusivity, not the measurement. The gate is a **per-CPU
maximum**, not a mean, which is why attempts fail at loads that look calm:

| attempt | UTC | 1-min load | result |
| --- | --- | ---: | --- |
| 1 | 08:24:28 | 59.50 | gate refused |
| 2 | 08:29:28 | 70.14 | gate refused |
| 3 | 08:31:04 | 31.09 | gate refused |
| 4 | 08:36:38 | 17.91 | gate refused |
| 5 | 08:40:19 | 13.01 | gate refused |

Attempts 4 and 5 are the informative ones: a 13-18 load on a 64-way host is a
quiet machine by any average measure, and the gate still refused. Peer agents
keep individual cores busy.
