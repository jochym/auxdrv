# Celestron AUX INDI Driver (Python)

[![CI](https://github.com/jochym/auxdrv/actions/workflows/ci.yml/badge.svg)](https://github.com/jochym/auxdrv/actions/workflows/ci.yml)
![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![License](https://img.shields.io/badge/license-GPL--3.0--or--later-green)
![INDI](https://img.shields.io/badge/INDI-compatible-orange)
![Version](https://img.shields.io/badge/version-1.7.5-blue)
[![Documentation](https://img.shields.io/badge/docs-User%20Manual-brightgreen)](docs/USER_MANUAL.md)

A modern INDI driver for Celestron mounts using the AUX protocol, validated against the hardware-grade `caux-sim` simulator.

## Project Architecture

*   `celestron_indi_driver.py`: Main INDI driver integrating with the `indipydriver` library.
*   `celestron_aux_driver.py`: Library handling the Celestron AUX binary communication protocol.
*   **Simulator**: The project utilizes the standalone `caux-sim` command for high-fidelity hardware emulation.

## Requirements

*   Python 3.11+
*   `indipydriver >= 3.0.4`
*   `pyserial-asyncio`
*   `ephem`
*   `numpy`
*   `scipy`
*   `caux-sim` (Standalone simulator package)

## Running

1.  **Starting the simulator:**
    ```bash
    caux-sim --text --perfect
    ```
2.  **Starting the INDI driver:**
    ```bash
    python src/celestron_aux/celestron_indi_driver.py
    ```

To connect to the simulator, use the port: `socket://localhost:2000`.

## Features
- **Non-Blocking Execution**: Background tasking for slewing and tracking ensures the driver remains responsive.
- **Singular Value Decomposition (SVD) Alignment**: Robust multi-point calibration with RMS error reporting.
- **Predictive Tracking**: 2nd-order prediction for smooth tracking of stars, planets, and satellites.
- **Full AUX Support**: Native binary protocol for high performance and compatibility.
- **Safety**: Built-in slew limits and cord-wrap prevention.

## Configuration

The driver, simulator, and validation scripts are all configured via **`config.toml`**. This file is organized into clean sections:
- `observer`: Location and elevation.
- `driver`: Serial port and baud rate for the mount.
- `simulator`: Ports and mechanical imperfections for simulation.
- `validation_hit`: Parameters for hardware interaction testing.
- `validation_ppt`: Parameters for pointing accuracy testing.
- `validation_pec`: Parameters for periodic error measurement.

The system uses a hierarchical configuration:
1.  **`config.default.toml`**: Built-in defaults (always loaded).
2.  **`config.toml`**: User overrides (if present).
3.  **CLI Arguments**: Specific overrides for scripts.
