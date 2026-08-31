//! Constructor-from-iterator head-to-head across all four classes.
//!
//! br-r37-c1-q86hv records the worst ratios in this repo's live ledger — `MultiGraph(iter(keyed))`
//! at 0.312x, `DiGraph(iter(attr_edges))` at 0.349x, eight rows between 0.31x and 0.79x — measured
//! 2026-07-10 on HEAD 7208ffd57 and marked "lever prepared; blocked on a remote build". Two things
//! make it worth re-measuring rather than trusting:
//!
//!   * it is seven weeks old, and six ready beads checked this session had already been fixed or
//!     superseded without being closed;
//!   * its own GUARD row is the tell. `Graph(iter(edges))` reads 0.982x because the ctorgen lever
//!     LANDED on `Graph` and deliberately left the other three classes open, while
//!     `DiGraph(list)` / `MultiGraph(list)` / `MultiDiGraph(list)` read 1.126-1.170x. So the claim
//!     is specifically that the deficit is the ITERATOR path on the three non-Graph classes, and
//!     both controls have to be carried in the same invocation or the claim is not being tested.
//!
//! Shapes: a materialised LIST is the guard (expected >= 1.0), a generator is the subject. The two
//! differ only in whether the constructor can size its input up front.
//!
//! Protocol: arms interleaved ABBA inside one loop, median, DUAL A/A nulls — a separately built fnx
//! fixture against the fnx arm and a separately built networkx fixture against the networkx arm. A
//! row is WITHHELD unless both land in band.
//!
//! CONSTRUCTION IS A MUTATION WORKLOAD and mutation arms are non-stationary — the allocator is in a
//! different state on every repeat — so some nulls here are expected to stray. That is what the gate
//! is for; strayed rows are withheld rather than published.
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
# br-r37-c1-jc9e4: the LAST candidate is a trap. The first two are cdylibs this cargo
# invocation built; the third is a checked-in artifact left by whatever peer last ran
# `maturin develop`, and on a shared checkout it is rebuilt underneath a running
# measurement (observed: sha 8ff908fc -> 486a2fb4 in nine minutes). Falling through to
# it means the run measured SOMEBODY ELSE'S BUILD while printing a respectable sha.
# Provenance is now a printed field so a row pasted from this output carries it.
_candidates = [
    os.path.join(target_dir, 'release', 'lib_fnx.so'),
    os.path.join(target_dir, 'release', 'libfnx_python.so'),
    os.path.join(cwd, 'python', 'franken_networkx', '_fnx.abi3.so'),
]
for _p in _candidates[:2]:
    if os.path.exists(_p):
        sys._fnx_ext_provenance = 'built-by-this-invocation'
        break
else:
    sys._fnx_ext_provenance = 'STALE-TREE-FALLBACK (not built by this invocation)'
for path in _candidates:
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
        print(f'fnx extension provenance: {{sys._fnx_ext_provenance}}', file=sys.stderr)
        break
"
    )
}

const HARNESS: &str = r#"
import gc as _gc
import random, statistics, time
import networkx as nx
import franken_networkx as fnx

import sys as _sys
NX_BUILD = f"{nx.__version__} @ {nx.__file__}"
FNX_EXT = getattr(_sys, "_fnx_ext", "unavailable")

N, M = 2000, 10000

def edge_lists_pair():
    """Build BOTH payloads INTERLEAVED, element by element.

    The previous run built them one after another and lost 11 of 20 rows to A/A null failures,
    nine of them on the networkx arm. Construction is a mutation workload - the allocator sits
    in a different state on every repeat - so two sequentially built payloads are not
    interchangeable fixtures. Interleaving spreads that drift across both instead of
    concentrating it in whichever was built second."""
    rng = random.Random(11)
    a = {"plain": [], "attr": [], "keyed": []}
    b = {"plain": [], "attr": [], "keyed": []}
    for _ in range(M):
        u, v = rng.randrange(N), rng.randrange(N)
        for d in (a, b):
            d["plain"].append((u, v))
            d["attr"].append((u, v, {"weight": 1.0}))
            d["keyed"].append((u, v, 0, {"weight": 1.0}))
    return a, b

def payload(lists, shape, cls):
    if shape == "keyed":
        return lists["keyed"]
    return lists["attr"] if shape == "attr" else lists["plain"]

