# Testing Strategy

This document describes the test suite for the Celestron AUX driver and procedures for moving from simulation to real hardware.

## Test Categories

### Tier 1: Virtual (Simulator Only)
These tests verify mathematical logic and protocol compliance.
*   `tests/test_alignment_*.py`: SVD transformation and geometric model validation.
*   `tests/integration/test_full_stack.py`: TCP layer and INDI session verification.

### Tier 2: Hardware-Ready
These tests can be safely run on a physical mount.
*   `tests/test_functional.py`: Basic GoTo commands, Parking, and Homing.
*   `tests/test_tracking_accuracy.py`: Long-term tracking drift analysis.
*   `tests/test_moving_objects.py`: Moon, planet, and satellite tracking.

### Tier 3: Critical (Manual Supervision Required)
Tests checking physical limits and emergency scenarios.
*   `tests/test_safety.py`: Alt/Az limits and Cord Wrap.
*   `scripts/hit_validation.py`: Interactive axis and abort test.

## Safety Protocol

When working with real hardware:
1.  **No Blind Restarts**: The physical mount preserves its state. Tests must not assume a "zero" starting point.
2.  **Two-Stage GoTo**: The driver uses a FAST + SLOW (anti-backlash) sequence. Do not bypass this for precision.
3.  **Emergency Stop**: Always have the **Space** key or INDI Abort button ready.
4.  **Power Stability**: High-rate slews (Rate 9) require stable power supply.

## Continuous Integration
The project uses GitHub Actions to run the full test suite and type checking (`mypy`) on Python 3.11, 3.12, and 3.13.
