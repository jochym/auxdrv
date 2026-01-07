# Development of INDI Driver for Celestron AUX Mount (Python)

## Current Project Status (v0.7.0)

The project has realized the technical and mathematical foundations needed for telescope control, including an alignment system, safety features, accessory support, and non-sidereal tracking.

### Implemented Milestones:
*   ✅ **AUX Core:** Complete support for the Celestron binary protocol (checksums, echo skipping).
*   ✅ **Connectivity:** Support for Serial and TCP (simulator).
*   ✅ **INDI API:** Full compatibility with `indipydriver 3.0.4`.
*   ✅ **Astronomy:** RA/Dec <-> Encoder transformations, 2nd order prediction, anti-backlash GoTo.
*   ✅ **Alignment:** Advanced **Multi-Point SVD solver** with RMS reporting and local weighting.
*   ✅ **Simulator:** Modern **Textual TUI** interface, Stellarium protocol support.
*   ✅ **Safety & Accessories:** Slew limits, Cord Wrap prevention, Focuser and GPS support.
*   ✅ **Moving Objects:** Support for Sun, Moon, Planets, and Satellites (TLE).
*   ✅ **Testing:** Comprehensive functional, safety, and mathematical test suite (23 tests passing).
*   ✅ **Documentation:** Complete English documentation for driver, alignment system, and simulator.

---

## Development Roadmap

### Phase 9: Advanced Calibration & PEC (Planned)
*   Periodic Error Correction (PEC) support.
*   Cone error and non-perpendicularity compensation.

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