def run_cell(cls, shape, feed, rounds=21, inner=1):
    # More, SHORTER slots: the tjp0g ledger row records that long slots on a loaded host drift
    # within the square and that shortening them is what made its nulls resolvable.
    a, b = edge_lists_pair()
    fa, na = payload(a, shape, cls), payload(a, shape, cls)
    fb, nb = payload(b, shape, cls), payload(b, shape, cls)
    F, X = getattr(fnx, cls), getattr(nx, cls)
    # `feed` is what the ledger row varies: a materialised list (the constructor can size it)
    # against a generator (it cannot). Building `iter(list)` is O(1) and charged to both arms.
    wrap = (lambda s: iter(s)) if feed == "iter" else (lambda s: s)
    arms = {"fnx": lambda: F(wrap(fa)), "nx": lambda: X(wrap(na)),
            "null_f": lambda: F(wrap(fb)), "null_n": lambda: X(wrap(nb))}
    ok = F(wrap(fa)).number_of_edges() == X(wrap(na)).number_of_edges()
    for fn in arms.values():
        fn()
    # Disable the cyclic collector for the timed region, identically for every arm: a
    # collection landing inside one arm's slot is pure common-mode noise on a workload that
    # allocates this hard. Not gc.collect() between rounds - that is its own confound.
    _gc_was = _gc.isenabled()
    _gc.disable()
    samples = {k: [] for k in arms}
    for r in range(rounds):
        order = list(arms) if r % 2 == 0 else list(arms)[::-1]
        for name in order:
            fn = arms[name]
            t = time.perf_counter()
            for _ in range(inner):
                fn()
            samples[name].append((time.perf_counter() - t) / inner)
    if _gc_was:
        _gc.enable()
    m = {k: statistics.median(v) for k, v in samples.items()}
    return (ok, m["nx"] / m["fnx"], m["null_f"] / m["fnx"], m["null_n"] / m["nx"],
            m["fnx"] * 1e3, m["nx"] * 1e3)

def main():
    """TWO INDEPENDENT PASSES over a NARROWED cell set.

    The previous run withheld every Graph row and three of four DiGraph rows - exactly the
    cells carrying the claim - while the multi classes went 8/8. Narrowing to the simple
    classes cuts total wall time roughly fourfold, so there is less room for the host to drift
    across the square, and raising rounds tightens each median.

    Two passes because REPLICATION is the discriminator a passing A/A null cannot substitute
    for: a null certifies stationarity WITHIN a pass and says nothing about common-mode drift
    BETWEEN them. Agreement across passes is what makes a number citable; disagreement is
    reported as disagreement rather than averaged away."""
    rows = []
    for attempt in (1, 2):
        for cls in ("Graph", "DiGraph"):
            for shape in ("plain", "attr"):
                for feed in ("iter", "list"):
                    rows.append((f"pass{attempt}", cls, shape, feed)
                                + run_cell(cls, shape, feed, rounds=41))
    return rows
"#;

fn main() {
    Python::initialize();
    Python::attach(|py| {
        py.run(cstring(&preload_source()).as_c_str(), None, None)
            .expect("bootstrap failed");
        let globals = PyDict::new(py);
        py.run(cstring(HARNESS).as_c_str(), Some(&globals), None)
            .expect("harness failed to define");

        let fetch =
            |n: &str| -> String { globals.get_item(n).unwrap().unwrap().extract().unwrap() };
        eprintln!("bench_elf_sha256 {}", self_identity());
        eprintln!("fnx_extension {}", fetch("FNX_EXT"));
        eprintln!("incumbent {}", fetch("NX_BUILD"));
        eprintln!(
            "\n{:<6} {:<9} {:<6} {:<5} {:>9} {:>9} {:>9} {:>10} {:>10}  {}",
            "pass",
            "class",
            "shape",
            "feed",
            "nx/fnx",
            "null fnx",
            "null nx",
            "fnx ms",
            "nx ms",
            "ok"
        );

        let rows = globals
            .get_item("main")
            .unwrap()
            .unwrap()
            .call0()
            .expect("harness main() raised");
        for row in rows.try_iter().unwrap() {
            let row = row.unwrap();
            let s = |i: usize| -> String { row.get_item(i).unwrap().extract().unwrap() };
            let f = |i: usize| -> f64 { row.get_item(i).unwrap().extract().unwrap() };
            let ok: bool = row.get_item(4).unwrap().extract().unwrap();
            let (pass, cls, shape, feed) = (s(0), s(1), s(2), s(3));
            let (ratio, null_f, null_n, fms, nms) = (f(5), f(6), f(7), f(8), f(9));
            let band = 0.90..=1.10;
            let flag = match (band.contains(&null_f), band.contains(&null_n)) {
                (true, true) => "",
                (true, false) => "  <- NX-ARM NULL OUT OF BAND, withheld",
                (false, true) => "  <- FNX-ARM NULL OUT OF BAND, withheld",
                (false, false) => "  <- BOTH NULLS OUT OF BAND, withheld",
            };
            eprintln!(
                "{pass:<6} {cls:<9} {shape:<6} {feed:<5} {ratio:8.3}x {null_f:9.3} {null_n:9.3} \
                 {fms:10.3} {nms:10.3}  {ok}{flag}"
            );
        }
    });
}
