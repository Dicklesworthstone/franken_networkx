#!/usr/bin/env python3
"""Ledger preflight — make an unfalsifiable verdict impossible, not merely discouraged.

Adopted 2026-07-25 from frankensqlite's `sql_pipeline_candidate_preflight` after the
fleet resurrection audit showed ledger integrity DECAYS: the one repo that audited once
and then mechanically enforced the check sits at 1.7% VOID, while repos that never did
sit at 25-91%. The current franken_networkx audit measures 75.6% VOID (133/176
rejection rows) under the six-class taxonomy, of which **122 are VOID-NONULL** — an
A/B ran, the row was rejected
on a near-1.0 wall ratio, and neither an A/A null control nor a counted mechanism was
recorded, so the lever cannot be distinguished from the harness.

Exit codes (frankensqlite convention):
  0  OK
  2  BLOCKED — a new verdict row is unfalsifiable, or prior art exists for a lever
 64  USAGE / IO ERROR

Modes
-----
--check [REF]      Every rejection row added or modified since REF (default: origin/main)
                   must carry
                   an A/A null control OR a counted mechanism. Every KEEP must carry the
                   in-process ELF SHA-256, a numeric A/A null, median-CI-only decision
                   metadata, and an explicit INCUMBENT or SELF-SPEEDUP comparison class.
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
                   escape rows. It also proves that a self-speedup cannot pass as campaign
                   output. This runs inside --check-staged.

KEEP comparison contract (machine-readable lines)
  comparison_class=INCUMBENT
  incumbent=networkx
  incumbent_same_invocation=true
  incumbent_ratio=1.234x
  campaign_output=true
  decision_gate=median_ci
  cv_role=report_only

or:
  comparison_class=SELF-SPEEDUP
  campaign_output=false
  decision_gate=median_ci
  cv_role=report_only

INCUMBENT means the actual legacy NetworkX implementation ran side-by-side in the same
invocation and the recorded ratio is greater than 1.0x. SELF-SPEEDUP is maintenance:
it may ship, but it cannot use a WIN heading or make a competitive claim.

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
# Policy 2 uses exact fields rather than prose inference. A self-speedup row can
# mention NetworkX while explaining a public loss; searching for "NetworkX" plus
# "same invocation" would therefore misclassify maintenance as campaign output.
COMPARISON_CLASS = re.compile(
    r"^\s*comparison_class\s*=\s*(INCUMBENT|SELF-SPEEDUP)\s*$",
    re.I | re.M,
)
INCUMBENT_NAME = re.compile(r"^\s*incumbent\s*=\s*networkx\s*$", re.I | re.M)
INCUMBENT_SAME_INVOCATION = re.compile(
    r"^\s*incumbent_same_invocation\s*=\s*true\s*$",
    re.I | re.M,
)
INCUMBENT_RATIO = re.compile(
    r"^\s*incumbent_ratio\s*=\s*(\d+(?:,\d{3})*(?:\.\d+)?)x\s*$",
    re.I | re.M,
)
CAMPAIGN_OUTPUT_TRUE = re.compile(
    r"^\s*campaign_output\s*=\s*true\s*$",
    re.I | re.M,
)
CAMPAIGN_OUTPUT_FALSE = re.compile(
    r"^\s*campaign_output\s*=\s*false\s*$",
    re.I | re.M,
)
DECISION_GATE_MEDIAN_CI = re.compile(
    r"^\s*decision_gate\s*=\s*median_ci\s*$",
    re.I | re.M,
)
CV_REPORT_ONLY = re.compile(
    r"^\s*cv_role\s*=\s*report_only\s*$",
    re.I | re.M,
)
# Every field a verdict is read off, captured with its value so that flipping
# one — INCUMBENT to SELF-SPEEDUP, a ratio, campaign_output — re-adjudicates
# the row even though the surrounding prose is untouched.
CLAIM_FIELD = re.compile(
    r"^\s*(comparison_class|incumbent|incumbent_same_invocation|incumbent_ratio|"
    r"campaign_output|decision_gate|cv_role|bench_elf_sha256)\s*=\s*(.+?)\s*$",
    re.I | re.M,
)
# A verdict is a number. Any digit that moves, anywhere in the body, is a claim
# change: ratios, CI bounds, round counts, self-time percentages, node counts.
CLAIM_NUMERAL = re.compile(r"\d+(?:[.,]\d+)*")
# Binary/input identities are hex, so a changed digest need not change a digit.
CLAIM_DIGEST = re.compile(r"\b[0-9a-f]{16,}\b", re.I)
COMPETITIVE_SELF_CLAIM = re.compile(
    r"\b(?:beats?|outperforms?)\s+(?:(?:the|actual|legacy)\s+)*"
    r"(?:networkx|incumbent)\b|"
    r"\bfaster\s+than\s+(?:networkx|(?:the\s+)?incumbent)\b",
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


def claim_class(heading: str, body: str) -> str:
    """Return the row's exact machine-readable comparison class."""
    del heading
    match = COMPARISON_CLASS.search(body)
    return match.group(1).upper() if match is not None else "UNLABELED"


