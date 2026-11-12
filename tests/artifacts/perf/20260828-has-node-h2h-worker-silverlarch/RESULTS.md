# has_node head-to-head, run entirely on the rch worker (br-r37-c1-p80x1)

SilverLarch, 2026-08-28. Both arms in ONE process, on ONE pinned worker CPU, in ONE
invocation: `rch exec -- cargo bench -p fnx-python --bench has_node_h2h`. No local build,
no ELF moved between machines. The binary self-reports its own SHA-256 and the extension
and NetworkX build it actually imported.

    bench_elf_sha256  55fecc117cf5feeb67a8cb1abd0a5ea061b80c3c3856bd222bd6c77dd30f712a
    fnx_extension     python/franken_networkx/_fnx.abi3.so
                      sha256=cd17e9fcc7e470b0120a59f2eb5106fecfedbb8f3a34c979255ed8c06428a935
    incumbent         networkx 3.7rc0.dev0 (vendored legacy_networkx_code)
    bench cpu         63

## Result, two runs

    key    probe      run 1     run 2    null 1   null 2    fnx ns    nx ns
    str    hit       1.202x    1.206x    0.998    1.000       91.9    110.8
    str    MISS      0.888x    0.878x    1.002    0.999      120.5    105.8
    int    hit       1.206x    1.215x    0.987    0.978       88.9    108.0
    int    MISS      0.178x    0.178x    1.008    1.002      521.7     93.0

Arms interleaved inside one loop, order reversed on odd rounds; 21 rounds; median. The A/A
null is a SEPARATELY BUILT fnx graph through the identical call protocol - timing one
object against itself is blind to the spread between separately built fixtures. All eight
nulls landed in band (0.978-1.008), so every row is quotable. The absent-int cell is
identical to three decimals across runs.

## The published loss is real and UNDERSTATED

The README publishes `has_node` at 0.41x. In wall clock the absent-INT cell is **0.178x** -
521.7 ns against networkx's 93.0 ns, 5.6x slower - so the published number understates the
real loss by about 2.3x.

Two further corrections to what was believed about this accessor:

  * HITS ARE WINS, not parity. Both key types read ~1.21x. The instruction-count artifact
    (20260828-has-node-absent-int-silverlarch) put hits at 1.006-1.009x; in wall clock fnx
    is comfortably ahead. br-r37-c1-native-method-attribute-lookup-tax-w7wjs was right that
    the accessors are fine, and understated it.
  * The loss is confined to ABSENT keys, and overwhelmingly to absent INT keys. Absent str
    is 0.878x; absent int is 0.178x.

## Ir said 0.430x, wall says 0.178x - and I could NOT isolate why

The instruction-count run measured the same cell at 0.430x against installed networkx
3.6.1. This run measures 0.178x against vendored 3.7rc0.dev0. TWO variables differ - the
metric AND the incumbent version - and the difference is not attributed here because it was
not isolated.

The attempt to isolate it failed for a structural reason worth recording: `FNX_INCUMBENT=installed`
drops the vendored oracle from sys.path so `import networkx` resolves to the worker's own
installation. There isn't one:

    ModuleNotFoundError: No module named 'networkx'

THE RCH WORKERS HAVE NO NETWORKX INSTALLED. The vendored `legacy_networkx_code` copy is the
only incumbent available there, which is why the existing head-to-head benches vendor it and
assert on it. So the worker-side method - both arms, one process, one invocation - can only
ever measure against 3.7rc0.dev0, a DEV PRERELEASE, while the README's published claims and
the library users actually install are 3.6.1.

That is a real limitation of this measurement route, not a defect in the harness. It does
not affect the qualitative finding (absent-int is a large loss on every metric and both
incumbent versions), but any ratio produced this way carries "vs 3.7rc0.dev0" and should not
be filed against a 3.6.1 claim without saying so.

## RESOLVED 2026-08-28: the workers gained networkx, and the metric is the explanation

The limitation recorded above is gone - the rch workers now have networkx **3.6.1**
installed (`/home/ubuntu/.local/lib/python3.14/site-packages/networkx/`), so
`FNX_INCUMBENT=installed` now runs against the release users actually have rather than the
vendored dev prerelease. Same harness, same extension (sha cd17e9fc...), only sys.path
differs.

    incumbent                      str hit   str MISS   int hit   int MISS
    installed 3.6.1, run 1          1.292x     0.946x    1.192x     0.189x
    installed 3.6.1, run 2          1.209x     0.880x    1.220x     0.176x
    vendored 3.7rc0.dev0, run 1     1.202x     0.888x    1.206x     0.178x
    vendored 3.7rc0.dev0, run 2     1.206x     0.878x    1.215x     0.178x

All A/A nulls in band (0.983-1.030).

THE INCUMBENT VERSION IS NOT THE EXPLANATION. The absent-int cell reads 0.176-0.189x
against installed 3.6.1 and 0.178x against vendored 3.7rc0.dev0 - indistinguishable. The
open question from the earlier artifact was whether the gap between the instruction-count
figure (0.430x) and the wall-clock figure (~0.18x) came from the METRIC or from the
INCUMBENT VERSION, since both differed at the time. It is the METRIC: the two networkx
builds agree, and Ir and wall clock do not.

That is consistent with the named mechanism below - a discarded PyErr and an allocation are
branch-and-memory heavy rather than instruction heavy, so they cost more wall time per
instruction than the retired-instruction count suggests. Still a hypothesis for the
direction of the gap, but the version confound is now eliminated rather than assumed away.

Absolute times move between runs (694.3 ns against 528.5 ns for the same cell on different
workers), which is why the RATIO with its in-process A/A null is the quotable figure and the
nanoseconds are not.

## Mechanism, from the instruction-count artifact

Not re-derived here, but the named causes of the absent-int path are a DISCARDED PyErr
(`<pyo3::err::PyErr>::take` runs on every absent-int probe, where networkx just misses a
dict) and CANONICALISATION ON A MISS (`write_int_decimal`, since a present int key answers
from the presence cache but a miss cannot - a cache hit is existence proof). The wall-clock
figure being so much worse than the Ir figure is consistent with those two being
branch-and-allocation heavy rather than instruction heavy, but that is a hypothesis and was
not measured.

## Reproduce

    rch exec -- cargo bench -p fnx-python --bench has_node_h2h

Add `env FNX_INCUMBENT=installed` to try the worker's own networkx; expect the
ModuleNotFoundError above until the workers gain one.
