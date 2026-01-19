# Project Status: INDI Celestron AUX Driver (Python)

**Current Version:** v1.6.5  
**Last Updated:** 2026-01-19  
**Status:** Feature Complete (Virtual) / Transitioning to Hardware Validation

---

## 🎯 Current Session Focus
Transition the project from **Virtual Validation** (Simulator-based) to **Physical Hardware Integration** and implement Phase 17 (Advanced Features).
- [ ] **Alignment Hibernation**: Implement persistent storage of sync points.
- [ ] **Software PEC**: Implement tracking rate corrections based on measured PE.

---

## 🚀 Achievements & Milestones
*   **Tracking Engine**: High-inertia dead reckoning ($dt=30s$) with sub-step floating-point precision. Achieved sub-arcsecond stability in simulation.
*   **Alignment System**: Adaptive mathematical model scaling from SVD Rotation (1-2 pts) to Full 6-parameter geometric correction (6+ pts).
*   **Digital Twin**: Integrated 3D Web Console (Three.js) for collision detection and visual motion verification.
*   **Quality Assurance**: 41 automated tests passing. CI/CD pipeline active on GitHub.
*   **Hardware Ready**: Dynamic mount detection (`MC_GET_MODEL`), RTC management, and battery telemetry implemented.

---

## 🗺 Detailed Roadmap (Functional Parity)

### 1. Driver Logic & Configuration
- [x] **Dynamic Mount Detection**: Automatically set mount type (Alt-Az/EQ) based on hardware response.
- [x] **Time Management (RTC)**: Write system time to mount RTC on connection.
- [x] **Site Management**: Read/Write Latitude/Longitude to hardware.

### 2. INDI Standard Compliance
- [x] **Properties Audit**: 1:1 parity with `indi_celestron_gps`.
- [x] **Standard Slew Rates**: Unified Guide/Centering/Find/Max mapping.

### 3. Auxiliary Functions & Peripherals
- [x] **Power Management**: Battery voltage and current telemetry (Evolution series).
- [x] **GPS & WiFi Status**: Extended status (satellites, signal strength).
- [ ] **Lighting & Outputs**: Backlight and 12V output control (Future Phase).

### 4. Phase 17: Hardware Phase & Advanced Features (Current)
- [ ] **HIT (Hardware Interaction Test)**: Physical verification of axis polarity.
- [ ] **PEC Measurement**: Record PE profile using `scripts/pec_measure.py`.
- [ ] **Alignment Hibernation**: Save/Load sync points to JSON.
- [ ] **Software PEC**: Apply measured profile to tracking rates.

---

## 🛠 Hardware Validation Protocol
Before first hardware slew:
1. **Safety Check**: Verify `TELESCOPE_ABORT_MOTION` stops both axes immediately.
2. **Axis Polarity**: Run `scripts/hit_validation.py` and confirm physical motion matches commands.
3. **Software Limits**: Ensure `TELESCOPE_LIMITS` are active and blocking slews below horizon/into pier.

---

## 📂 Key Resources
- `AGENTS.md`: Technical instructions for build, test, and code style.
- `docs/USER_MANUAL.md`: Installation and basic operation.
- `scripts/`: Hardware validation tools.
