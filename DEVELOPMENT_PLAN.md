# Development Plan for INDI Celestron AUX (Functional Parity)

## Goal
Achieve full functional interchangeability with the original `indi_celestron_gps` driver. Focus on solid base logic, standard compliance, and hardware peripheral support.

## 1. Driver Logic and Configuration (Highest Priority)
The goal is for the driver to be "Plug & Play" and autonomously recognize what it is connected to.

- [ ] **Dynamic Model and Mount Type Detection**
    - Completely eliminate dependency on the device name in XML (e.g., remove rigid "CGX" -> EQ mapping).
    - Implement logic to query motor controllers (`MC_GET_MODEL`) during connection.
    - Automatically set `m_MountType` (Alt-Az / EQ-GEM / EQ-Fork) based on hardware response.
- [ ] **Time Management (RTC)**
    - Implement active time setting in the mount (write to RTC) instead of relying solely on passive GPS emulation.
    - Verify time correctness upon connection (synchronize with INDI server system time).

## 2. INDI Standard Compliance (High Priority)
The client user (e.g., Ekos, SkyCharts) should not perceive any difference between this driver and the official one.

- [ ] **Properties Audit**
    - 1:1 comparison of the property tree with `indi_celestron_gps`.
    - Unify naming of Switches and Numbers.
    - Standardize `TELESCOPE_SLEW_RATE` handling (rate names: Guide, Centering, Find, Max).
- [ ] **Site Management**
    - Full support for location management (read/write from/to mount).

## 3. Auxiliary Functions and Peripherals (New Features)
Support for AUX modules supported by the protocol but often overlooked.

- [ ] **Power Management**
    - Read supply voltage (`BAT` / `MB` module).
    - Charging status (for mounts with built-in battery, e.g., Evolution).
    - Low battery warning.
- [ ] **Lighting and Outputs (Lighting/Aux)**
    - Backlight control (if mount/accessories possess it, e.g., LED rings).
    - 12V output control (if available on the specific model via AUX).
- [ ] **GPS and WiFi (Status)**
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

- [ ] **Web-based 3D Console**
    - [ ] Create an optional web server using FastAPI/WebSockets.
    - [ ] Develop a 3D visualization using Three.js (simplified Evolution 8 model).
    - [ ] Implement collision visualization (detect camera hitting the base).
    - [ ] Support configurable mount dimensions in `config.yaml`.
- [ ] **Optional Packaging**
    - [ ] Define `[simulator]` and `[web]` extras in `pyproject.toml`.
    - [ ] Ensure conditional imports for heavy dependencies (Textual, FastAPI).
