# frankentui Workflow Map + Event Contract (V1)

- generated_at_utc: `2026-02-15T20:26:00+00:00`
- baseline_comparator: `legacy_networkx/main@python3.12 + frankentui@main`
- surface_id: `frankentui-operator-surfaces-v1`

## Journeys

| Journey | Kind | Terminal State |
|---|---|---|
| `FTUI-JOURNEY-GOLDEN-001` | `golden` | `completed` |
| `FTUI-JOURNEY-FAIL-001` | `failure` | `failed_closed` |

## State Model

| State | Terminal |
|---|---|
| `idle` | no |
| `workflow_selected` | no |
| `executing_step` | no |
| `awaiting_confirmation` | no |
| `completed` | yes |
| `failed_closed` | yes |

## Event Contract

| Event ID | Name | From | To | Index |
|---|---|---|---|---|
| `FTUI-EVT-001` | `select_workflow` | `idle` | `workflow_selected` | 1 |
| `FTUI-EVT-002` | `begin_execution` | `workflow_selected` | `executing_step` | 2 |
| `FTUI-EVT-003` | `request_commit_confirmation` | `executing_step` | `awaiting_confirmation` | 3 |
| `FTUI-EVT-004` | `commit_step` | `awaiting_confirmation` | `executing_step` | 4 |
| `FTUI-EVT-005` | `finalize_workflow` | `executing_step` | `completed` | 5 |
| `FTUI-EVT-006` | `operator_abort` | `executing_step` | `failed_closed` | 6 |
| `FTUI-EVT-007` | `checksum_mismatch` | `awaiting_confirmation` | `failed_closed` | 7 |

## Accessibility Baselines

- deterministic keyboard tab order with required shortcuts (`Ctrl+N`, `Ctrl+Enter`, `Esc`)
- screen-reader labels and transition announcements are mandatory
- minimum contrast ratio set to WCAG AA (`4.5`)
- maximum primary actions per screen: `5`

## Gate Replay

- `FTUI-A-DIFF-001`: `rch exec -- env CARGO_TARGET_DIR=target-codex-mossy cargo test -p fnx-conformance --test ftui_workflow_event_contract_gate -- --nocapture`
