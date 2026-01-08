# Development of INDI Driver for Celestron AUX Mount (Python)

## Current Project Status (v1.4.0)

The driver has achieved high functional parity with reference implementations and is structured as a professional, redistributable Python package.

### Implemented Milestones:
*   ✅ **AUX Core:** Complete support for the Celestron binary protocol (checksums, echo skipping).
*   ✅ **Connectivity:** Support for Serial (direct/HC) and TCP (simulator/WiFi).
*   ✅ **INDI API:** Full compatibility with `indipydriver 3.0.4` and standard property naming.
*   ✅ **Plug & Play:** Dynamic mount model and type detection (`MC_GET_MODEL`).
*   ✅ **Time/Site:** Support for reading/writing RTC and Location data to the hardware.
*   ✅ **Astronomy:** RA/Dec <-> Encoder transformations, 2nd order prediction, anti-backlash GoTo.
*   ✅ **Alignment:** Advanced **6-Parameter Geometric solver** with **Residual-Aware Grid Thinning**.
*   ✅ **Homing:** Support for automated homing and leveling.
*   ✅ **Peripherals:** Support for Focuser, GPS, and Power/Battery telemetry.
*   ✅ **Validation:** Dedicated hardware (HIT) and photography (PPT) testing routines.
*   ✅ **Simulator:** High-fidelity **NSE Simulator** with Textual TUI and tunable mount imperfections.
*   ✅ **Packaging:** PyPI-ready structure with `src` layout and `pyproject.toml`.
*   ✅ **Testing:** 37+ automated tests covering all subsystems.

---

## Development Roadmap

### Phase 16: Web Console & 3D Visualization (In Progress)
*   Implementation of an optional digital twin for the simulator.
*   3D visualization of mount movement using Three.js.
*   Configurable mount geometry for collision detection.

### Phase 17: Advanced Features (Planned)
*   Periodic Error Correction (PEC).
*   Hibernation mode.
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
