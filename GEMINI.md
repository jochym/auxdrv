# Development of INDI Driver for Celestron AUX Mount (Python)

## Current Project Status (v1.6.5)

The driver has achieved high functional parity with reference implementations and features a sophisticated "Digital Twin" simulator with 3D visualization and real-time schematic sky view. The tracking system has been optimized for sub-arcsecond stability.

### Implemented Milestones:
*   ✅ **AUX Core:** Complete support for the Celestron binary protocol (checksums, echo skipping).
*   ✅ **Connectivity:** Support for Serial (direct/HC) and TCP (simulator/WiFi).
*   ✅ **INDI API:** Full compatibility with `indipydriver 3.0.4` and standard property naming.
*   ✅ **Plug & Play:** Dynamic mount model and type detection (`MC_GET_MODEL`).
*   ✅ **Time/Site:** Support for reading/writing RTC and Location data to the hardware.
*   ✅ **Astronomy:** RA/Dec <-> Encoder transformations, 2nd order prediction, anti-backlash GoTo.
*   ✅ **Tracking:** High-inertia Dead Reckoning (dt=30s) with sub-step precision in rate estimation, achieving <1" stability in pure simulation.
*   ✅ **Alignment:** Advanced **6-Parameter Geometric solver** with **Adaptive Complexity** (SVD -> 4-param -> 6-param).
*   ✅ **Homing:** Support for automated homing and leveling.
*   ✅ **Peripherals:** Support for Focuser, GPS, and Power/Battery telemetry.
*   ✅ **Validation:** Real-world validation script (`scripts/real_world_validation.py`) verifying local alignment accuracy under mechanical errors.
*   ✅ **Simulator:** High-fidelity **NSE Simulator** with Textual TUI, 3D Web Console, and **Schematic Sky View**.
*   ✅ **Packaging:** PyPI-ready structure with `src` layout, `pyproject.toml`, and optional `[web]` extras.
*   ✅ **Testing:** 41+ automated tests covering all subsystems.

---

## Development Roadmap

### Phase 17: Hardware Validation & Advanced Features (Current/Next)
*   [ ] **Hardware Interaction Test (HIT)**: Physical verification of axis polarity and safety on real mounts.
*   [ ] **PEC (Periodic Error Correction)**: Recording, playback, and software correction of mechanical PE.
*   [ ] **Alignment Hibernation**: Persistent storage of sync points and alignment state to JSON/Persistent memory.
*   [ ] **Internal INDI Server**: Further refinement of the standalone `indipyserver` integration.

---

## Instructions for Developers

### Test Environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install indipydriver pyserial-asyncio ephem pyyaml
```

### Running Tests:
```bash
./venv/bin/python tests/test_functional.py
```
