# Development of INDI Driver for Celestron AUX Mount (Python)

## Current Project Status (v0.5.0)

The project has realized the technical and mathematical foundations needed for telescope control, including an alignment system and a modern testing interface.

### Implemented Milestones:
*   ✅ **AUX Core:** Complete support for the Celestron binary protocol (checksums, echo skipping).
*   ✅ **Connectivity:** Support for Serial and TCP (simulator).
*   ✅ **INDI API:** Full compatibility with `indipydriver 3.0.4`.
*   ✅ **Astronomy:** RA/Dec <-> Encoder transformations, 2nd order prediction, anti-backlash GoTo.
*   ✅ **Alignment:** 3-point matrix transformation model (alignment error correction).
*   ✅ **Simulator:** Modern **Textual TUI** interface, Stellarium protocol support.
*   ✅ **Testing:** Functional and mathematical test suite.
*   ✅ **Documentation:** Full Docstrings support (Google Style).

---

## Development Roadmap

### Phase 6: Safety and Accessories (IN PROGRESS)
*   **Slew Limits:** Implementation of software altitude and azimuth limits.
*   **Cord Wrap Prevention:** Protecting cables from twisting.
*   **Focuser Support:** Support for focuser modules via the AUX bus.
*   **GPS Support:** Integration with the built-in GPS module.

### Phase 7: Moving Objects Support (Planned)
*   Extension of the tracking loop to support non-sidereal objects (Satellites, Comets).
*   Integration with TLE data.

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