def keep_contract(heading: str, body: str) -> tuple[bool, str, list[str]]:
    """Validate KEEP provenance, decision discipline, and comparison semantics."""
    problems = []
    if not has_loaded_elf_sha(body):
        problems.append("missing in-process loaded-ELF SHA-256")
    if not has_recorded_null(body):
        problems.append("missing numeric same-invocation A/A null control")
    if not DECISION_GATE_MEDIAN_CI.search(body):
        problems.append("missing decision_gate=median_ci")
    if not CV_REPORT_ONLY.search(body):
        problems.append("missing cv_role=report_only")

    comparison_class = claim_class(heading, body)
    if comparison_class == "UNLABELED":
        problems.append("missing comparison_class=INCUMBENT|SELF-SPEEDUP")
        return False, "KEEP-NO-COMPARISON-CLASS", problems

    if comparison_class == "INCUMBENT":
        if not INCUMBENT_NAME.search(body):
            problems.append("missing incumbent=networkx")
        if not INCUMBENT_SAME_INVOCATION.search(body):
            problems.append("missing incumbent_same_invocation=true")
        ratio_match = INCUMBENT_RATIO.search(body)
        if ratio_match is None:
            problems.append("missing numeric incumbent_ratio=<ratio>x")
        else:
            ratio = float(ratio_match.group(1).replace(",", ""))
            if ratio <= 1.0:
                problems.append("incumbent_ratio must be greater than 1.0x")
        if not CAMPAIGN_OUTPUT_TRUE.search(body):
            problems.append("missing campaign_output=true")
        if CAMPAIGN_OUTPUT_FALSE.search(body):
            problems.append("INCUMBENT row also declares campaign_output=false")
        label = "KEEP-INCUMBENT"
    else:
        if not CAMPAIGN_OUTPUT_FALSE.search(body):
            problems.append("missing campaign_output=false")
        if CAMPAIGN_OUTPUT_TRUE.search(body):
            problems.append("SELF-SPEEDUP row also declares campaign_output=true")
        if re.search(r"\bWIN\b", heading, re.I):
            problems.append("SELF-SPEEDUP cannot use a WIN heading")
        if COMPETITIVE_SELF_CLAIM.search(body):
            problems.append("SELF-SPEEDUP makes a competitive claim")
        label = "KEEP-SELF-SPEEDUP"
    return not problems, label, problems


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


def keyed_sections(text: str) -> dict[tuple[str, int], str]:
    """Index sections by heading plus occurrence, preserving duplicate headings."""
    occurrences: dict[str, int] = {}
    indexed = {}
    for heading, body in sections(text):
        occurrence = occurrences.get(heading, 0)
        occurrences[heading] = occurrence + 1
        indexed[(heading, occurrence)] = body
    return indexed


