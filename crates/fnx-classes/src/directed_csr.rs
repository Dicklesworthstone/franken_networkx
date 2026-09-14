//! Checked, immutable directed CSR storage shared by graph classes.

use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DirectedCsrError {
    NodeCountOverflow {
        node_count: usize,
    },
    OffsetCountMismatch {
        side: &'static str,
        expected: usize,
        actual: usize,
    },
    FirstOffsetNotZero {
        side: &'static str,
        actual: usize,
    },
    OffsetDecreased {
        side: &'static str,
        row: usize,
        previous: usize,
        next: usize,
    },
    TerminalOffsetMismatch {
        side: &'static str,
        terminal: usize,
        target_count: usize,
    },
    TargetOutOfBounds {
        side: &'static str,
        row: usize,
        target_position: usize,
        target: u32,
        node_count: usize,
    },
    NodeIndexOutOfBounds {
        index: usize,
        node_count: usize,
    },
}

impl fmt::Display for DirectedCsrError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NodeCountOverflow { node_count } => {
                write!(f, "CSR node count {node_count} exceeds u32 target capacity")
            }
            Self::OffsetCountMismatch {
                side,
                expected,
                actual,
            } => write!(
                f,
                "{side} CSR offsets have {actual} entries; expected {expected}"
            ),
            Self::FirstOffsetNotZero { side, actual } => {
                write!(f, "{side} CSR offsets start at {actual}, expected zero")
            }
            Self::OffsetDecreased {
                side,
                row,
                previous,
                next,
            } => write!(
                f,
                "{side} CSR offset decreased before row {row}: {previous} -> {next}"
            ),
            Self::TerminalOffsetMismatch {
                side,
                terminal,
                target_count,
            } => write!(
                f,
                "{side} CSR terminal offset {terminal} does not match {target_count} targets"
            ),
            Self::TargetOutOfBounds {
                side,
                row,
                target_position,
                target,
                node_count,
            } => write!(
                f,
                "{side} CSR row {row} target {target} at position {target_position} exceeds node count {node_count}"
            ),
            Self::NodeIndexOutOfBounds { index, node_count } => {
                write!(f, "CSR node index {index} exceeds node count {node_count}")
            }
        }
    }
}

impl std::error::Error for DirectedCsrError {}

/// Immutable bidirectional integer adjacency, associated with one graph revision.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DirectedCsr {
    pub revision: u64,
    pub node_count: usize,
    pub succ_offsets: Vec<usize>,
    pub succ_targets: Vec<u32>,
    pub pred_offsets: Vec<usize>,
    pub pred_targets: Vec<u32>,
}

impl DirectedCsr {
    pub fn try_new(
        revision: u64,
        node_count: usize,
        succ_offsets: Vec<usize>,
        succ_targets: Vec<u32>,
        pred_offsets: Vec<usize>,
        pred_targets: Vec<u32>,
    ) -> Result<Self, DirectedCsrError> {
        let view = Self {
            revision,
            node_count,
            succ_offsets,
            succ_targets,
            pred_offsets,
            pred_targets,
        };
        view.validate()?;
        Ok(view)
    }

    pub fn validate(&self) -> Result<(), DirectedCsrError> {
        if u32::try_from(self.node_count.saturating_sub(1)).is_err() {
            return Err(DirectedCsrError::NodeCountOverflow {
                node_count: self.node_count,
            });
        }
        validate_side(
            "successor",
            self.node_count,
            &self.succ_offsets,
            &self.succ_targets,
        )?;
        validate_side(
            "predecessor",
            self.node_count,
            &self.pred_offsets,
            &self.pred_targets,
        )
    }

    #[must_use]
    pub const fn revision(&self) -> u64 {
        self.revision
    }

    #[must_use]
    pub const fn node_count(&self) -> usize {
        self.node_count
    }

    #[must_use]
    pub fn successors(&self, idx: usize) -> &[u32] {
        self.row(idx, &self.succ_offsets, &self.succ_targets)
            .unwrap_or(&[])
    }

    #[must_use]
    pub fn predecessors(&self, idx: usize) -> &[u32] {
        self.row(idx, &self.pred_offsets, &self.pred_targets)
            .unwrap_or(&[])
    }

    pub fn checked_successors(&self, idx: usize) -> Result<&[u32], DirectedCsrError> {
        self.validate()?;
        self.row(idx, &self.succ_offsets, &self.succ_targets).ok_or(
            DirectedCsrError::NodeIndexOutOfBounds {
                index: idx,
                node_count: self.node_count,
            },
        )
    }

    pub fn checked_predecessors(&self, idx: usize) -> Result<&[u32], DirectedCsrError> {
        self.validate()?;
        self.row(idx, &self.pred_offsets, &self.pred_targets).ok_or(
            DirectedCsrError::NodeIndexOutOfBounds {
                index: idx,
                node_count: self.node_count,
            },
        )
    }

    pub fn visit_successors_until<F>(
        &self,
        idx: usize,
        mut visit: F,
    ) -> Result<bool, DirectedCsrError>
    where
        F: FnMut(u32) -> bool,
    {
        for &target in self.checked_successors(idx)? {
            if !visit(target) {
                return Ok(false);
            }
        }
        Ok(true)
    }

