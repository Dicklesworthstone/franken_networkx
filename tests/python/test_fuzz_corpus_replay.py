"""scripts/fuzz_corpus_replay.py must fail when any fuzz input fails (hhj5p.1).

The gate replays each target's committed corpus through its libFuzzer binary
with -runs=0. Fake binaries stand in for libFuzzer here so each verdict path is
exercised: a crash, an exit 0 that replayed nothing, and a missing binary all
fail; only an exit 0 that reports its runs passes. The replay against the real
binaries is the DSR check itself.
"""

from __future__ import annotations

import importlib.util
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "fuzz_corpus_replay.py"


def _load_replay():
    spec = importlib.util.spec_from_file_location("fuzz_corpus_replay", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


replay = _load_replay()

PASS = 'echo "INFO: Running with entropic power schedule"\necho "Done 3 runs in 0 second(s)"\nexit 0\n'
CRASH = (
    'echo "thread \'<unnamed>\' panicked at src/lib.rs:344: index out of bounds" >&2\n'
    'echo "==7== ERROR: libFuzzer: deadly signal" >&2\nexit 77\n'
)
SILENT = 'echo "INFO: seed corpus: files: 0"\nexit 0\n'


def _fuzz_dir(tmp_path, targets, *, reproducers=()):
    """A fuzz crate layout: Cargo.toml, corpus dirs, and fake binaries."""
    fuzz = tmp_path / "fuzz"
    release = replay.binary_path(fuzz, "x").parent
    release.mkdir(parents=True)
    bins = []
    for name, body in targets.items():
        bins.append(f'[[bin]]\nname = "{name}"\npath = "fuzz_targets/{name}.rs"\n')
        corpus = fuzz / "corpus" / name
        corpus.mkdir(parents=True)
        (corpus / "seed").write_bytes(b"0 1\n")
        if body is not None:
            binary = release / name
            binary.write_text(f'#!/bin/sh\necho "$@" > "{fuzz}/{name}.argv"\n{body}')
            binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    for name in reproducers:
        artifacts = fuzz / "artifacts" / name
        artifacts.mkdir(parents=True)
        (artifacts / "crash-0").write_bytes(b"x")
    (fuzz / "Cargo.toml").write_text('[package]\nname = "fnx-fuzz"\n\n' + "\n".join(bins))
    return fuzz


def test_targets_are_the_declared_bins_that_have_a_corpus(tmp_path):
    fuzz = _fuzz_dir(tmp_path, {"fuzz_a": PASS, "fuzz_b": PASS})
    text = (fuzz / "Cargo.toml").read_text()
    (fuzz / "Cargo.toml").write_text(text + '\n[[bin]]\nname = "fuzz_no_corpus"\npath = "x.rs"\n')
    assert replay.fuzz_targets(fuzz) == ["fuzz_a", "fuzz_b"]


def test_the_build_queues_for_a_worker_and_instruments_only_the_target(tmp_path):
    # A DSR run on 2026-09-24 failed this check with "no admissible workers"
    # (rch exit 103) because the build did not ask rch to queue.
    command, env = replay.build_command(3, tmp_path / "fuzz")
    assert command[:4] == ["rch", "exec", "--", "cargo"]
    assert env["RCH_QUEUE_WHEN_BUSY"] == "1"
    assert env["CARGO_TARGET_DIR"] == str(tmp_path / "fuzz" / "target")
    assert command[command.index("-j") + 1] == "3"
    assert command[command.index("--target") + 1] == replay.TRIPLE
    flags = command[command.index("--config") + 1]
    assert flags.startswith("build.rustflags=[") and "-Cpasses=sancov-module" in flags
    assert '"--cfg","fuzzing"' in flags


class _FakeRun:
    """Stands in for subprocess.run, returning the given exit codes in turn."""

    def __init__(self, codes):
        self.codes, self.calls = list(codes), 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return subprocess.CompletedProcess(args, self.codes.pop(0))


def test_the_build_retries_rch_refusals_a_bounded_number_of_times(tmp_path, monkeypatch, capsys):
    # The second DSR run on 2026-09-24 failed this check: every rch worker was
    # under critical pressure or short of slots, which RCH_QUEUE_WHEN_BUSY
    # does not wait out.
    monkeypatch.setattr(replay.time, "sleep", lambda seconds: None)
    fake = _FakeRun([103, 103, 0])
    monkeypatch.setattr(replay.subprocess, "run", fake)
    replay.build(2, tmp_path, attempts=5, wait_seconds=1)
    assert fake.calls == 3
    assert capsys.readouterr().out.count("rch admitted no worker") == 2

    fake = _FakeRun([103] * 3)
    monkeypatch.setattr(replay.subprocess, "run", fake)
    with pytest.raises(SystemExit, match="exit 103, attempt 3 of 3"):
        replay.build(2, tmp_path, attempts=3, wait_seconds=1)
    assert fake.calls == 3


def test_a_real_build_failure_is_not_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(replay.time, "sleep", lambda seconds: None)
    fake = _FakeRun([101, 0])
    monkeypatch.setattr(replay.subprocess, "run", fake)
    with pytest.raises(SystemExit, match="exit 101, attempt 1 of 20"):
        replay.build(2, tmp_path)
    assert fake.calls == 1


def test_the_repo_declares_a_corpus_for_every_fuzz_bin():
    declared = replay.BIN_RE.findall((replay.FUZZ / "Cargo.toml").read_text())
    assert declared, "no [[bin]] parsed from fuzz/Cargo.toml"
    assert replay.fuzz_targets() == declared


def test_a_passing_replay_runs_the_corpus_and_the_reproducers_once(tmp_path):
    fuzz = _fuzz_dir(tmp_path, {"fuzz_a": PASS}, reproducers=["fuzz_a"])
    result = replay.replay("fuzz_a", fuzz_dir=fuzz, input_timeout=9, rss_limit_mb=123)
    assert result["ok"], result
    assert result["summary"].startswith("Done 3 runs")
    argv = (fuzz / "fuzz_a.argv").read_text().split()
    assert argv[:2] == [str(fuzz / "corpus" / "fuzz_a"), str(fuzz / "artifacts" / "fuzz_a")]
    assert "-runs=0" in argv and not any(a.startswith("-max_total_time") for a in argv)
    assert "-timeout=9" in argv and "-rss_limit_mb=123" in argv
    assert f"-artifact_prefix={fuzz / 'artifacts' / 'fuzz_a'}/" in argv


# libFuzzer writes the inputs it finds into the first directory on its command line.
WRITES_TO_FIRST_DIR = 'echo found > "$1/new-input"\n' + PASS


def test_a_budget_fuzzes_after_the_replay_without_touching_the_committed_corpus(tmp_path):
    fuzz = _fuzz_dir(tmp_path, {"fuzz_a": WRITES_TO_FIRST_DIR}, reproducers=["fuzz_a"])
    corpus = fuzz / "corpus" / "fuzz_a"
    result = replay.replay("fuzz_a", fuzz_dir=fuzz, budget_seconds=5)
    assert result["ok"], result
    argv = (fuzz / "fuzz_a.argv").read_text().split()
    assert "-max_total_time=5" in argv and "-runs=0" not in argv
    assert argv[1:3] == [str(corpus), str(fuzz / "artifacts" / "fuzz_a")]
    assert not argv[0].startswith(str(fuzz))
    assert sorted(p.name for p in corpus.iterdir()) == ["seed"]
    assert sorted(p.name for p in (fuzz / "artifacts" / "fuzz_a").iterdir()) == ["crash-0"]


def test_a_crashing_input_fails_the_target_and_keeps_the_log(tmp_path):
    fuzz = _fuzz_dir(tmp_path, {"fuzz_a": CRASH})
    result = replay.replay("fuzz_a", fuzz_dir=fuzz)
    assert not result["ok"]
    assert result["summary"].startswith("exit 77")
    assert "deadly signal" in result["log"] and "index out of bounds" in result["log"]


def test_exit_zero_without_a_run_count_is_not_a_pass(tmp_path):
    fuzz = _fuzz_dir(tmp_path, {"fuzz_a": SILENT})
    assert not replay.replay("fuzz_a", fuzz_dir=fuzz)["ok"]


def test_a_missing_binary_fails(tmp_path):
    fuzz = _fuzz_dir(tmp_path, {"fuzz_a": None})
    result = replay.replay("fuzz_a", fuzz_dir=fuzz)
    assert not result["ok"] and "missing binary" in result["summary"]


def test_main_exits_nonzero_and_names_the_failing_target(tmp_path, capsys):
    fuzz = _fuzz_dir(tmp_path, {"fuzz_a": PASS, "fuzz_b": CRASH, "fuzz_c": PASS})
    assert replay.main(["--no-build", "--fuzz-dir", str(fuzz)]) == 1
    out = capsys.readouterr().out
    assert "FAIL fuzz_b" in out
    assert "TOTAL 3 targets, 1 failed: ['fuzz_b']" in out


def test_main_passes_only_when_every_target_passes(tmp_path, capsys):
    fuzz = _fuzz_dir(tmp_path, {"fuzz_a": PASS, "fuzz_c": PASS})
    assert replay.main(["--no-build", "--fuzz-dir", str(fuzz)]) == 0
    out = capsys.readouterr().out
    assert "TOTAL 2 targets, 0 failed" in out and "cpu-seconds, budget 0s per target" in out


def test_main_refuses_when_there_is_nothing_to_replay(tmp_path):
    fuzz = tmp_path / "fuzz"
    fuzz.mkdir()
    (fuzz / "Cargo.toml").write_text('[package]\nname = "fnx-fuzz"\n')
    assert replay.main(["--no-build", "--fuzz-dir", str(fuzz)]) == 2