def claim_fingerprint(heading: str, body: str) -> tuple:
    """Everything about a row that a verdict can be read off.

    Two bodies with the same fingerprint state the same claim on the same
    evidence: same heading, same machine-readable contract fields, same
    numbers, same binary identities, and the same adjudication under every
    classifier in this file. Only the prose around them moved.
    """
    _ok, keep_label, keep_problems = keep_contract(heading, body)
    return (
        heading.strip(),
        tuple((key.lower(), value.lower()) for key, value in CLAIM_FIELD.findall(body)),
        tuple(CLAIM_NUMERAL.findall(body)),
        tuple(digest.lower() for digest in CLAIM_DIGEST.findall(body)),
        is_rejection(heading),
        is_keep(heading),
        classify(heading, body),
        has_recorded_null(body),
        has_counted_mechanism(body),
        has_loaded_elf_sha(body),
        keep_label,
        tuple(keep_problems),
    )


def changed_section_rows(path: Path, before: str, after: str):
    """Return every verdict section from ``after`` whose CLAIM is new or moved.

    A row is re-adjudicated when it is new, or when anything a verdict rests on
    changed: the heading, a contract field, any number, any binary digest, or
    any classifier's reading of the body. An edit that leaves all of those
    byte-identical is an annotation — reflowing prose, fixing Markdown, adding
    a cross-reference — and re-running today's contract over a row written
    under an older one would only strand the edit (br-r37-c1-qo7uf).

    This is not an escape hatch for stale rows: an annotation that publishes a
    NEW number moves the fingerprint and faces the full contract, which is the
    right outcome — the annotation is itself a measurement and must carry its
    own provenance.
    """
    before_sections = keyed_sections(before)
    rows = []
    for (heading, occurrence), body in keyed_sections(after).items():
        prior = before_sections.get((heading, occurrence))
        if prior == body:
            continue
        if prior is not None and claim_fingerprint(heading, prior) == claim_fingerprint(
            heading, body
        ):
            continue
        rows.append((path.name, heading, body))
    return rows


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


