# Development of INDI Driver for Celestron AUX Mount (Python)

## Current Project Status (v1.1.0)

The project has achieved its core architectural goals and features a robust hardware validation suite.

### Implemented Milestones:
*   ✅ **AUX Core:** Complete support for the Celestron binary protocol (checksums, echo skipping).
*   ✅ **Connectivity:** Support for Serial and TCP (simulator).
*   ✅ **INDI API:** Full compatibility with `indipydriver 3.0.4`.
*   ✅ **Astronomy:** RA/Dec <-> Encoder transformations, 2nd order prediction, anti-backlash GoTo.
*   ✅ **Alignment:** Advanced **6-Parameter Geometric solver** with **Residual-Aware Grid Thinning**.
*   ✅ **Refraction:** Switchable atmospheric refraction correction in the driver.
*   ✅ **Validation:** Dedicated hardware (HIT) and photography (PPT) testing routines.
*   ✅ **Simulator:** High-fidelity **NSE Simulator** with Textual TUI and tunable mount imperfections.
*   ✅ **Testing:** 30+ automated tests covering all subsystems.
*   ✅ **Documentation:** Complete English documentation for driver, alignment, and validation.

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
