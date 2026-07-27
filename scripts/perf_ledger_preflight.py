#!/usr/bin/env python3
"""Ledger preflight — make an unfalsifiable REJECT impossible, not merely discouraged.

Adopted 2026-07-25 from frankensqlite's `sql_pipeline_candidate_preflight` after the
fleet resurrection audit showed ledger integrity DECAYS: the one repo that audited once
and then mechanically enforced the check sits at 1.7% VOID, while repos that never did
sit at 25-91%. franken_networkx measured 81.8% VOID (130/159 rejection rows) under the
six-class taxonomy, of which **121 are VOID-NONULL** — an A/B ran, the row was rejected
on a near-1.0 wall ratio, and neither an A/A null control nor a counted mechanism was
recorded, so the lever cannot be distinguished from the harness.

Exit codes (frankensqlite convention):
  0  OK
  2  BLOCKED — a new verdict row is unfalsifiable, or prior art exists for a lever
 64  USAGE / IO ERROR

Modes
-----
--check [REF]      Every rejection row added since REF (default: origin/main) must carry
                   an A/A null control OR a counted mechanism, and every KEEP must carry
                   the SHA-256 of the ELF identified from inside the benchmark process.
--check-staged      Apply that rule to the exact staged ledger text. This is the
                   pre-commit gate; it does not inspect an unstaged worktree by mistake.
--candidate         Given `--lever TEXT --surface TEXT`, search prior ledger rows on the
                   target surface and print each recorded retry predicate.
--prior-art TERMS  Grep every ledger for prior rows matching TERMS before proposing a
                   lever. Exit 2 if a prior REJECT matches — read it and justify, per the
                   campaign's HARD GATE ("grep the ledger before you propose a lever").
--audit            Re-classify all rejection rows under the six-class taxonomy and print
                   the void rate. Run it periodically: a rising void rate IS the decay.
--selfcheck        Exercise all six classes, loaded-ELF provenance, and known historical
                   escape rows from this repository. This also runs inside --check-staged.

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
GIT_TIMEOUT_SECONDS = 30
LEDGERS = [
    REPO / "docs" / "NEGATIVE_EVIDENCE.md",
    REPO / "docs" / "NEGATIVE_EVIDENCE_cc.md",
    REPO / "docs" / "progress" / "perf-negative-results.md",
]

REJECT_HEAD = re.compile(
    r"\b(REJECT\w*|NO-?SHIPS?|NOSHIP|REVERTED|ABANDONED|NOT TAKEN|NOT SHIPPED|"
    r"BACKED OUT|VALID-PROFILE)\b",
    re.I,
)
KEEP_HEAD = re.compile(r"\b(KEEP|SHIP(?:PED|S)?|WIN|MILESTONE|FINDING|SURFACE)\b", re.I)
KEEP_VERDICT_HEAD = re.compile(r"\b(KEEP|SHIP(?:PED|S)?|WIN)\b", re.I)
NULL_TOKEN = re.compile(
    r"\bA/A\b|\bnull(?:[- ](?:control|floor|band|envelope|CI))\b|"
    r"\bnull\b(?=\s*\|)|"
    r"self[- ]control|identical arm|control arm|"
    r"same-?binary (?:forced )?control",
    re.I,
)
COUNTED_EVIDENCE = re.compile(
    r"\b(?:count(?:ed|er|ers|ing|s)?|measur(?:ed|ement|ements|ing)|"
    r"record(?:ed|ing)|observ(?:ed|ation|ations|ing)|perf(?:\s+stat)?)\b",
    re.I,
)
COUNTED_METRIC = re.compile(
    r"\b(?:instructions?|cycles?|syscalls?|allocations?|faults?)\b",
    re.I,
)
COUNTED_RESULT = re.compile(
    r"\b(?:instructions?|cycles?|syscalls?|allocations?|faults?)\b"
    r"[^.\n]{0,120}"
    r"(?:\b(?:was|were|remained|stayed)\s+(?:unchanged|identical|flat)\b|"
    r"\bno reduction\b|\bdid not (?:change|drop|fall)\b|\bzero difference\b)|"
    r"\b(?:unchanged|identical)\b[^.\n]{0,60}"
    r"\b(?:instructions?|cycles?|syscalls?|allocations?|faults?)\b",
    re.I,
)
ZERO_SELF = re.compile(
    r"0\.0{4,}\s*s\b|0\.000\s*%|(?<!non-)zero self[- ]?time|"
    r"never (?:executed|ran|routed)|did not (?:execute|reach (?:the )?timed path)|"
    r"(?<!non-)no self[- ]?time",
    re.I,
)
PROFILE_PRE_EDIT = re.compile(
    r"\bpre[- ]edit\b|\bbefore (?:any )?(?:source )?edit(?:ing)?\b|"
    r"\bno source (?:edit|change)\b",
    re.I,
)
PROFILE_VERDICT = re.compile(r"\bVALID-PROFILE\b|\bRESULT\b[^.\n]{0,80}\bNO SOURCE EDIT\b", re.I)
PROFILE_FRAME = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_][A-Za-z0-9_]*)+\b|"
    r"\b[A-Za-z_][A-Za-z0-9_]*\b[^.\n]{0,40}\bframe\b",
    re.I,
)
NONZERO_SELF = re.compile(
    r"(?:\b(?:[1-9]\d*(?:\.\d+)?|0\.\d*[1-9]\d*)\s*%"
    r"[^.\n]{0,40}\bself(?:[- ]time)?\b|"
    r"\bself(?:[- ]time)?\b[^.\n]{0,40}"
    r"(?:[1-9]\d*(?:\.\d+)?|0\.\d*[1-9]\d*)\s*%|"
    r"\b(?:[1-9]\d*(?:\.\d+)?|0\.\d*[1-9]\d*)\s*s\b"
    r"[^.\n]{0,40}\bself\b|\bnon-zero (?:measured )?self[- ]time\b)",
    re.I,
)
AMDHAL_CEILING = re.compile(
    r"\b(?:computed|executable)?\s*(?:Amdahl\s+)?"
    r"(?:ceilings?|upper bound|maximum|max)\b"
    r"[\s\S]{0,500}?\d+(?:\.\d+)?\s*(?:[x×]|%)",
    re.I,
)
CV_GATE = re.compile(r"cv\b[^.\n]{0,60}(?:gate|exceed|above|below|missed|failed)", re.I)
RATIO = re.compile(r"\*{0,2}(\d+(?:,\d{3})*(?:\.\d+)?)\s*[x×]\*{0,2}")
LOADED_ELF_SHA = re.compile(
    r"\bbench_elf_sha256\s*=\s*[`*]?([0-9a-f]{64})\b|"
    r"(?:self[- ]report(?:ed|ing)?|inside (?:the )?(?:benchmark )?process|"
    r"in[- ]process|line one)"
    r"[\s\S]{0,240}?\b(?:ELF|binary)\b"
    r"[\s\S]{0,120}?\bsha-?256\b[^0-9a-f]{0,32}[`*]?([0-9a-f]{64})\b",
    re.I,
)
NEGATED_NULL = re.compile(
    r"\b(?:no|without|lacks?|lacking|missing|never recorded|not recorded)\s+"
    r"(?:an?\s+)?(?:recorded\s+)?(?:same[- ]invocation\s+)?"
    r"(?:A/A(?:\s+null(?:\s+control)?)?|null control)\b|"
    r"\bno\b[^.\n]{0,120}\b(?:A/A|null)\b",
    re.I,
)
FUTURE_NULL = re.compile(
    r"\b(?:future|retry|reopen|must|need(?:s|ed)?|require[sd]?|"
    r"only (?:after|if)|permitted)\b"
    r"[\s\S]{0,1000}?(?:\bA/A\b|\bnull\b)",
    re.I,
)
NULL_NUMERIC_EVIDENCE = re.compile(
    r"\b\d+(?:\.\d+)?\s*[x×]\b|"
    r"\b\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?\s*[x×]\b|"
    r"\[\s*\d+(?:\.\d+)?\s*[,–-]\s*\d+(?:\.\d+)?\s*\]",
    re.I,
)
TOKEN = re.compile(r"[a-z0-9_:.]+")
STOPWORDS = {
    "and",
    "for",
    "from",
    "into",
    "lever",
    "method",
    "new",
    "path",
    "proposed",
    "surface",
    "the",
    "with",
}


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


def is_keep(heading: str) -> bool:
    """Return whether the heading declares a shipped performance verdict."""
    return not is_rejection(heading) and bool(KEEP_VERDICT_HEAD.search(heading))


def logical_evidence_units(body: str) -> list[str]:
    """Join wrapped prose while keeping Markdown table rows independently decidable."""
    logical_lines = []
    paragraph = []
    for physical_line in body.splitlines():
        stripped = physical_line.strip()
        if not stripped:
            if paragraph:
                logical_lines.append(" ".join(paragraph))
                paragraph = []
        elif stripped.startswith("|"):
            if paragraph:
                logical_lines.append(" ".join(paragraph))
                paragraph = []
            logical_lines.append(stripped)
        else:
            paragraph.append(stripped)
    if paragraph:
        logical_lines.append(" ".join(paragraph))
    return logical_lines


def has_recorded_null(body: str) -> bool:
    """Require positive measurement evidence, not merely the word ``null``.

    ``no A/A null`` and a retry sentence saying that a future run *needs* a
    null must not make an undecidable rejection pass the gate.
    """

    for logical_line in logical_evidence_units(body):
        if not NULL_TOKEN.search(logical_line):
            continue
        if NEGATED_NULL.search(logical_line) or FUTURE_NULL.search(logical_line):
            continue
        if NULL_NUMERIC_EVIDENCE.search(logical_line):
            return True
    return False


def has_counted_mechanism(body: str) -> bool:
    """Require a locally recorded counter result, not a proposed mechanism.

    The escaped classifier matched a word such as ``allocations`` in proposed
    work and an unrelated ``unchanged`` elsewhere in the section.  A genuine
    VALID-MECHANISM row must put a counting/measurement marker, the named
    metric, and its unchanged result in one evidence sentence or table row.
    """
    for unit in logical_evidence_units(body):
        sentences = re.split(r"(?<=[.!?])\s+", unit)
        for sentence in sentences:
            if (
                COUNTED_EVIDENCE.search(sentence)
                and COUNTED_METRIC.search(sentence)
                and COUNTED_RESULT.search(sentence)
            ):
                return True
    return False


def has_valid_profile_rejection(heading: str, body: str) -> bool:
    """Recognize the taxonomy's profile-only class without weakening new-row policy."""
    plain = (heading + "\n" + body).replace("`", "").replace("*", "")
    return all(
        pattern.search(plain)
        for pattern in (
            PROFILE_VERDICT,
            PROFILE_PRE_EDIT,
            PROFILE_FRAME,
            NONZERO_SELF,
            AMDHAL_CEILING,
        )
    )