def added_sections(ref: str):
    """Sections added or modified on HEAD relative to the merge base with ``ref``."""
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

    merge_base = subprocess.run(
        ["git", "merge-base", ref, "HEAD"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    if merge_base.returncode != 0:
        raise RuntimeError((merge_base.stderr or merge_base.stdout).strip())
    base = merge_base.stdout.strip()

    out = []
    for path in LEDGERS:
        out.extend(
            changed_section_rows(
                path,
                git_text(base, path),
                git_text("HEAD", path),
            )
        )
    return out


def staged_sections():
    """Sections added or modified in the index, never the unstaged worktree."""
    out = []
    for path in LEDGERS:
        out.extend(
            changed_section_rows(
                path,
                git_text("HEAD", path),
                git_text(":", path),
            )
        )
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
            ok, cls, problems = keep_contract(heading, body)
            if not ok:
                bad_keeps.append((fname, heading, cls, problems))
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
                f"\n{len(bad_keeps)} KEEP row(s) violate the provenance/comparison contract. "
                "Every KEEP needs an in-process loaded-ELF SHA, a numeric A/A null, "
                "`decision_gate=median_ci`, and `cv_role=report_only`. It must then declare "
                "either a >1.0x same-invocation `incumbent=networkx` result with "
                "`campaign_output=true`, or `comparison_class=SELF-SPEEDUP` with "
                "`campaign_output=false`."
            )
            for fname, heading, _cls, problems in bad_keeps:
                print(f"  - {fname}: {heading[:72]}")
                for problem in problems:
                    print(f"      {problem}")
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

    common_keep = (
        f"bench_elf_sha256={digest} (13155240 bytes) /tmp/pkg/_fnx.abi3.so\n"
        "The same-invocation A/A null measured 1.001x with bootstrap CI "
        "[0.995,1.008].\n"
        "decision_gate=median_ci\n"
        "cv_role=report_only\n"
    )
    keep_rows = [
        (
            "valid incumbent campaign output",
            "2026-07-27 KEEP incumbent",
            common_keep
            + "comparison_class=INCUMBENT\n"
            + "incumbent=networkx\n"
            + "incumbent_same_invocation=true\n"
            + "incumbent_ratio=1.234x\n"
            + "campaign_output=true\n",
            True,
        ),
        (
            "incumbent missing same-invocation proof",
            "2026-07-27 KEEP incumbent",
            common_keep
            + "comparison_class=INCUMBENT\n"
            + "incumbent=networkx\n"
            + "incumbent_ratio=1.234x\n"
            + "campaign_output=true\n",
            False,
        ),
        (
            "incumbent loss cannot be campaign output",
            "2026-07-27 KEEP incumbent",
            common_keep
            + "comparison_class=INCUMBENT\n"
            + "incumbent=networkx\n"
            + "incumbent_same_invocation=true\n"
            + "incumbent_ratio=0.912x\n"
            + "campaign_output=true\n",
            False,
        ),
        (
            "valid maintenance self-speedup",
            "2026-07-27 KEEP maintenance",
            common_keep
            + "comparison_class=SELF-SPEEDUP\n"
            + "campaign_output=false\n",
            True,
        ),
        (
            "self-speedup cannot use WIN heading",
            "2026-07-27 WIN maintenance",
            common_keep
            + "comparison_class=SELF-SPEEDUP\n"
            + "campaign_output=false\n",
            False,
        ),
        (
            "self-speedup cannot claim incumbent victory",
            "2026-07-27 KEEP maintenance",
            common_keep
            + "comparison_class=SELF-SPEEDUP\n"
            + "campaign_output=false\n"
            + "This beats NetworkX on the fixture.\n",
            False,
        ),
    ]
    for label, keep_heading, keep_body, expected_ok in keep_rows:
        checks += 1
        actual_ok, _class, _problems = keep_contract(keep_heading, keep_body)
        if actual_ok != expected_ok:
            failures.append(
                f"{label}: expected keep_contract={expected_ok}, got {actual_ok}"
            )

    # br-r37-c1-qo7uf: a row is re-adjudicated when its CLAIM moves, never
    # because someone reflowed the prose around it. The legacy row below fails
    # today's KEEP contract, so if any of these edits reaches the validator the
    # commit is blocked — which is exactly right for four of the five.
    legacy_keep = (
        "## 2026-07-12 SHIPPED WIN: `grid_graph` UPGRADED to INDEX batch **12.6885x**\n"
        "\n"
        "MEASURED on grid_graph([100,100]) (10000 nodes, 19800 edges), 61 rounds:\n"
        "BATCH 12.6885x vs NULL 1.0159x [0.8168,1.2459]. Parity asserted on [4,5,6].\n"
    )
    annotation_cases = [
        (
            "cosmetic Markdown edit is an annotation",
            legacy_keep.replace("on [4,5,6]", "on shape `[4,5,6]`"),
            0,
        ),
        (
            "a moved ratio is a claim change",
            legacy_keep.replace("12.6885x**", "12.9885x**"),
            1,
        ),
        (
            "a moved null control is a claim change",
            legacy_keep.replace("1.0159x", "1.0159x [0.9,1.1] and"),
            1,
        ),
        (
            "declaring a comparison class is a claim change",
            legacy_keep + "comparison_class=INCUMBENT\n",
            1,
        ),
        (
            "an added row is validated as new",
            legacy_keep + "\n## 2026-08-15 KEEP: unrelated new verdict row\n\nNo evidence.\n",
            1,
        ),
    ]
    synthetic_path = Path("selfcheck-ledger.md")
    for label, after_text, expected_rows in annotation_cases:
        checks += 1
        actual_rows = len(changed_section_rows(synthetic_path, legacy_keep, after_text))
        if actual_rows != expected_rows:
            failures.append(
                f"{label}: expected {expected_rows} re-validated row(s), got {actual_rows}"
            )

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


PROOF_ROOT = "tests/artifacts/perf/"
# A proof directory is only held to the ledger when it CLAIMS something: both a
# gate marker and a ship/keep verdict. Exploratory sweeps and measured rejections
# are exactly what an artifact directory is for and are not required to appear.
_PROOF_GATE = re.compile(
    r"ADMISSIBLE|STRICT[- ]GATE|nulls? (?:pass|clean)|worst[ _]bound|CERTIFIED", re.I
)
_PROOF_VERDICT = re.compile(r"\bSHIPPED\b|\bKEEP\b|\bWIN\b", re.I)
_PROOF_BEAD = re.compile(r"br-[a-z0-9]+-c\d+-[a-z0-9.]+", re.I)


def staged_proof_dirs() -> list[tuple[str, set[str]]]:
    """(proof dir, bead ids) for proof-dir docs ADDED in this commit.

    Only newly staged files. The 16 pre-existing orphans this check was written
    for must not block anyone's unrelated commit — the point is to stop the
    inventory growing, not to hold the fleet hostage to its history.
    """
    try:
        names = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return []
    claims: dict[str, set[str]] = {}
    for name in names:
        if not name.startswith(PROOF_ROOT) or not name.endswith(".md"):
            continue
        try:
            text = git_text(":", REPO / name)
        except Exception:  # pragma: no cover - unreadable blob
            continue
        if not (_PROOF_GATE.search(text) and _PROOF_VERDICT.search(text)):
            continue
        parts = name.split("/")
        proof_dir = "/".join(parts[:3]) if len(parts) > 3 else name
        claims.setdefault(proof_dir, set()).update(
            b.lower() for b in _PROOF_BEAD.findall(text)
        )
    return sorted(claims.items())


def cmd_check_proof_dirs() -> int:
    """A newly added, certified proof dir must name a bead this ledger records.

    br-r37-c1-ml7s5. Measured on this repo: of 1065 proof directories, 21 carry
    BOTH a gate marker and a ship/keep verdict, and 16 of those cite a bead that
    appears in no ledger. Certified work that lives only in an artifact directory
    is work the next pane pays to measure again — four of the sixteen are levers
    this pane later re-derived from memory rather than from the ledger.

    Filing that inventory does not stop it growing. This does.
    """
    offenders = []
    ledger_text = ""
    for path in LEDGERS:
        try:
            ledger_text += path.read_text(errors="replace").lower()
        except OSError:
            continue
    for proof_dir, beads in staged_proof_dirs():
        if beads and any(b in ledger_text for b in beads):
            continue
        offenders.append((proof_dir, sorted(beads)))
    if not offenders:
        return 0
    print(
        f"BLOCKED: {len(offenders)} newly added proof dir(s) claim a certified "
        "result whose bead appears in no ledger."
    )
    for proof_dir, beads in offenders:
        named = ", ".join(beads) if beads else "NO BEAD ID IN THE DOCS"
        print(f"  - {proof_dir}: {named}")
    print(
        "  A proof directory that records a gate marker AND a ship/keep verdict "
        "is a certified result. Add its row to docs/NEGATIVE_EVIDENCE_cc.md in "
        "THIS commit, or drop the verdict wording if it is exploratory."
    )
    return 1


def cmd_check_staged() -> int:
    if cmd_selfcheck(quiet=True) != 0:
        print("BLOCKED: the staged gate failed its own defect-class selfcheck.")
        return 2
    rc = cmd_check_rows(staged_sections(), "in the staged index")
    proof_rc = cmd_check_proof_dirs()
    return rc or proof_rc


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
    claim_counts: dict[str, int] = {}
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
                claim_counts[claim_class(heading, body)] = (
                    claim_counts.get(claim_class(heading, body), 0) + 1
                )
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
    # Policy 2 decay signal: campaign output is the INCUMBENT count, not the KEEP
    # count. A ledger whose KEEP rows are overwhelmingly self-speedups is a ledger
    # full of maintenance, however large its multipliers look.
    incumbent = claim_counts.get("INCUMBENT", 0)
    for key in ("INCUMBENT", "SELF-SPEEDUP", "UNLABELED"):
        print(f"  {key.lower():<16}: {claim_counts.get(key, 0):>4}")
    if keep_total:
        print(
            f"  {'campaign output':<16}: {incumbent:>4} / {keep_total} = "
            f"{incumbent / keep_total * 100:.1f}% measured vs the incumbent"
        )
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
