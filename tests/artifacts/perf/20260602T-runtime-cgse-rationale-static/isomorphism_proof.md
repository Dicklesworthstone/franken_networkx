# CGSE Rationale Static Template Proof

Bead: `br-r37-c1-04z53.9`

## Profile Target

- Baseline artifact: `baseline_strict_hyperfine.json`
- Hotspot: `rationale_format` accounted for 473.950125 ms of 716.093281 ms in the prior 2.5M strict CGSE profile.
- Lever: replace repeated dynamic formatting for the common `0.2000` selected-policy rationale with static rule/action templates.

## Benchmark

- Before: 858.1 ms mean, 856.1 ms median, 15 runs.
- After: 381.1 ms mean, 378.5 ms median, 15 runs.
- After confirmations: 378.2 ms mean over 10 runs; 372.5 ms mean over 15 runs.
- Speedup: 2.25x by mean.
- Score: impact 4 x confidence 5 / effort 2 = 10.0.
- Note: `rch exec` only offloads compilation commands in this environment. The hyperfine command was invoked through `rch exec`, but `rch` classified it as non-compilation and ran it locally; compile/test/check/clippy gates below were crate-scoped and `rch`-wrapped, with some runs remote and the final full test falling open locally when workers were saturated.

## Isomorphism

- Ordering preserved: yes. The rule/action selection path is unchanged; only rationale string construction changes after the action has already been selected.
- Tie-breaking unchanged: yes. No comparator, iteration, rule precedence, allowlist, or ambiguity precedence logic changed.
- Floating-point unchanged: yes. The existing clamp and NaN paths are unchanged; the static path is selected only when `clamped_probability.to_bits() == 0.2_f64.to_bits()`.
- RNG unchanged: yes. The CGSE policy engine remains deterministic and does not use RNG.
- Golden outputs unchanged: `sha256sum -c golden_sha256.txt` passes for baseline output, after output, and the full rationale matrix.

## Verification

- `rch exec -- cargo test -p fnx-runtime cgse_policy_engine_rationale_matrix_matches_legacy_text -- --nocapture`
- `rch exec -- cargo test -p fnx-runtime`
- `rch exec -- cargo check -p fnx-runtime --all-targets`
- `rch exec -- cargo clippy -p fnx-runtime --all-targets -- -D warnings`
- `rch exec -- cargo fmt -p fnx-runtime --check`
- `sha256sum -c golden_sha256.txt`
