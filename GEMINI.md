# Development of INDI Driver for Celestron AUX Mount (Python)

## Current Project Status (v1.6.4)

The driver has achieved high functional parity with reference implementations and features a sophisticated "Digital Twin" simulator with 3D visualization and real-time schematic sky view. The tracking system has been optimized for sub-arcsecond stability.

### Implemented Milestones:
*   ✅ **AUX Core:** Complete support for the Celestron binary protocol (checksums, echo skipping).
*   ✅ **Connectivity:** Support for Serial (direct/HC) and TCP (simulator/WiFi).
*   ✅ **INDI API:** Full compatibility with `indipydriver 3.0.4` and standard property naming.
*   ✅ **Plug & Play:** Dynamic mount model and type detection (`MC_GET_MODEL`).
*   ✅ **Time/Site:** Support for reading/writing RTC and Location data to the hardware.
*   ✅ **Astronomy:** RA/Dec <-> Encoder transformations, 2nd order prediction, anti-backlash GoTo.
*   ✅ **Tracking:** High-inertia Dead Reckoning (dt=30s) with sub-step precision in rate estimation, achieving <1" stability.
*   ✅ **Alignment:** Advanced **6-Parameter Geometric solver** with **Residual-Aware Grid Thinning**.
*   ✅ **Homing:** Support for automated homing and leveling.
*   ✅ **Peripherals:** Support for Focuser, GPS, and Power/Battery telemetry.
*   ✅ **Validation:** Real-world validation script (`scripts/real_world_validation.py`) verifying local alignment accuracy under mechanical errors.
*   ✅ **Simulator:** High-fidelity **NSE Simulator** with Textual TUI, 3D Web Console, and **Schematic Sky View**.
*   ✅ **Packaging:** PyPI-ready structure with `src` layout, `pyproject.toml`, and optional `[web]` extras.
*   ✅ **Testing:** 38+ automated tests covering all subsystems.

---

## Development Roadmap

### Phase 17: Advanced Features (Planned)
*   Periodic Error Correction (PEC).
*   Hibernation mode.
*   Internal INDI Server refinement.

*   ✅ **Packaging:** PyPI-ready structure with `src` layout and `pyproject.toml`.

---

## Development Roadmap

### Phase 12: Periodic Error Correction (Planned)
*   Implementation of software and hardware-interfaced PEC.
*   Persistent storage of calibration data.

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
