# Development of INDI Driver for Celestron AUX Mount (Python)

## Current Project Status (v1.5.1)

The driver has achieved high functional parity with reference implementations and features a high-fidelity "Digital Twin" simulator with 3D visualization.

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
*   ✅ **Simulator:** High-fidelity **NSE Simulator** with Textual TUI, tunable imperfections, and **3D Web Console**.
*   ✅ **Packaging:** PyPI-ready structure with `src` layout, `pyproject.toml`, and optional `[web]` extras.
*   ✅ **Testing:** 37+ automated tests covering all subsystems.

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
