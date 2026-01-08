# Driver Readiness for Hardware Testing

This document assesses the driver's stability and safety features before physical deployment on Celestron mount hardware.

## 1. Safety Audit

| Feature | Status | Implementation | Verification |
| :--- | :--- | :--- | :--- |
| **Slew Limits** | 🟢 Ready | Enforced in `goto_position` and background `hardware()` poll. | `tests/test_safety.py` (Verified blocking 60° slew with 45° limit). |
| **Abort Motion** | 🟢 Ready | `TELESCOPE_ABORT_MOTION` sends high-priority Rate 0 to both axes. | `scripts/hit_validation.py` (Emergency stop manual test). |
| **Cord Wrap** | 🟢 Ready | Sends `MC_ENABLE_CORDWRAP` and `MC_SET_CORDWRAP_POS` to the mount. | `tests/test_safety.py` (Verified MC polling response). |
| **Backlash Handling**| 🟢 Ready | Direction-aware GoTo approach implemented in the driver logic. | `tests/test_functional.py` (Verified 4-stage slew sequence). |

## 2. Communication Readiness

- **TCP/IP over WiFi**: Fully tested against the NSE Simulator. Uses standard port 2000. Recommended for Evolution and SkyPortal setups.
- **Serial over HC**: Supported via standard serial paths (e.g., `/dev/ttyUSB0`). Handles 9600 baud and protocol echo-skipping.

## 3. Recommended Testing Procedure

To ensure the safety of your equipment, follow the **Hardware Interaction Test (HIT)** routine exactly as described in `docs/HARDWARE_TESTING.md`.

### Critical Checklist before first hardware slew:
1.  [ ] **Balance**: Ensure the OTA is perfectly balanced.
2.  [ ] **Cables**: Verify 360-degree clearance for all cables.
3.  [ ] **Soft Limits**: Configure `TELESCOPE_LIMITS` in INDI to a safe range (e.g., 10° to 80° Altitude).
4.  [ ] **Emergency Abort**: Keep the computer keyboard within reach. Pressing **Space** in the HIT script or the Abort button in Ekos will stop all motion.

## 4. Known Differences from Official Driver

- **Alignment**: This driver uses a 6-parameter geometric model instead of the standard INDI alignment subsystem. It is more robust but may report different residual values than you are used to.
- **Slew Rates**: We use a unified 1-9 scale. Mapping to standard INDI rates (Guide, Centering, etc.) is handled via an overlay vector.

## 5. Conclusion: READY

The driver is considered **Ready for Hardware Testing**. All critical safety features are implemented and verified via automated regression tests.
