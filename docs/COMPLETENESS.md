# Celestron AUX Driver: Feature Completeness & Parity Checklist

This document tracks the functional parity between this Python implementation and the reference C++ `indi-celestronaux` driver.

## 1. Communication Modes

| Mode | Importance | Python Status | C++ Parity | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Serial (Direct AUX)** | High | ✅ Done | Yes | 19200 baud, requires AUX-Serial adapter. |
| **Serial (via HC)** | **Crucial** | ✅ Done | Yes | 9600 baud, connected to Hand Controller USB/Serial port. |
| **TCP/IP (WiFi/Ethernet)** | **Crucial** | ✅ Done | Yes | Port 2000, supports Evolution/SkyPortal WiFi. |
| **Echo-Skipping** | High | ✅ Done | Yes | Required for single-wire AUX bus hardware. |

## 2. Mount Functions

| Feature | Python Status | C++ Parity | Notes |
| :--- | :--- | :--- | :--- |
| **Manual Slew** | ✅ Done | Yes | 9-speed N/S/E/W slewing. |
| **Fast GoTo** | ✅ Done | Yes | High-speed positioning. |
| **Slow Approach** | ✅ Done | Yes | Precision final centering. |
| **Anti-backlash** | ✅ Done | Yes | Direction-aware approach. |
| **Abort Motion** | ✅ Done | Yes | Immediate stop. |
| **Sidereal Tracking** | ✅ Done | Yes | 2nd-order predictive tracking. |
| **Custom Track Rates** | ⏳ Planned | Yes | Setting specific arcsec/sec rates. |
| **Homing / Leveling** | ✅ Done | Yes | Startup sequences. |
| **Hibernation** | ⏳ Planned | Yes | Save/Restore alignment state. |

## 3. Alignment & Calibration

| Feature | Python Status | C++ Parity | Notes |
| :--- | :--- | :--- | :--- |
| **Sync (1-star)** | ✅ Done | Yes | Local coordinate offset. |
| **Multi-Point SVD** | ✅ Done | Yes | Mathematical rotation fitting. |
| **6-Param Geometric** | ✅ Done | **Improved** | Compensates for Cone and Non-Perpendicularity. |
| **Point Thinning** | ✅ Done | **New** | Residual-aware grid thinning (15° sectors). |
| **Refraction** | ✅ Done | Yes | Atmospheric correction. |

## 4. Peripheral Support (AUX Bus)

| Device | Python Status | C++ Parity | Notes |
| :--- | :--- | :--- | :--- |
| **Focuser** | ✅ Done | Yes | Position and GoTo support. |
| **GPS** | ✅ Done | Yes | Location and Time sync. |
| **RTC (Clock)** | ✅ Done | Yes | Reading/Writing mount time. |
| **Power/Battery** | ✅ Done | **New** | Voltage and Current telemetry. |
| **WiFi Status** | ⏳ Planned | No | RSSI reporting. |

## 5. Simulator Status

The NSE Simulator is a high-fidelity tool for driver development.

| Feature | Status | Notes |
| :--- | :--- | :--- |
| **AUX Protocol** | ✅ Done | Binary packet handling, checksums, echo. |
| **Physics Engine** | ✅ Done | Encoders, slew rates, acceleration. |
| **TUI Interface** | ✅ Done | Interactive Modern TUI (Textual). |
| **Stellarium Proto** | ✅ Done | Allows visual verification in planetarium. |
| **Imperfections** | ✅ Done | Backlash, PE, Cone Error, Jitter simulation. |
| **Discovery** | ✅ Done | UDP 55555 discovery support. |

## 6. Packaging & Distribution

| Feature | Status | Notes |
| :--- | :--- | :--- |
| **`src` Layout** | ✅ Done | Adheres to modern Python standards. |
| **`pyproject.toml`** | ✅ Done | Build metadata and dependency management. |
| **Entry Points** | ✅ Done | `indi-celestron-aux` and `celestron-aux-simulator` tools. |
| **PyPI Readiness** | ✅ Done | Structured for future release. |
