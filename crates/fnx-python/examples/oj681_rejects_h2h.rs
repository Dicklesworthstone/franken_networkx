//! The two remaining br-r37-c1-oj681 rejects, re-measured with candidate-arm A/A nulls.
//!
//! br-r37-c1-oj681 lists three rejected levers that `scripts/perf_ledger_preflight.py` refuses
//! to admit (VOID-NONULL) because they were timed with plain repeat-min and no control. Item 3
//! was measured and landed in 51c693de8. These are items 1 and 2, which the bead says "need
//! the rejected variant restored to be measured, so they need a code arm, not just a harness
//! arm".
//!
//! Both turn out to be reachable WITHOUT restoring any code, which is why they are done
//! together here:
//!
//!   ITEM 2, MultiDiGraph dijkstra delegation (recorded 6.926 ms against 5.461 ms, worse).
//!   The rejected variant is "delegate to networkx instead of collapsing", and
//!   `_call_networkx_for_parity` — the helper the shipped code already uses for the cases it
//!   cannot handle — IS that variant. Both arms are called on the same graph and verified to
//!   return equal results before timing.
//!
//!   ITEM 1, the min-weight collapse rebuild (recorded 4.264 ms against 4.144 ms, 2.9% worse).
//!   The shipped line in `_multigraph_collapse_min_weight` is
//!   `simple.add_edges_from((u, v, {weight: w}) ...)`; the rejected variant is
//!   `simple.add_weighted_edges_from((u, v, w) ...)`. Both spellings are timed against the
//!   same `best` dict, which is derived from a real collapse pass rather than invented.
//!
//! ITEM 1 IS A BUILD/MUTATION ARM AND MAY NOT SURVIVE ITS OWN NULL. Mutation workloads are
//! non-stationary — the allocator is in a different state on every repeat — so its A/A null is
//! expected to be the fragile one. If it strays the row is WITHHELD rather than published,
//! which is the same standard that blocked these rows in the first place.
//!
//! Both are SELF-comparisons (fnx against fnx). That is MAINTENANCE evidence and the correct
//! shape for a REJECT verdict about our own lever; no vs-incumbent win is claimed.
//!
//! Results go to STDERR so the remote runner returns them.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use sha2::{Digest, Sha256};
use std::ffi::CString;

fn self_identity() -> String {
    let Ok(path) = std::env::current_exe() else {
        return "unavailable".to_owned();
    };
    let Ok(bytes) = std::fs::read(&path) else {
        return "unavailable".to_owned();
    };
    let mut hasher = Sha256::new();
    hasher.update(&bytes);
    format!("{:x} ({} bytes)", hasher.finalize(), bytes.len())
}

fn cstring(source: &str) -> CString {
    CString::new(source).expect("Python snippets must not contain NUL bytes")
}

fn preload_source() -> String {
    let repo_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(std::path::Path::parent)
        .expect("fnx-python crate must live under crates/")
        .to_str()
        .expect("repo path must be UTF-8");
    format!(
        "import importlib.util, os, sys
cwd = {repo_root:?}
for rel_path in ('python',):
    path = os.path.join(cwd, rel_path)
    if path not in sys.path:
        sys.path.insert(0, path)
available_cpus = sorted(os.sched_getaffinity(0))
if available_cpus:
    os.sched_setaffinity(0, set((available_cpus[-1],)))
    print(f'bench cpu: {{available_cpus[-1]}}', file=sys.stderr)
target_dir = os.environ.get('CARGO_TARGET_DIR') or os.path.join(cwd, 'target')
for path in (
    os.path.join(target_dir, 'release', 'lib_fnx.so'),
    os.path.join(target_dir, 'release', 'libfnx_python.so'),
    os.path.join(cwd, 'python', 'franken_networkx', '_fnx.abi3.so'),
):
    if os.path.exists(path):
        spec = importlib.util.spec_from_file_location('franken_networkx._fnx', path)
        module = importlib.util.module_from_spec(spec)
        sys.modules['franken_networkx._fnx'] = module
        spec.loader.exec_module(module)
        import hashlib
        with open(path, 'rb') as fh:
            _sha = hashlib.sha256(fh.read()).hexdigest()
        sys._fnx_ext = f'{{path}} sha256={{_sha}}'
        print(f'fnx extension: {{sys._fnx_ext}}', file=sys.stderr)
        break
"
    )
}

const HARNESS: &str = r#"
import random, statistics, time
import franken_networkx as fnx

import sys as _sys
FNX_EXT = getattr(_sys, "_fnx_ext", "unavailable")

N, DEG = 400, 3

def make_mdg(seed):
    rng = random.Random(seed)
    g = fnx.MultiDiGraph()
    g.add_nodes_from(range(N))
    for i in range(N):
        for _ in range(DEG):
            j = rng.randrange(N)
            if i != j:
                g.add_edge(i, j, weight=float(rng.randint(1, 9)))
    return g

def best_pairs(g, weight="weight"):
    """The per-pair minimum the shipped collapse computes, derived from a REAL graph so the
    rebuild arms are fed the same data the shipped line sees."""
    best = {}
    for u, v, k, attrs in g.edges(keys=True, data=True):
        w = attrs.get(weight, 1)
        pair = (u, v)
        if pair not in best or w < best[pair]:
            best[pair] = w
    return best