    pub fn visit_predecessors_until<F>(
        &self,
        idx: usize,
        mut visit: F,
    ) -> Result<bool, DirectedCsrError>
    where
        F: FnMut(u32) -> bool,
    {
        for &target in self.checked_predecessors(idx)? {
            if !visit(target) {
                return Ok(false);
            }
        }
        Ok(true)
    }

    fn row<'a>(&self, idx: usize, offsets: &[usize], targets: &'a [u32]) -> Option<&'a [u32]> {
        if idx >= self.node_count {
            return None;
        }
        let start = *offsets.get(idx)?;
        let end = *offsets.get(idx + 1)?;
        (start <= end && end <= targets.len()).then(|| &targets[start..end])
    }
}

pub type DiCsr = DirectedCsr;
pub type MultiDiCsr = DirectedCsr;

fn validate_side(
    side: &'static str,
    node_count: usize,
    offsets: &[usize],
    targets: &[u32],
) -> Result<(), DirectedCsrError> {
    let expected = node_count.saturating_add(1);
    if offsets.len() != expected {
        return Err(DirectedCsrError::OffsetCountMismatch {
            side,
            expected,
            actual: offsets.len(),
        });
    }
    if offsets.first().copied().unwrap_or(1) != 0 {
        return Err(DirectedCsrError::FirstOffsetNotZero {
            side,
            actual: offsets.first().copied().unwrap_or(usize::MAX),
        });
    }
    for (row, pair) in offsets.windows(2).enumerate() {
        if pair[1] < pair[0] {
            return Err(DirectedCsrError::OffsetDecreased {
                side,
                row,
                previous: pair[0],
                next: pair[1],
            });
        }
    }
    let terminal = offsets.last().copied().unwrap_or(0);
    if terminal != targets.len() {
        return Err(DirectedCsrError::TerminalOffsetMismatch {
            side,
            terminal,
            target_count: targets.len(),
        });
    }
    for (row, pair) in offsets.windows(2).enumerate() {
        for (relative, &target) in targets[pair[0]..pair[1]].iter().enumerate() {
            if usize::try_from(target).is_ok_and(|target| target >= node_count) {
                return Err(DirectedCsrError::TargetOutOfBounds {
                    side,
                    row,
                    target_position: pair[0] + relative,
                    target,
                    node_count,
                });
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid() -> DirectedCsr {
        DirectedCsr::try_new(
            7,
            3,
            vec![0, 2, 2, 3],
            vec![1, 2, 0],
            vec![0, 1, 2, 3],
            vec![2, 0, 0],
        )
        .expect("fixture is valid")
    }

    #[test]
    fn validates_bidirectional_rows_and_preserves_row_order() {
        let csr = valid();
        assert_eq!(csr.revision(), 7);
        assert_eq!(csr.node_count(), 3);
        assert_eq!(csr.successors(0), &[1, 2]);
        assert_eq!(csr.predecessors(2), &[0]);
        assert!(csr.validate().is_ok());
    }

    #[test]
    fn rejects_malformed_offsets_targets_and_overflow() {
        let err = DirectedCsr::try_new(0, 2, vec![0, 2], vec![1], vec![0, 0, 1], vec![0])
            .expect_err("offset count must be exact");
        assert!(matches!(err, DirectedCsrError::OffsetCountMismatch { .. }));
        let err = DirectedCsr::try_new(0, 2, vec![0, 2, 1], vec![1, 0], vec![0, 0, 0], vec![])
            .expect_err("row offsets must be monotonic");
        assert!(matches!(err, DirectedCsrError::OffsetDecreased { .. }));
        let err = DirectedCsr::try_new(0, 2, vec![1, 1, 1], vec![], vec![0, 0, 0], vec![])
            .expect_err("row offsets must start at zero");
        assert!(matches!(err, DirectedCsrError::FirstOffsetNotZero { .. }));
        let err = DirectedCsr::try_new(0, 2, vec![0, 0, 2], vec![1], vec![0, 0, 0], vec![])
            .expect_err("terminal offset must match targets");
        assert!(matches!(
            err,
            DirectedCsrError::TerminalOffsetMismatch { .. }
        ));
        let err = DirectedCsr::try_new(0, 2, vec![0, 1, 1], vec![2], vec![0, 0, 0], vec![])
            .expect_err("target must be in bounds");
        assert!(matches!(err, DirectedCsrError::TargetOutOfBounds { .. }));
        let err = DirectedCsr::try_new(0, usize::MAX, vec![], vec![], vec![], vec![])
            .expect_err("node count cannot fit u32 targets");
        assert!(matches!(err, DirectedCsrError::NodeCountOverflow { .. }));
        assert!(matches!(
            valid().checked_successors(3),
            Err(DirectedCsrError::NodeIndexOutOfBounds { .. })
        ));
    }

    #[test]
    fn cancellation_stops_a_row_without_losing_generation() {
        let csr = valid();
        let mut seen = Vec::new();
        let complete = csr
            .visit_successors_until(0, |target| {
                seen.push(target);
                false
            })
            .expect("row is valid");
        assert!(!complete);
        assert_eq!(seen, vec![1]);
        assert_eq!(csr.revision(), 7);
    }
}
