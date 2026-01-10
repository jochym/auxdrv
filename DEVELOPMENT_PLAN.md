# Development Plan for INDI Celestron AUX (Functional Parity)

## Goal
Achieve full functional interchangeability with the original `indi_celestron_gps` driver. Focus on solid base logic, standard compliance, and hardware peripheral support.

## 1. Driver Logic and Configuration (Highest Priority)
The goal is for the driver to be "Plug & Play" and autonomously recognize what it is connected to.

- [x] **Dynamic Model and Mount Type Detection**
    - Completely eliminate dependency on the device name in XML (e.g., remove rigid "CGX" -> EQ mapping).
    - Implement logic to query motor controllers (`MC_GET_MODEL`) during connection.
    - Automatically set `m_MountType` (Alt-Az / EQ-GEM / EQ-Fork) based on hardware response.
- [x] **Time Management (RTC)**
    - Implement active time setting in the mount (write to RTC) instead of relying solely on passive GPS emulation.
    - Verify time correctness upon connection (synchronize with INDI server system time).

## 2. INDI Standard Compliance (High Priority)
The client user (e.g., Ekos, SkyCharts) should not perceive any difference between this driver and the official one.

- [x] **Properties Audit**
    - 1:1 comparison of the property tree with `indi_celestron_gps`.
    - Unify naming of Switches and Numbers.
    - Standardize `TELESCOPE_SLEW_RATE` handling (rate names: Guide, Centering, Find, Max).
- [x] **Site Management**
    - Full support for location management (read/write from/to mount).

## 3. Auxiliary Functions and Peripherals (New Features)
Support for AUX modules supported by the protocol but often overlooked.

- [x] **Power Management**
    - Read supply voltage (`BAT` / `MB` module).
    - Charging status (for mounts with built-in battery, e.g., Evolution).
    - Low battery warning.
- [ ] **Lighting and Outputs (Lighting/Aux)**
    - Backlight control (if mount/accessories possess it, e.g., LED rings).
    - 12V output control (if available on the specific model via AUX).
- [x] **GPS and WiFi (Status)**
    - Extended GPS module status (fix, satellite count) – beyond simple emulation.
    - WiFi signal status (RSSI) for connection diagnostics.

## 4. Advanced Functions (Low Priority)
Features used less frequently or specific to high-level Deep Sky astrophotography.

- [ ] **PEC (Periodic Error Correction)**
    - Add PPEC commands to `auxproto.h`.
    - Implement recording, playback, and enabling correction.
- [ ] **Hibernacja (Hibernate)**
    - Implement hibernation mode (saving alignment state to persistent mount memory and safe shutdown).

## 5. Packaging and Distribution (Planned Release)
The driver will be packaged for PyPI to allow easy installation via standard tools.

- [x] **Refactor to `src` layout**
- [x] **Prepare `pyproject.toml`**
- [x] **Standalone executable entry points**

## 6. High-Fidelity Simulation & Digital Twin (Phase 16)
Enable visual validation of mount behavior and safety logic.

- [x] **Web-based 3D Console**
    - [x] Create an optional web server using FastAPI/WebSockets.
    - [x] Develop a 3D visualization using Three.js (simplified Evolution 8 model).
    - [x] Implement collision visualization (detect camera hitting the base).
    - [x] Support configurable mount dimensions in `config.yaml`.
- [x] **Optional Packaging**
    - [x] Define `[simulator]` and `[web]` extras in `pyproject.toml`.
    - [x] Ensure conditional imports for heavy dependencies (Textual, FastAPI).

## 7. Tracking and Alignment Optimization (v1.6.x)
High-precision motion control.

- [x] **6-Parameter Geometric Model**
    - Support for ID, CH, and NP corrections.
- [x] **High-Inertia Dead Reckoning**
    - Sub-step rate estimation with $dt=30s$.
- [x] **Automated Real-World Validation**
    - Script for measuring pointing and tracking accuracy under mechanical stress.
- [x] **PEC Measurement Suite**
    - Standalone script `scripts/pec_measure.py` using ASTAP for sensor-based PE analysis.

