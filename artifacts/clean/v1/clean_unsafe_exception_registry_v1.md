# Clean Unsafe Policy + Exception Registry

- artifact id: `clean-unsafe-exception-registry-v1`
- generated at (utc): `2026-02-15T05:21:46Z`

## Policy Defaults
- workspace default: #![forbid(unsafe_code)] required in every workspace crate root
- lint gate: `cargo clippy --workspace --all-targets -- -D warnings`
- ci enforcement: deny release if forbid-missing or unresolved unsafe findings are present
- unknown unsafe behavior: `fail_closed`

## Coverage Snapshot
- workspace crates: ['crates/fnx-classes', 'crates/fnx-views', 'crates/fnx-dispatch', 'crates/fnx-convert', 'crates/fnx-algorithms', 'crates/fnx-generators', 'crates/fnx-readwrite', 'crates/fnx-durability', 'crates/fnx-conformance', 'crates/fnx-runtime']
- forbid missing: []
- unsafe findings count: 0

## Fail-Closed Controls
- `UFC-1` trigger=`unsafe_findings.count > approved_exceptions.count` action=deny release and require explicit exception registration
- `UFC-2` trigger=`forbid_unsafe_missing.count >= 1` action=deny release and require crate-level policy restoration
- `UFC-3` trigger=`approved exception expires_at_utc < now` action=deny release until renewal or revocation

## Runtime Contract
- states: ['clean', 'exception_pending', 'exception_approved', 'blocked']
- actions: ['scan', 'approve_exception', 'revoke_exception', 'block_release']
- loss model: undocumented unsafe usage > expired exception usage > delayed release
- safe mode fallback: block release whenever scanner findings exceed approved exception budget
- safe mode budget: {'max_unmapped_unsafe_findings': 0, 'max_expired_approved_exceptions': 0, 'max_missing_forbid_crates': 0}
- trigger thresholds:
  - `TRIG-UNMAPPED-UNSAFE` condition=unsafe_findings.count > approved_exceptions.count threshold=1 fallback=enter blocked state and reject release
  - `TRIG-MISSING-FORBID` condition=forbid_unsafe_missing.count >= 1 threshold=1 fallback=enter blocked state and require policy repair
  - `TRIG-EXPIRED-EXCEPTION` condition=approved exception expires_at_utc < now threshold=1 fallback=revoke exception and block release until renewed