def has_loaded_elf_sha(body: str) -> bool:
    """Accept only an in-process loaded-binary identity with a full SHA-256."""
    return bool(LOADED_ELF_SHA.search(body))


def retry_predicate(body: str) -> str | None:
    """Extract the first concrete ``RETRY PREDICATE`` paragraph, if present."""
    lines = body.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"\s*RETRY PREDICATE:\s*(.*)", line, re.I)
        if match is None:
            continue
        parts = [match.group(1).strip()] if match.group(1).strip() else []
        for continuation in lines[index + 1 :]:
            stripped = continuation.strip()
            if not stripped:
                break
            parts.append(stripped)
        return " ".join(parts) if parts else "<empty>"
    return None


def search_tokens(text: str) -> list[str]:
    """Normalize quoted lever/surface prose into stable grep tokens."""
    return [
        token
        for token in TOKEN.findall(text.lower())
        if token not in STOPWORDS and (len(token) >= 3 or token.isdigit())
    ]


def contains_search_token(haystack: str, token: str) -> bool:
    """Match identifiers without treating ``Graph`` as part of ``DiGraph``."""
    return bool(
        re.search(
            rf"(?<![a-z0-9_]){re.escape(token)}(?![a-z0-9_])",
            haystack,
            re.I,
        )
    )


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
    has_null = has_recorded_null(body)
    counted = has_counted_mechanism(body)
    if ZERO_SELF.search(body):
        return "VOID-ZEROSELF"
    if has_valid_profile_rejection(heading, body):
        return "VALID-PROFILE"
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
    return has_recorded_null(body) or has_counted_mechanism(body), cls