def timed(fn, rounds, inner):
    s = []
    for _ in range(rounds):
        t = time.perf_counter()
        for _ in range(inner):
            fn()
        s.append((time.perf_counter() - t) / inner)
    return s

def square(arms, rounds, inner):
    """ABBA over the arms dict; returns median seconds per call for each."""
    samples = {k: [] for k in arms}
    for r in range(rounds):
        order = list(arms) if r % 2 == 0 else list(arms)[::-1]
        for name in order:
            fn = arms[name]
            t = time.perf_counter()
            for _ in range(inner):
                fn()
            samples[name].append((time.perf_counter() - t) / inner)
    return {k: statistics.median(v) for k, v in samples.items()}

def item2(rounds=15, inner=3):
    """Shipped MultiDiGraph dijkstra against forced networkx delegation."""
    g1, g2 = make_mdg(7), make_mdg(8)     # g2 is the separately built A/A null fixture
    ship = lambda G: fnx.single_source_dijkstra(G, 0)
    dele = lambda G: fnx._call_networkx_for_parity(
        "single_source_dijkstra", G, 0, target=None, cutoff=None, weight="weight")
    equal = ship(g1) == dele(g1) and ship(g2) == dele(g2)
    arms = {"ship": lambda: ship(g1), "ship_null": lambda: ship(g2),
            "dele": lambda: dele(g1), "dele_null": lambda: dele(g2)}
    for fn in arms.values():
        fn()
    m = square(arms, rounds, inner)
    # ratio > 1 means DELEGATION is faster, i.e. the rejected lever would have been a win
    return (equal, m["ship"] / m["dele"], m["ship_null"] / m["ship"],
            m["dele_null"] / m["dele"], m["ship"] * 1e3, m["dele"] * 1e3)

def item1(rounds=15, inner=3):
    """The two collapse-rebuild spellings, same `best` dict, fresh target graph each call."""
    b1, b2 = best_pairs(make_mdg(7)), best_pairs(make_mdg(8))

    def shipped(best):
        s = fnx.DiGraph()
        s.add_nodes_from(range(N))
        s.add_edges_from((u, v, {"weight": w}) for (u, v), w in best.items())
        return s

    def rejected(best):
        s = fnx.DiGraph()
        s.add_nodes_from(range(N))
        s.add_weighted_edges_from(((u, v, w) for (u, v), w in best.items()), weight="weight")
        return s

    a, b = shipped(b1), rejected(b1)
    equal = (sorted(a.edges(data=True)) == sorted(b.edges(data=True)))
    arms = {"ship": lambda: shipped(b1), "ship_null": lambda: shipped(b2),
            "rej": lambda: rejected(b1), "rej_null": lambda: rejected(b2)}
    for fn in arms.values():
        fn()
    m = square(arms, rounds, inner)
    # ratio > 1 means add_weighted_edges_from is faster
    return (equal, m["ship"] / m["rej"], m["ship_null"] / m["ship"],
            m["rej_null"] / m["rej"], m["ship"] * 1e3, m["rej"] * 1e3)

def main():
    return [("item2 dijkstra delegation",) + item2(),
            ("item1 collapse rebuild",) + item1()]
"#;

fn main() {
    Python::initialize();
    Python::attach(|py| {
        py.run(cstring(&preload_source()).as_c_str(), None, None)
            .expect("bootstrap failed");
        let globals = PyDict::new(py);
        py.run(cstring(HARNESS).as_c_str(), Some(&globals), None)
            .expect("harness failed to define");

        let ext: String = globals.get_item("FNX_EXT").unwrap().unwrap().extract().unwrap();
        eprintln!("bench_elf_sha256 {}", self_identity());
        eprintln!("fnx_extension {ext}");
        eprintln!(
            "\n{:<26} {:>9} {:>10} {:>10} {:>11} {:>11}  {}",
            "lever", "ship/alt", "null ship", "null alt", "ship ms", "alt ms", "arms agree"
        );

        let rows = globals
            .get_item("main").unwrap().unwrap().call0().expect("harness main() raised");
        for row in rows.try_iter().unwrap() {
            let row = row.unwrap();
            let label: String = row.get_item(0).unwrap().extract().unwrap();
            let equal: bool = row.get_item(1).unwrap().extract().unwrap();
            let g = |i: usize| -> f64 { row.get_item(i).unwrap().extract().unwrap() };
            let (ratio, null_s, null_a, ship, alt) = (g(2), g(3), g(4), g(5), g(6));
            let band = 0.90..=1.10;
            let flag = match (band.contains(&null_s), band.contains(&null_a)) {
                (true, true) => "",
                (true, false) => "  <- ALT-ARM NULL OUT OF BAND, withheld",
                (false, true) => "  <- SHIP-ARM NULL OUT OF BAND, withheld",
                (false, false) => "  <- BOTH NULLS OUT OF BAND, withheld",
            };
            eprintln!(
                "{label:<26} {ratio:8.4}x {null_s:10.3} {null_a:10.3} {ship:11.4} {alt:11.4}  \
                 {equal}{flag}"
            );
        }
        eprintln!("\nratio > 1 means the REJECTED variant is faster (the lever would have won)");
    });
}
