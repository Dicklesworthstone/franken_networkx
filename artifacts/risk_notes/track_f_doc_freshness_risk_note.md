# Risk Note — Track F: Long-Tail Polish, NX Residue, and Documentation Freshness

## Risk Surface
- parser/ingestion: documentation can overstate parser/native coverage and hide delegated behavior behind compatibility-friendly language
- algorithmic denial vectors: low direct exposure, but stale parity claims can cause users to trust unsupported or under-tested algorithm paths
- **public-surface count drift**: hand-maintained export totals and coverage percentages decay quickly as `__all__` and backend dispatch change
- **backend residue drift**: lingering `_to_nx` or delegated routes can silently expand the gap between native and advertised behavior

## Failure Modes
- fail-closed triggers: docs freshness or coverage-matrix checks fail when README / FEATURE_PARITY / CHANGELOG / generated coverage artifacts drift from HEAD
- degraded-mode triggers: public docs remain technically true but materially misleading because delegation gaps are described too optimistically

## Mitigations
- controls: generated `docs/coverage.md` from `franken_networkx.__all__`; explicit delegated/native accounting; freshness gates for public docs; backend coverage measurement work before making parity claims
- tests: `python3 scripts/generate_coverage_matrix.py --check`; `python3 scripts/verify_docs.py`; targeted parity tests for APIs that recently moved from delegated to native

## Residual Risk
- unresolved risks: machine-checked export counts do not prove behavioral parity, only surface accounting
- follow-up actions: keep family-level docs qualitative unless backed by generated evidence, and treat every newly native backend route as requiring explicit parity coverage before marketing it