def added_headings(diff: str) -> set[str]:
    """Return exact ``##`` headings added by a Git diff."""
    return {
        line[1:].strip()[3:].strip()
        for line in diff.splitlines()
        if line.startswith("+## ")
    }


def git_text(spec: str, path: Path) -> str:
    """Read one ledger from a revision (`HEAD:path`) or the index (`:path`)."""
    relative = path.relative_to(REPO).as_posix()
    object_name = f":{relative}" if spec == ":" else f"{spec}:{relative}"
    result = subprocess.run(
        ["git", "show", object_name],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"cannot read {object_name}: {(result.stderr or result.stdout).strip()}"
        )
    return result.stdout


def rows_for_added_headings(path: Path, headings: set[str], text: str):
    return [
        (path.name, heading, body)
        for heading, body in sections(text)
        if heading in headings
    ]


def added_sections(ref: str):
    """Sections whose heading line was committed after ``ref``."""
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    if probe.returncode != 0:
        raise RuntimeError(f"unknown Git ref: {ref}")

    out = []
    for path in LEDGERS:
        relative = path.relative_to(REPO).as_posix()
        diff = subprocess.run(
            ["git", "diff", f"{ref}...HEAD", "--unified=0", "--", relative],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        if diff.returncode != 0:
            raise RuntimeError((diff.stderr or diff.stdout).strip())
        headings = added_headings(diff.stdout)
        if headings:
            out.extend(rows_for_added_headings(path, headings, git_text("HEAD", path)))
    return out


def staged_sections():
    """Sections added in the index, read from the index rather than the worktree."""
    out = []
    for path in LEDGERS:
        relative = path.relative_to(REPO).as_posix()
        diff = subprocess.run(
            ["git", "diff", "--cached", "--unified=0", "--", relative],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        if diff.returncode != 0:
            raise RuntimeError((diff.stderr or diff.stdout).strip())
        headings = added_headings(diff.stdout)
        if headings:
            out.extend(rows_for_added_headings(path, headings, git_text(":", path)))
    return out


def cmd_check_rows(rows, label: str) -> int:
    verdict_rows = [
        (fname, heading, body)
        for fname, heading, body in rows
        if is_rejection(heading) or is_keep(heading)
    ]
    if not verdict_rows:
        print(f"preflight: no new REJECT/KEEP rows {label} — OK")
        return 0

    bad_rejects = []
    bad_keeps = []
    for fname, heading, body in verdict_rows:
        if is_rejection(heading):
            ok, cls = falsifiable(heading, body)
            if not ok:
                bad_rejects.append((fname, heading, cls))
        else:
            ok = has_loaded_elf_sha(body)
            cls = "KEEP-ELF" if ok else "KEEP-NO-LOADED-ELF-SHA"
            if not ok:
                bad_keeps.append((fname, heading, cls))
        mark = "OK  " if ok else "FAIL"
        print(f"  [{mark}] {cls:<23} {fname}: {heading[:88]}")

    if bad_rejects or bad_keeps:
        print(f"\nBLOCKED: {len(bad_rejects) + len(bad_keeps)} invalid verdict row(s).")
        if bad_rejects:
            print(
                f"\n{len(bad_rejects)} REJECT row(s) carry neither a positively recorded "
                "same-invocation A/A null control nor a counted mechanism. A mention such as "
                "'no A/A null' does not satisfy the gate. Add ONE of:\n"
                "  * paired(base, base) and paired(base, candidate) in the SAME invocation; "
                "gate on the bootstrap median CI, never CV, or\n"
                "  * unchanged counted instructions / cycles / syscalls / allocations / faults, "
                "which proves no work was removed."
            )
        if bad_keeps:
            print(
                f"\n{len(bad_keeps)} KEEP row(s) lack the SHA-256 of the binary identified "
                "from INSIDE the benchmark process. Print `bench_elf_sha256=<64 hex>` as line "
                "one (or record equivalent explicit in-process loaded-ELF provenance). A shell "
                "hash computed next to the run is not accepted."
            )
        return 2

    print(f"\npreflight: {len(verdict_rows)} new verdict row(s) {label}, all valid — OK")
    return 0


def cmd_check(ref: str) -> int:
    return cmd_check_rows(added_sections(ref), f"since {ref}")


def cmd_selfcheck(*, quiet: bool = False) -> int:
    """Prove the gate rejects its historical escape class on this repository."""
    failures: list[str] = []
    checks = 0

    synthetic_rows = [
        (
            "escaped proposed-allocation prose",
            (
                "The candidate sought to remove allocations, but the unchanged source "
                "then ran at 1.001x. No A/A null control was recorded."
            ),
            "VOID-NONULL",
            False,
        ),
        (
            "profile filename is not a flat counter result",
            (
                "perf record -e cycles:u wrote perf.flat.txt for the unchanged source. "
                "No A/A null control was recorded."
            ),
            "VOID-NONULL",
            False,
        ),
        (
            "genuine counted mechanism",
            (
                "perf stat counted allocation totals: baseline 1024, candidate 1024; "
                "allocations were unchanged between arms."
            ),
            "VALID-MECHANISM",
            True,
        ),
        (
            "positive same-invocation null",
            (
                "The same-invocation A/A null measured 1.001x with bootstrap "
                "CI [0.995,1.008]; the candidate effect sat inside it."
            ),
            "VALID-AB",
            True,
        ),
        (
            "profile-only historical row",
            (
                "RESULT: VALID-PROFILE / NO SOURCE EDIT. Rejected before any source "
                "edit. The named frame `Graph::neighbors` carried 3.2% self-time. "
                "The computed Amdahl ceiling was 1.033x."
            ),
            "VALID-PROFILE",
            False,
        ),
    ]
    heading = "2026-07-27 REJECT selfcheck"
    for label, body, expected_class, expected_falsifiable in synthetic_rows:
        checks += 1
        actual_class = classify(heading, body)
        actual_falsifiable, _ = falsifiable(heading, body)
        if (actual_class, actual_falsifiable) != (
            expected_class,
            expected_falsifiable,
        ):
            failures.append(
                f"{label}: expected {(expected_class, expected_falsifiable)}, "
                f"got {(actual_class, actual_falsifiable)}"
            )

    digest = "a" * 64
    checks += 2
    if has_loaded_elf_sha(
        f"Adjacent shell step reported binary sha256={digest}; process printed no identity."
    ):
        failures.append("adjacent shell SHA incorrectly satisfies KEEP provenance")
    if not has_loaded_elf_sha(
        f"bench_elf_sha256={digest} (13155240 bytes) /tmp/pkg/_fnx.abi3.so"
    ):
        failures.append("in-process bench_elf_sha256 does not satisfy KEEP provenance")

    own_sentinels = [
        ("pre-size durability envelope JSON", "VALID-AB"),
        ("core-laggard display-key probes", "VOID-NONULL"),
        ("REJECT (br-r37-c1-2zn1u): AVX2 dense-linalg", "VOID-NONULL"),
        (
            "LEDGER-INTEGRITY CORRECTION: the StackCanon REJECT itself is INVALID",
            "VOID-ZEROSELF",
        ),
        ("corrected long-warm retry hit a contended worker", "VOID-CV"),
        (
            "VALID-PROFILE ADMISSION REJECT (`Graph.has_edge` exact-string",
            "VALID-PROFILE",
        ),
    ]
    own_rows = []
    for path in LEDGERS:
        if path.exists():
            own_rows.extend(
                (path.name, row_heading, body)
                for row_heading, body in sections(
                    path.read_text(encoding="utf-8", errors="replace")
                )
            )
    for fragment, expected_class in own_sentinels:
        checks += 1
        matches = [
            (fname, row_heading, body)
            for fname, row_heading, body in own_rows
            if fragment in row_heading
        ]
        if len(matches) != 1:
            failures.append(
                f"own-ledger sentinel {fragment!r}: expected one row, found {len(matches)}"
            )
            continue
        fname, row_heading, body = matches[0]
        actual_class = classify(row_heading, body)
        if actual_class != expected_class:
            failures.append(
                f"{fname}: {fragment!r}: expected {expected_class}, got {actual_class}"
            )

    if failures:
        print(f"gate selfcheck: FAIL ({len(failures)} defect(s), {checks} checks)")
        for failure in failures:
            print(f"  - {failure}")
        return 2
    if not quiet:
        print(
            f"gate selfcheck: PASS ({checks} checks; "
            f"own_ledger_sentinels={len(own_sentinels)}/{len(own_sentinels)})"
        )
    return 0


def cmd_check_staged() -> int:
    if cmd_selfcheck(quiet=True) != 0:
        print("BLOCKED: the staged gate failed its own defect-class selfcheck.")
        return 2
    return cmd_check_rows(staged_sections(), "in the staged index")


def cmd_prior_art(terms: list[str]) -> int:
    needles = search_tokens(" ".join(terms))
    if not needles:
        print("usage: --prior-art TERM [TERM ...]")
        return 64
    hits = []
    for path in LEDGERS:
        if not path.exists():
            continue
        for heading, body in sections(path.read_text(encoding="utf-8", errors="replace")):
            hay = (heading + "\n" + body).lower()
            if all(n in hay for n in needles):
                hits.append(
                    (
                        path.name,
                        heading,
                        body,
                        is_rejection(heading),
                        classify(heading, body),
                    )
                )
    if not hits:
        print(f"prior-art: no ledger row matches {needles} — proceed")
        return 0
    rejects = [hit for hit in hits if hit[3]]
    for fname, heading, body, is_rej, cls in hits:
        kind = f"REJECT/{cls}" if is_rej else "other"
        print(f"  [{kind:<22}] {fname}: {heading[:96]}")
        predicate = retry_predicate(body)
        if predicate is not None:
            print(f"    retry_predicate={predicate}")
    if rejects:
        print(
            f"\nBLOCKED: {len(rejects)} prior REJECT row(s) match this lever. Read them in full "
            "before\nproposing it. If a row is VOID-* the rejection is not evidence and you may "
            "re-run it —\nsay so explicitly in the new row and cite the old one."
        )
        return 2
    return 0


def cmd_candidate(lever: str, surface: str) -> int:
    """Structured prior-art preflight modeled on frankensqlite's candidate key."""
    lever_tokens = search_tokens(lever)
    surface_tokens = search_tokens(surface)
    if not lever_tokens or not surface_tokens:
        print("usage: --candidate --lever TEXT --surface TEXT", file=sys.stderr)
        return 64

    hits = []
    for path in LEDGERS:
        if not path.exists():
            continue
        for heading, body in sections(path.read_text(encoding="utf-8", errors="replace")):
            hay = (heading + "\n" + body).lower()
            if not all(contains_search_token(hay, token) for token in surface_tokens):
                continue
            lever_overlap = sum(
                contains_search_token(hay, token) for token in lever_tokens
            )
            heading_lower = heading.lower()
            if lever_overlap == 0 and not all(
                contains_search_token(heading_lower, token)
                for token in surface_tokens
            ):
                continue
            hits.append(
                (
                    lever_overlap,
                    path.name,
                    heading,
                    body,
                    is_rejection(heading),
                    classify(heading, body),
                )
            )

    if not hits:
        print(
            f"candidate: no ledger row matches surface={surface!r}; "
            f"lever_tokens={lever_tokens} — proceed"
        )
        return 0

    hits.sort(key=lambda hit: (-hit[0], hit[1], hit[2]))
    rejects = [hit for hit in hits if hit[4]]
    print(
        f"candidate: lever={lever!r} surface={surface!r} "
        f"matched_rows={len(hits)}"
    )
    for overlap, fname, heading, body, is_rej, cls in hits:
        kind = f"REJECT/{cls}" if is_rej else ("KEEP" if is_keep(heading) else "other")
        print(
            f"  [{kind:<22}] overlap={overlap}/{len(lever_tokens)} "
            f"{fname}: {heading[:96]}"
        )
        predicate = retry_predicate(body)
        if predicate is not None:
            print(f"    retry_predicate={predicate}")

    if rejects:
        print(
            f"\nBLOCKED: {len(rejects)} prior REJECT row(s) exist on target surface "
            f"{surface!r}. Read and adjudicate them before editing. VOID-* rows may be "
            "re-run only when the new row says why; VALID-* rows require their recorded "
            "retry predicate."
        )
        return 2
    return 0


def cmd_audit() -> int:
    counts: dict[str, int] = {}
    total = 0
    keep_total = 0
    keep_with_loaded_elf = 0
    for path in LEDGERS:
        if not path.exists():
            continue
        for heading, body in sections(path.read_text(encoding="utf-8", errors="replace")):
            if is_rejection(heading):
                total += 1
                classification = classify(heading, body)
                counts[classification] = counts.get(classification, 0) + 1
            elif is_keep(heading):
                keep_total += 1
                keep_with_loaded_elf += int(has_loaded_elf_sha(body))
    void = sum(v for k, v in counts.items() if k.startswith("VOID"))
    print(f"rejection rows audited : {total}")
    for key in sorted(counts):
        print(f"  {key:<16}: {counts[key]:>4}")
    if total:
        print(f"  {'VOID total':<16}: {void:>4} / {total} = {void / total * 100:.1f}%")
    print(f"KEEP rows audited      : {keep_total}")
    print(
        f"  {'loaded ELF sha':<16}: {keep_with_loaded_elf:>4} / {keep_total}"
        if keep_total
        else f"  {'loaded ELF sha':<16}:    0 / 0"
    )
    print(f"  {'missing ELF sha':<16}: {keep_total - keep_with_loaded_elf:>4}")
    return 0


def candidate_options(args: list[str]) -> tuple[str, str] | None:
    values: dict[str, str] = {}
    index = 0
    while index < len(args):
        name = args[index]
        if name not in {"--lever", "--surface"} or name in values:
            return None
        index += 1
        if index >= len(args) or not args[index].strip():
            return None
        values[name] = args[index]
        index += 1
    if set(values) != {"--lever", "--surface"}:
        return None
    return values["--lever"], values["--surface"]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return cmd_check_staged()
    mode = argv[1]
    try:
        if mode == "--check":
            return cmd_check(argv[2] if len(argv) > 2 else "origin/main")
        if mode == "--check-staged":
            return cmd_check_staged()
        if mode == "--candidate":
            options = candidate_options(argv[2:])
            if options is None:
                print("usage: --candidate --lever TEXT --surface TEXT", file=sys.stderr)
                return 64
            return cmd_candidate(*options)
        if mode == "--prior-art":
            return cmd_prior_art(argv[2:])
        if mode == "--audit":
            return cmd_audit()
        if mode == "--selfcheck":
            return cmd_selfcheck()
        if mode in {"-h", "--help"}:
            print(__doc__)
            return 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"preflight error: {error}", file=sys.stderr)
        return 64
    print(__doc__)
    return 64


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
