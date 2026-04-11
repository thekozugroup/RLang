use crate::ast::phases::{Phase, Trace};
use crate::errors::ValidationError;

const MAX_REBLOOM: usize = 3;

pub fn validate_phases(trace: &Trace) -> Result<(), Vec<ValidationError>> {
    let mut errors = Vec::new();

    let phases: Vec<Phase> = trace.phases.iter().map(|b| b.phase).collect();

    // Must contain all four phases
    let has_frame = phases.contains(&Phase::Frame);
    let has_explore = phases.contains(&Phase::Explore);
    let has_verify = phases.contains(&Phase::Verify);
    let has_decide = phases.contains(&Phase::Decide);

    if !has_frame {
        errors.push(ValidationError::Phase {
            message: "trace missing required Frame phase".to_string(),
        });
    }
    if !has_explore {
        errors.push(ValidationError::Phase {
            message: "trace missing required Explore phase".to_string(),
        });
    }
    if !has_verify {
        errors.push(ValidationError::Phase {
            message: "trace missing required Verify phase".to_string(),
        });
    }
    if !has_decide {
        errors.push(ValidationError::Phase {
            message: "trace missing required Decide phase".to_string(),
        });
    }

    // Frame must appear exactly once
    let frame_count = phases.iter().filter(|&&p| p == Phase::Frame).count();
    if frame_count > 1 {
        errors.push(ValidationError::Phase {
            message: format!("Frame phase must appear exactly once, found {}", frame_count),
        });
    }

    // Decide must appear exactly once
    let decide_count = phases.iter().filter(|&&p| p == Phase::Decide).count();
    if decide_count > 1 {
        errors.push(ValidationError::Phase {
            message: format!("Decide phase must appear exactly once, found {}", decide_count),
        });
    }

    // Validate transitions
    let mut rebloom_count = 0;
    for window in phases.windows(2) {
        let (from, to) = (window[0], window[1]);
        let valid = match (from, to) {
            (Phase::Frame, Phase::Explore) => true,
            (Phase::Explore, Phase::Verify) => true,
            (Phase::Verify, Phase::Decide) => true,
            // Rebloom: Verify -> Explore is allowed (bounded)
            (Phase::Verify, Phase::Explore) => {
                rebloom_count += 1;
                if rebloom_count > MAX_REBLOOM {
                    errors.push(ValidationError::Phase {
                        message: format!(
                            "exceeded maximum rebloom count of {} (Verify -> Explore)",
                            MAX_REBLOOM
                        ),
                    });
                    false
                } else {
                    true
                }
            }
            _ => false,
        };

        if !valid && !matches!((from, to), (Phase::Verify, Phase::Explore)) {
            errors.push(ValidationError::Phase {
                message: format!("invalid phase transition: {:?} -> {:?}", from, to),
            });
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}
