# G0 Docs-Freshness Threshold — Integrity Split (2026-09)

> Required by the suite's gate-change rule (`/data/projects/AGENTS.md`,
> Named Reward-Hacking Patterns #1): a gate parameter may change only with a
> published split of what the change admits. This is that split for the G0
> raise 50 → 150 code commits (`.github/workflows/ci.yml:40-46`).

## What changed

Two variables changed at once in the G0 step:

1. **Re-scoping**: lag counts only *code* commits (`crates/ python/ scripts/
   tests/ fuzz/`), not beads/artifact/ledger chores.
2. **Budget raise**: 50 → 150 code commits.

## Defect demonstration (why the old gate could not stand)

Under the old rule the gate vetoed **every** push on main from 2026-04-17 to
2026-09-01 — 0 successful runs out of 6,947 (`br-r37-c1-qrldi`) — with
G1–G8 skipped throughout. A freshness gate that passes nothing does not
protect freshness; it zeroes out all downstream gate evidence (G3/G4/G5/G6/G7/G8
produced nothing for ~4.5 months). The commit-rate premise of the old budget
(~30+ commits/day of any kind on this swarm) is verifiable in the git history.

## Method

Counterfactual replay over the last 300 main pushes (script:
rev-list counts per push, run 2026-09-03 at HEAD `153ac4f33`). For each push
C and each of the three watched files: `d_code` = code-only commits from the
file's last touch to C; `d_all` = all commits over the same span; `surf` =
commits touching `crates/fnx-python/src` + `python/franken_networkx` inside
the lag window. Rules compared:

- **Rule A** (old): `d_all ≤ 50`.
- **Rule A′**: `d_code ≤ 50` (isolates the re-scoping).
- **Rule B** (current): `d_code ≤ 150`.

Adjudication rule for rows Rule B admits that Rule A′ vetoed ("budget
admits"): **WIN_fix** if `surf == 0` (no public-surface-adjacent commit in
the lag window — the doc cannot have drifted, so the veto was a pure budget
artifact); **LOSE_plausible_drift** if `surf > 0` (the old gate's staleness
suspicion was reasonable).

## Results (300-push window)

| Class | Count |
|---|---|
| Pass Rule A and Rule B | 25 |
| Budget admits (Rule B only) | **31** |
| Re-scoping admits (A′ only) | **0** |
| Still vetoed under Rule B | 244 |
| **Regressions** (pass A, fail B) | **0** |

**Split of the 31 budget-admitted rows: 0 WIN_fix / 31 LOSE_plausible_drift.**
Median lag 140 code commits; median 122 public-surface commits inside the
lag window; binding file README.md on all 31. (An earlier 10-day-since-touch
adjudication was discarded as degenerate: at swarm velocity 150 code commits
≈ 6 days, so it classified every row WIN by construction. The surface-commit
rule is the honest one and it is adversarial to the change.)

## Verdict

- **The raise is NOT validated as a defect fix.** By the suite's own
  standard — "a gate change that suddenly produces wins was a loosening" —
  this change produces *zero* wins: every row it admits is a row where the
  docs had plausibly drifted (median 122 surface commits unaudited by the
  doc).
- **It is validated only as throughput restoration.** Rule A passed 25/300
  pushes over the sampled window and 0% of pushes for 137 consecutive days
  in the wild; G1–G8 were dark the entire time. The 2026-09-02/03 doc
  refreshes — not the raise — are what actually restored G0 to green at
  HEAD (all three files currently pass with small distances).
- **Keep 150 provisionally**, with this split published and the following
  revert trigger: once docs receive sustained maintenance (a watched-file
  touch inside every 150-code-commit window for 30 consecutive days), the
  budget should step back down toward 50 — at that point the swarm's real
  cadence will have re-validated the stricter budget without re-darkening
  the gates.

## Reproduce

```bash
# per push C and watched file f:
last=$(git log -n1 --format=%H $C -- "$f")
git rev-list --count "${last}..$C" -- crates python scripts tests fuzz   # d_code
git rev-list --count "${last}..$C"                                        # d_all
git rev-list --count "${last}..$C" -- crates/fnx-python/src python/franken_networkx  # surf
```
