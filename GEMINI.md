# Development of INDI Driver for Celestron AUX Mount (Python)

## Current Project Status (v1.0.0)

The project has achieved its core architectural goals, including high-fidelity mount simulation, advanced multi-point calibration, and non-sidereal tracking.

### Implemented Milestones:
*   ✅ **AUX Core:** Complete support for the Celestron binary protocol (checksums, echo skipping).
*   ✅ **Connectivity:** Support for Serial and TCP (simulator).
*   ✅ **INDI API:** Full compatibility with `indipydriver 3.0.4`.
*   ✅ **Astronomy:** RA/Dec <-> Encoder transformations, 2nd order prediction, anti-backlash GoTo.
*   ✅ **Alignment:** Advanced **6-Parameter Geometric solver** (Rotation, Cone Error, Non-Perpendicularity) with RMS reporting and spatial thinning.
*   ✅ **Refraction:** Switchable atmospheric refraction correction in the driver.
*   ✅ **Simulator:** High-fidelity **NSE Simulator** with Textual TUI, Stellarium support, and tunable mount imperfections.
*   ✅ **Testing:** 30+ automated tests covering all subsystems.
*   ✅ **Documentation:** Complete English documentation for driver, alignment, and test suites.

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
