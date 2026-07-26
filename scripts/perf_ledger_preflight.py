#!/usr/bin/env python3
"""Ledger preflight — make an unfalsifiable REJECT impossible, not merely discouraged.

Adopted 2026-07-25 from frankensqlite's `sql_pipeline_candidate_preflight` after the
fleet resurrection audit showed ledger integrity DECAYS: the one repo that audited once
and then mechanically enforced the check sits at 1.7% VOID, while repos that never did
sit at 25-91%. franken_networkx measured 75.5% VOID (120/159 rejection rows) under the
six-class taxonomy, of which **113 are VOID-NONULL** — an A/B ran, the row was rejected
on a near-1.0 wall ratio, and neither an A/A null control nor a counted mechanism was
recorded, so the lever cannot be distinguished from the harness.

Exit codes (frankensqlite convention):
  0  OK
  2  BLOCKED — a new rejection row is unfalsifiable, or prior art exists for a lever

Modes
-----
--check [REF]      Every rejection row added since REF (default: origin/main) must carry
                   an A/A null control OR a counted mechanism. This is the gate; it is
                   wired into the test suite via tests/python/test_perf_ledger_gate.py
                   so a nullless REJECT fails the suite.
--prior-art TERMS  Grep every ledger for prior rows matching TERMS before proposing a
                   lever. Exit 2 if a prior REJECT matches — read it and justify, per the
                   campaign's HARD GATE ("grep the ledger before you propose a lever").
--audit            Re-classify all rejection rows under the six-class taxonomy and print
                   the void rate. Run it periodically: a rising void rate IS the decay.

Verdict taxonomy (frankenfs, adopted fleet-wide 2026-07-25)
  VALID-PROFILE    rejected pre-edit on a named frame with non-zero self-time + a ceiling
  VALID-MECHANISM  no A/A null, but refuted on a COUNTED mechanism (instructions, cycles,
                   syscalls, allocations, faults unchanged). A null control cannot change
                   the fact that no work was removed. NB: this class cuts BOTH ways — it
                   rescues rows from being wrongly voided, so apply it honestly.
  VALID-AB         A/B with a recorded A/A null; the effect sits inside it
  VOID-CV          killed ONLY by a cv<5% gate (unreachable on this hardware)
  VOID-ZEROSELF    target frame had ~0% self-time in the profile the bench actually ran
  VOID-NONULL      near-1.0 ratio, no null, no counted mechanism
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LEDGERS = [
    REPO / "docs" / "NEGATIVE_EVIDENCE.md",
    REPO / "docs" / "NEGATIVE_EVIDENCE_cc.md",
    REPO / "docs" / "progress" / "perf-negative-results.md",
]

REJECT_HEAD = re.compile(
    r"\b(REJECT\w*|NO-?SHIPS?|NOSHIP|REVERTED|ABANDONED|NOT TAKEN|NOT SHIPPED|BACKED OUT)\b",
    re.I,
)
KEEP_HEAD = re.compile(r"\b(KEEP|SHIP(?:PED|S)?|WIN|MILESTONE|FINDING|SURFACE)\b", re.I)
NULL_PAT = re.compile(
    r"\bnull\b|\bA/A\b|self[- ]control|identical arm|control arm|same-?binary (?:forced )?control",
    re.I,
)
COUNTED = re.compile(
    r"\binstructions?\b|\bcycles\b|\bsyscall|\ballocations?\b|\bmalloc|\bpage fault|"
    r"\bbranch(?:es|-miss)|\bcache miss|perf stat|callgrind|\bcall count\b|\bself[- ]time\b",
    re.I,
)
UNCHANGED = re.compile(
    r"\bunchanged\b|\bidentical\b|\bno (?:work|allocation|syscall|instruction)|\bsame number\b|"
    r"\bflat\b|\bnot? reduction\b|\bdid not (?:change|drop|fall)\b|\bzero (?:allocations|difference)",
    re.I,
)
ZERO_SELF = re.compile(
    r"0\.0{4,}\s*s\b|0\.000\s*%|zero self[- ]?time|never (?:executed|ran|routed)|"
    r"did not execute|no self[- ]?time",
    re.I,
)
CV_GATE = re.compile(r"cv\b[^.\n]{0,60}(?:gate|exceed|above|below|missed|failed)", re.I)
RATIO = re.compile(r"\*{0,2}(\d+(?:,\d{3})*(?:\.\d+)?)\s*[x×]\*{0,2}")


def sections(text: str):
    """Yield (heading, body) for every `## ` section."""
    current, buf = None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                yield current, "\n".join(buf)
            current, buf = line[3:].strip(), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        yield current, "\n".join(buf)


def is_rejection(heading: str) -> bool:
    if not REJECT_HEAD.search(heading):
        return False
    # a KEEP/FINDING heading that merely mentions a rejection in prose is not a reject row
    return not (KEEP_HEAD.search(heading) and not REJECT_HEAD.search(heading.split(":")[0]))


def ratio_of(heading: str):
    cut = re.split(r"\(`?br-", heading)[0]
    vals = RATIO.findall(cut)
    if not vals:
        return None
    try:
        return float(vals[-1].replace(",", ""))
    except ValueError:
        return None


def classify(heading: str, body: str) -> str:
    has_null = bool(NULL_PAT.search(body))
    counted = bool(COUNTED.search(body)) and bool(UNCHANGED.search(body))
    if ZERO_SELF.search(body):
        return "VOID-ZEROSELF"
    if has_null:
        return "VALID-AB"
    if counted:
        return "VALID-MECHANISM"
    if CV_GATE.search(body):
        return "VOID-CV"
    return "VOID-NONULL"


def falsifiable(heading: str, body: str) -> tuple[bool, str]:
    """A rejection row must carry an A/A null OR a counted mechanism."""
    cls = classify(heading, body)
    if cls.startswith("VALID"):
        return True, cls
    return False, cls


def added_sections(ref: str):
    """Sections whose heading line was ADDED to a ledger since `ref`."""
    out = []
    for path in LEDGERS:
        if not path.exists():
            continue
        try:
            diff = subprocess.run(
                ["git", "diff", f"{ref}...HEAD", "--unified=0", "--", str(path)],
                cwd=REPO, capture_output=True, text=True, check=False,
            ).stdout
        except OSError:
            continue
        added_heads = {
            line[1:].strip()[3:].strip()
            for line in diff.splitlines()
            if line.startswith("+## ")
        }
        if not added_heads:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for heading, body in sections(text):
            if heading in added_heads:
                out.append((path.name, heading, body))
    return out


def cmd_check(ref: str) -> int:
    rows = [(f, h, b) for f, h, b in added_sections(ref) if is_rejection(h)]
    if not rows:
        print(f"preflight: no new rejection rows since {ref} — OK")
        return 0
    bad = []
    for fname, heading, body in rows:
        ok, cls = falsifiable(heading, body)
        mark = "OK  " if ok else "FAIL"
        print(f"  [{mark}] {cls:<15} {fname}: {heading[:88]}")
        if not ok:
            bad.append((fname, heading, cls))
    if bad:
        print(
            f"\nBLOCKED: {len(bad)} new rejection row(s) carry neither an A/A null control "
            f"nor a counted mechanism.\n"
            "A rejection that records neither cannot distinguish the lever from the harness — "
            "it is\nunfalsifiable and will be voided by the next audit. Add ONE of:\n"
            "  * an A/A null control measured in the SAME invocation (see scripts/perf_harness.py:\n"
            "    paired(base, base) then paired(base, cand); gate on the median CI, never on cv), or\n"
            "  * a COUNTED mechanism showing no work was removed (instructions / cycles / syscalls /\n"
            "    allocations / faults unchanged), which a null control cannot overturn."
        )
        return 2
    print(f"\npreflight: {len(rows)} new rejection row(s), all falsifiable — OK")
    return 0


def cmd_prior_art(terms: list[str]) -> int:
    needles = [t.lower() for t in terms if t.strip()]
    if not needles:
        print("usage: --prior-art TERM [TERM ...]")
        return 1
    hits = []
    for path in LEDGERS:
        if not path.exists():
            continue
        for heading, body in sections(path.read_text(encoding="utf-8", errors="replace")):
            hay = (heading + "\n" + body).lower()
            if all(n in hay for n in needles):
                hits.append((path.name, heading, is_rejection(heading), classify(heading, body)))
    if not hits:
        print(f"prior-art: no ledger row matches {needles} — proceed")
        return 0
    rejects = [h for h in hits if h[2]]
    for fname, heading, is_rej, cls in hits:
        kind = f"REJECT/{cls}" if is_rej else "other"
        print(f"  [{kind:<22}] {fname}: {heading[:96]}")
    if rejects:
        print(
            f"\nBLOCKED: {len(rejects)} prior REJECT row(s) match this lever. Read them in full "
            "before\nproposing it. If a row is VOID-* the rejection is not evidence and you may "
            "re-run it —\nsay so explicitly in the new row and cite the old one."
        )
        return 2
    return 0


def cmd_audit() -> int:
    counts: dict[str, int] = {}
    total = 0
    for path in LEDGERS:
        if not path.exists():
            continue
        for heading, body in sections(path.read_text(encoding="utf-8", errors="replace")):
            if not is_rejection(heading):
                continue
            total += 1
            counts[classify(heading, body)] = counts.get(classify(heading, body), 0) + 1
    void = sum(v for k, v in counts.items() if k.startswith("VOID"))
    print(f"rejection rows audited : {total}")
    for key in sorted(counts):
        print(f"  {key:<16}: {counts[key]:>4}")
    if total:
        print(f"  {'VOID total':<16}: {void:>4} / {total} = {void / total * 100:.1f}%")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    mode = argv[1]
    if mode == "--check":
        return cmd_check(argv[2] if len(argv) > 2 else "origin/main")
    if mode == "--prior-art":
        return cmd_prior_art(argv[2:])
    if mode == "--audit":
        return cmd_audit()
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
