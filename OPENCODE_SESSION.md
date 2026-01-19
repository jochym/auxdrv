# OpenCode Session Status - INDI Celestron AUX

**Date:** 2026-01-13
**Agent:** OpenCode (Software Engineering Specialist)
**Session ID:** current-production-v1.6.5

## 🎯 Current Goal
Transition the project from **Virtual Validation** (Simulator-based) to **Physical Hardware Integration** and implement Phase 17 (Advanced Features).

## ✅ Completed in this Session
1.  **Project State Audit:** Verified that all 41 functional and safety tests are passing in the `venv` environment.
2.  **Documentation Sync:** Updated `CHANGELOG.md` and `GEMINI.md` to reflect the current stable version (v1.6.5).
3.  **Handoff Preparation:** Created `STATUS.md` with technical details for the next developer/agent.
4.  **Math Verification:** Confirmed that the MathJax/LaTeX rendering for Sphinx documentation is fixed.
5.  **Environment Check:** Validated `PYTHONPATH` and `venv` requirements for running the driver and simulator.

## 📋 Pending Tasks (Next Session)
1.  **Hardware Interaction Test (HIT):** Execute `scripts/hit_validation.py` on a physical mount (Evolution/NexStar/CGX).
2.  **PEC Measurement:** Use `scripts/pec_measure.py` with ASTAP to record the mount's periodic error profile.
3.  **Phase 17 Implementation:**
    *   Add `Alignment Hibernation` to save/load sync points to `alignment_state.json`.
    *   Add `Software PEC` logic to the tracking loop in `celestron_indi_driver.py`.

## ⚙️ Environment Details
- **Root Directory:** `/home/jochym/Projects/indi/auxdrv`
- **Python:** 3.13 (in `venv`)
- **Main Dependencies:** `indipydriver`, `indipyserver`, `numpy`, `scipy`, `ephem`.
- **PYTHONPATH:** Must include `$(pwd)/src`.

## 🧠 Critical Context for the Next Agent
- **No Code Touch Policy:** Hardware-specific settings (encoder counts, gear ratios, offsets) MUST stay in `config.yaml`. Do not hardcode them in `alignment.py` or `celestron_aux_driver.py`.
- **Tracking Window:** We are using a 30-second window for velocity differentiation to ensure high-inertia stability.
- **Safety First:** Always run `scripts/hit_validation.py` before any long GoTo on real hardware.
