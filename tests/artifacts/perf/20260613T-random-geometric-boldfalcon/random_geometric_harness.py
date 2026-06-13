#!/usr/bin/env python3
"""Focused random_geometric_graph benchmark and golden harness."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import pstats
import shlex
import statistics
import subprocess
import sys
import time


CASE = {
    "n": 800,
    "radius": 0.08,
    "seed": 3,
}


def load_fnx(repo_root: Path, extension: Path):
    package_dir = repo_root / "python"
    sys.path.insert(0, str(package_dir))
    spec = importlib.util.spec_from_file_location("franken_networkx._fnx", extension)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load extension from {extension}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["franken_networkx._fnx"] = module
    spec.loader.exec_module(module)
    import franken_networkx as fnx

    return fnx


def graph_payload(graph):
    return {
        "directed": graph.is_directed(),
        "multigraph": graph.is_multigraph(),
        "graph": sorted((str(k), repr(v)) for k, v in graph.graph.items()),
        "nodes": [
            [repr(node), sorted((str(k), repr(v)) for k, v in data.items())]
            for node, data in graph.nodes(data=True)
        ],
        "edges": [
            [repr(u), repr(v), sorted((str(k), repr(vv)) for k, vv in data.items())]
            for u, v, data in graph.edges(data=True)
        ],
    }


def digest_payload(payload) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def make_graph(impl, args):
    if impl == "fnx":
        fnx = load_fnx(args.repo_root, args.extension)
        return fnx.random_geometric_graph(**CASE)
    import networkx as nx

    return nx.random_geometric_graph(**CASE)


def make_factory(impl, args):
    if impl == "fnx":
        fnx = load_fnx(args.repo_root, args.extension)
        return lambda: fnx.random_geometric_graph(**CASE)
    import networkx as nx

    return lambda: nx.random_geometric_graph(**CASE)


def command_env(args):
    try:
        import scipy
        scipy_version = scipy.__version__
    except Exception as exc:  # noqa: BLE001 - diagnostic artifact only.
        scipy_version = f"unavailable: {type(exc).__name__}: {exc}"

    result = {
        "cwd": str(args.repo_root),
        "executable": sys.executable,
        "git_head": subprocess.check_output(
            ["git", "-C", str(args.repo_root), "rev-parse", "HEAD"],
            text=True,
        ).strip(),
        "platform": platform.platform(),
        "python": sys.version,
        "scipy": scipy_version,
    }
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


def command_golden(args):
    fnx_graph = make_graph("fnx", args)
    nx_graph = make_graph("nx", args)
    fnx_payload = graph_payload(fnx_graph)
    nx_payload = graph_payload(nx_graph)
    result = {
        "case": CASE,
        "fnx_sha256": digest_payload(fnx_payload),
        "nx_sha256": digest_payload(nx_payload),
        "match": fnx_payload == nx_payload,
        "node_count": fnx_graph.number_of_nodes(),
        "edge_count": fnx_graph.number_of_edges(),
        "fnx_first_edges": fnx_payload["edges"][:12],
        "nx_first_edges": nx_payload["edges"][:12],
        "fnx_last_edges": fnx_payload["edges"][-12:],
        "nx_last_edges": nx_payload["edges"][-12:],
        "first_positions": fnx_payload["nodes"][:6],
        "last_positions": fnx_payload["nodes"][-6:],
    }
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["match"] else 1


def command_bench(args):
    factory = make_factory(args.impl, args)
    samples = []
    for _ in range(args.warmups):
        factory()
    for _ in range(args.loops):
        start = time.perf_counter()
        graph = factory()
        elapsed = time.perf_counter() - start
        samples.append(elapsed)
        if graph.number_of_nodes() != CASE["n"]:
            raise AssertionError("random_geometric_graph node count changed")
    result = {
        "case": CASE,
        "impl": args.impl,
        "loops": args.loops,
        "warmups": args.warmups,
        "median_seconds": statistics.median(samples),
        "mean_seconds": statistics.fmean(samples),
        "min_seconds": min(samples),
        "max_seconds": max(samples),
        "samples_seconds": samples,
    }
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


def command_profile(args):
    factory = make_factory(args.impl, args)
    profile = cProfile.Profile()
    profile.enable()
    for _ in range(args.loops):
        factory()
    profile.disable()
    stats = pstats.Stats(profile).sort_stats("cumulative")
    stats.print_stats(args.limit)
    return 0


def command_loop(args):
    factory = make_factory(args.impl, args)
    total = 0
    for _ in range(args.repeat):
        graph = factory()
        total += graph.number_of_nodes() + graph.number_of_edges()
    print(total)
    return 0


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def run_capture_json(args, command_args):
    command = [sys.executable, str(Path(__file__).resolve())]
    command.extend(["--repo-root", str(args.repo_root)])
    command.extend(["--extension", str(args.extension)])
    command.extend(command_args)
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def run_capture_text(args, command_args) -> str:
    command = [sys.executable, str(Path(__file__).resolve())]
    command.extend(["--repo-root", str(args.repo_root)])
    command.extend(["--extension", str(args.extension)])
    command.extend(command_args)
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return completed.stdout


def command_collect(args):
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix

    env = run_capture_json(args, ["env"])
    write_json(args.output_dir / "env.json", env)

    golden = run_capture_json(args, ["golden"])
    write_json(args.output_dir / f"{prefix}_golden.json", golden)

    bench_fnx = run_capture_json(
        args,
        [
            "bench",
            "--impl",
            "fnx",
            "--loops",
            str(args.loops),
            "--warmups",
            str(args.warmups),
        ],
    )
    write_json(args.output_dir / f"{prefix}_bench_fnx.json", bench_fnx)

    bench_nx = run_capture_json(
        args,
        [
            "bench",
            "--impl",
            "nx",
            "--loops",
            str(args.loops),
            "--warmups",
            str(args.warmups),
        ],
    )
    write_json(args.output_dir / f"{prefix}_bench_nx.json", bench_nx)

    profile_text = run_capture_text(
        args,
        ["profile", "--impl", "fnx", "--loops", str(args.profile_loops)],
    )
    (args.output_dir / f"{prefix}_profile_fnx.txt").write_text(profile_text)

    hyperfine_cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--repo-root",
        str(args.repo_root),
        "--extension",
        str(args.extension),
        "loop",
        "--impl",
        "fnx",
        "--repeat",
        str(args.hyperfine_repeat),
    ]
    hyperfine_json = args.output_dir / f"{prefix}_hyperfine_fnx_loop{args.hyperfine_repeat}.json"
    subprocess.run(
        [
            "hyperfine",
            "--warmup",
            str(args.hyperfine_warmup),
            "--runs",
            str(args.hyperfine_runs),
            "--export-json",
            str(hyperfine_json),
            " ".join(shlex.quote(part) for part in hyperfine_cmd),
        ],
        check=True,
    )

    hash_paths = [
        args.output_dir / "env.json",
        args.output_dir / f"{prefix}_golden.json",
        args.output_dir / f"{prefix}_bench_fnx.json",
        args.output_dir / f"{prefix}_bench_nx.json",
        args.output_dir / f"{prefix}_profile_fnx.txt",
        hyperfine_json,
    ]
    lines = []
    for path in hash_paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path}")
    (args.output_dir / f"{prefix}_artifact_sha256.txt").write_text(
        "\n".join(lines) + "\n"
    )
    return 0


def command_parity(args):
    fnx = load_fnx(args.repo_root, args.extension)
    import networkx as nx

    cases = [
        (4, 1.0, 2, {0: (0, 0), 1: (1, 0), 2: (1, 1), 3: (0, 1)}, float("inf"), "pos"),
        (25, 0.25, 2, {i: (i * 0.1, (i * 0.17) % 1.0) for i in range(25)}, 1, "pos"),
        (25, 0.25, 2, {i: (i * 0.1, (i * 0.17) % 1.0) for i in range(25)}, 3, "xy"),
        (800, 0.08, 2, None, 2, "pos"),
    ]
    payloads = []
    for n, radius, dim, pos, p, pos_name in cases:
        kwargs = {"dim": dim, "pos": pos, "p": p, "seed": 3, "pos_name": pos_name}
        fnx_graph = fnx.random_geometric_graph(n, radius, **kwargs)
        nx_graph = nx.random_geometric_graph(n, radius, **kwargs)
        fnx_payload = graph_payload(fnx_graph)
        nx_payload = graph_payload(nx_graph)
        if fnx_payload != nx_payload:
            raise AssertionError((n, radius, dim, p, pos_name))
        payloads.append(
            {
                "n": n,
                "radius": radius,
                "dim": dim,
                "p": repr(p),
                "pos_name": pos_name,
                "sha256": digest_payload(fnx_payload),
                "nodes": fnx_graph.number_of_nodes(),
                "edges": fnx_graph.number_of_edges(),
            }
        )

    error_cases = []
    for kwargs in [
        {"n": -5, "radius": 0.5},
        {"n": 5, "radius": 0.5, "dim": 0},
        {"n": 5, "radius": 0.5, "seed": float("nan")},
    ]:
        fnx_error = None
        nx_error = None
        try:
            fnx.random_geometric_graph(**kwargs)
        except Exception as exc:  # noqa: BLE001 - parity harness captures type/message.
            fnx_error = (type(exc).__name__, str(exc))
        try:
            nx.random_geometric_graph(**kwargs)
        except Exception as exc:  # noqa: BLE001 - parity harness captures type/message.
            nx_error = (type(exc).__name__, str(exc))
        if fnx_error != nx_error:
            raise AssertionError((kwargs, fnx_error, nx_error))
        error_cases.append({"kwargs": repr(kwargs), "error": fnx_error})

    result = {
        "cases": payloads,
        "errors": error_cases,
    }
    result["sha256"] = digest_payload(result)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("env")
    subparsers.add_parser("golden")

    bench = subparsers.add_parser("bench")
    bench.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench.add_argument("--loops", type=int, default=41)
    bench.add_argument("--warmups", type=int, default=7)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--impl", choices=("fnx", "nx"), required=True)
    profile.add_argument("--loops", type=int, default=1)
    profile.add_argument("--limit", type=int, default=50)

    loop = subparsers.add_parser("loop")
    loop.add_argument("--impl", choices=("fnx", "nx"), required=True)
    loop.add_argument("--repeat", type=int, default=10)

    collect = subparsers.add_parser("collect")
    collect.add_argument("--prefix", required=True)
    collect.add_argument("--output-dir", type=Path, required=True)
    collect.add_argument("--loops", type=int, default=41)
    collect.add_argument("--warmups", type=int, default=7)
    collect.add_argument("--profile-loops", type=int, default=1)
    collect.add_argument("--hyperfine-runs", type=int, default=10)
    collect.add_argument("--hyperfine-warmup", type=int, default=3)
    collect.add_argument("--hyperfine-repeat", type=int, default=10)

    subparsers.add_parser("parity")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "env":
        return command_env(args)
    if args.command == "golden":
        return command_golden(args)
    if args.command == "bench":
        return command_bench(args)
    if args.command == "profile":
        return command_profile(args)
    if args.command == "loop":
        return command_loop(args)
    if args.command == "collect":
        return command_collect(args)
    if args.command == "parity":
        return command_parity(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
