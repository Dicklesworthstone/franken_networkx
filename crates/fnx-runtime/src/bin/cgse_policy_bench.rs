#![forbid(unsafe_code)]

use fnx_runtime::{CgsePolicyEngine, CgsePolicyRule, CompatibilityMode};
use std::env;

fn parse_u64_flag(args: &[String], flag: &str, default: u64) -> u64 {
    let Some(pos) = args.iter().position(|value| value == flag) else {
        return default;
    };
    let Some(raw) = args.get(pos + 1) else {
        eprintln!("missing value for {flag}");
        std::process::exit(2);
    };
    raw.parse::<u64>().unwrap_or_else(|err| {
        eprintln!("invalid {flag}={raw}: {err}");
        std::process::exit(2);
    })
}

fn parse_mode(args: &[String]) -> CompatibilityMode {
    let Some(pos) = args.iter().position(|value| value == "--mode") else {
        return CompatibilityMode::Strict;
    };
    let Some(raw) = args.get(pos + 1) else {
        eprintln!("missing value for --mode (expected strict|hardened)");
        std::process::exit(2);
    };
    match raw.as_str() {
        "strict" => CompatibilityMode::Strict,
        "hardened" => CompatibilityMode::Hardened,
        other => {
            eprintln!("invalid --mode={other} (expected strict|hardened)");
            std::process::exit(2);
        }
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.iter().any(|value| value == "--help" || value == "-h") {
        println!(
            "cgse_policy_bench\n\n\
Usage:\n  cgse_policy_bench [--iterations N] [--mode strict|hardened]\n\n\
Defaults:\n  --iterations 2500000\n  --mode strict"
        );
        return;
    }

    let iterations = parse_u64_flag(&args, "--iterations", 2_500_000);
    let mode = parse_mode(&args);

    let engine = CgsePolicyEngine::new(mode);
    let rules = CgsePolicyRule::ALL;

    // Keep the loop hot and deterministic; we digest a tiny slice of the operation string
    // to prevent the optimizer from eliding work.
    let mut hash: u64 = 0xcbf29ce484222325_u64;
    let ts_unix_ms: u128 = 1_700_000_000_000_u128;

    for index in 0..iterations {
        let rule = rules[(index as usize) % rules.len()];
        let decision = engine.evaluate_at(rule, None, 0.2, false, ts_unix_ms);

        let op = std::hint::black_box(decision.decision.operation.as_bytes());
        hash ^= u64::from(op.first().copied().unwrap_or(0));
        hash = hash.wrapping_mul(0x0000_0100_0000_01B3_u64);
        hash ^= u64::from(op.last().copied().unwrap_or(0));
        hash = hash.wrapping_mul(0x0000_0100_0000_01B3_u64);
        hash ^= op.len() as u64;
        hash = hash.wrapping_mul(0x0000_0100_0000_01B3_u64);
    }

    println!("{hash:016x}");
}
