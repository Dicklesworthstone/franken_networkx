#![forbid(unsafe_code)]

use fnx_runtime::{
    CgsePolicyEngine, CgsePolicyRule, CompatibilityMode, EffectTrace, EffectTraceSummary,
    ParserEffect, ParserEffectKind,
};
use std::env;
use std::hint::black_box;
use std::time::Instant;

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
  cgse_policy_bench --effect-trace-summary-ab [--effects N] [--iterations N]\n\n\
Defaults:\n  --iterations 2500000\n  --mode strict"
        );
        return;
    }

    if args
        .iter()
        .any(|value| value == "--effect-trace-summary-ab")
    {
        let effects = parse_u64_flag(&args, "--effects", 65_536) as usize;
        let iterations = parse_u64_flag(&args, "--iterations", 4) as usize;
        run_effect_trace_summary_ab(effects, iterations);
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

fn effect_trace_summary_frozen(trace: &EffectTrace) -> EffectTraceSummary {
    let mut by_kind = std::collections::HashMap::new();
    for effect in trace.effects() {
        *by_kind.entry(effect.kind).or_insert(0) += 1;
    }

    EffectTraceSummary {
        total_effects: trace.len(),
        warnings: trace.count_kind(ParserEffectKind::Warning),
        failures: trace.count_kind(ParserEffectKind::FailClosed),
        coercions: trace.count_kind(ParserEffectKind::Coercion),
        is_terminated: trace.is_terminated(),
        max_risk: trace
            .effects()
            .iter()
            .map(|effect| effect.risk_probability)
            .fold(0.0_f64, f64::max),
    }
}

fn assert_summary_exact(candidate: &EffectTraceSummary, baseline: &EffectTraceSummary) {
    assert_eq!(candidate.total_effects, baseline.total_effects);
    assert_eq!(candidate.warnings, baseline.warnings);
    assert_eq!(candidate.failures, baseline.failures);
    assert_eq!(candidate.coercions, baseline.coercions);
    assert_eq!(candidate.is_terminated, baseline.is_terminated);
    assert_eq!(candidate.max_risk.to_bits(), baseline.max_risk.to_bits());
}

fn run_effect_trace_summary_ab(effect_count: usize, iterations: usize) {
    assert!(effect_count > 0, "--effects must be positive");
    assert!(iterations > 0, "--iterations must be positive");

    let kinds = [
        ParserEffectKind::Warning,
        ParserEffectKind::Validation,
        ParserEffectKind::FailClosed,
        ParserEffectKind::Allow,
        ParserEffectKind::Fallback,
        ParserEffectKind::Sanitize,
        ParserEffectKind::Coercion,
    ];
    let mut trace = EffectTrace::new();
    for index in 0..effect_count {
        let risk = (index % 1_001) as f64 / 1_000.0;
        trace.record(ParserEffect::new(
            kinds[index % kinds.len()],
            "parse-operation",
            "stable-effect-message",
            CompatibilityMode::Strict,
            risk,
        ));
    }

    let baseline = effect_trace_summary_frozen(&trace);
    let candidate = trace.summary();
    assert_summary_exact(&candidate, &baseline);

    let time = |candidate: bool| -> f64 {
        let started = Instant::now();
        for _ in 0..iterations {
            let summary = if candidate {
                trace.summary()
            } else {
                effect_trace_summary_frozen(&trace)
            };
            black_box(summary);
        }
        started.elapsed().as_nanos() as f64 / iterations as f64
    };

    for _ in 0..3 {
        black_box(time(false));
        black_box(time(true));
    }

    const ROUNDS: usize = 15;
    let paired = |null_control: bool| -> (Vec<f64>, Vec<f64>, Vec<f64>) {
        let mut ratios = Vec::with_capacity(ROUNDS);
        let mut baseline_times = Vec::with_capacity(ROUNDS);
        let mut candidate_times = Vec::with_capacity(ROUNDS);
        for round in 0..ROUNDS {
            let baseline_arm = null_control;
            let (baseline_time, candidate_time) = if round.is_multiple_of(2) {
                (time(baseline_arm), time(true))
            } else {
                let candidate_time = time(true);
                (time(baseline_arm), candidate_time)
            };
            ratios.push(baseline_time / candidate_time);
            baseline_times.push(baseline_time);
            candidate_times.push(candidate_time);
        }
        (ratios, baseline_times, candidate_times)
    };
    let median = |values: &[f64]| {
        let mut sorted = values.to_vec();
        sorted.sort_by(f64::total_cmp);
        sorted[sorted.len() / 2]
    };
    let report = |label: &str, ratios: &[f64], baseline_times: &[f64], candidate_times: &[f64]| {
        let wins = ratios.iter().filter(|&&ratio| ratio > 1.0).count();
        let mut sorted = ratios.to_vec();
        sorted.sort_by(f64::total_cmp);
        println!(
            "EFFECT_TRACE_SUMMARY_AB {label}: median={:.4}x win_rate={wins}/{ROUNDS} \
             p5_p95=[{:.4},{:.4}] baseline_median_ns={:.0} candidate_median_ns={:.0}",
            median(ratios),
            sorted[ROUNDS * 5 / 100],
            sorted[ROUNDS * 95 / 100],
            median(baseline_times),
            median(candidate_times),
        );
    };

    let (ratios, baseline_times, candidate_times) = paired(false);
    report("FROZEN_vs_LIVE", &ratios, &baseline_times, &candidate_times);
    let (null_ratios, null_first, null_second) = paired(true);
    report("NULL_live_vs_live", &null_ratios, &null_first, &null_second);
    println!(
        "EFFECT_TRACE_SUMMARY_AB effects={effect_count} iterations={iterations} rounds={ROUNDS} exact_parity=true"
    );
}
