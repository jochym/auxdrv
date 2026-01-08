# Celestron AUX INDI Driver (Python)

A modern INDI driver for Celestron mounts using the AUX protocol, with a built-in simulator for testing.

## Project Architecture

*   `celestron_indi_driver.py`: Main INDI driver integrating with the `indipydriver` library.
*   `celestron_aux_driver.py`: Library handling the Celestron AUX binary communication protocol.
*   `simulator/`: Sophisticated NexStar telescope simulator, allowing driver testing without physical hardware.

## Requirements

*   Python 3.8+
*   `indipydriver >= 3.0.0`
*   `pyserial-asyncio`
*   `ephem`
*   `pyyaml`
*   `textual`
*   `rich`
*   `numpy`
*   `scipy`

Installation of dependencies:
```bash
pip install indipydriver pyserial-asyncio ephem pyyaml textual rich numpy scipy
```

## Running

1.  **Starting the simulator:**
    *   Graphical mode (Textual TUI): `python simulator/nse_simulator.py`
    *   Headless mode (background): `python simulator/nse_simulator.py -t`
2.  **Starting the INDI driver:**
    ```bash
    python celestron_indi_driver.py
    ```

To connect to the simulator, use the port: `socket://localhost:2000`.

## Stellarium Integration

The simulator provides a server compatible with the Stellarium protocol on port `10001`. To verify operation:

1.  Start the simulator: `python simulator/nse_simulator.py`
2.  In Stellarium, go to: **Configuration (F2) -> Plugins -> Telescope Control -> Configure**.
3.  Add a new telescope:
    *   Controlled by: **External software or another computer**.
    *   Name: **NSE Simulator**.
    *   Host: **localhost**, Port: **10001**.
4.  Connect to the telescope. You will see the telescope reticle on the sky map.

## Documentation

- [User Manual](docs/USER_MANUAL.md) - Installation and basic operation.
- [Alignment System](docs/ALIGNMENT_SYSTEM.md) - Technical guide to the multi-point SVD alignment.
- [Simulator Guide](simulator/README.md) - How to use the built-in telescope simulator.

## Features
- **Singular Value Decomposition (SVD) Alignment**: Robust multi-point calibration with RMS error reporting.
- **Predictive Tracking**: 2nd-order prediction for smooth tracking of stars, planets, and satellites.
- **Full AUX Support**: Native binary protocol for high performance and compatibility.
- **Safety**: Built-in slew limits and cord-wrap prevention.
- **Interactive Simulator**: Modern TUI for offline development and testing.

## Configuration

The driver, simulator, and validation scripts are all configured via **`config.yaml`**. This file is organized into clean sections:
- `observer`: Location and elevation.
- `driver`: Serial port and baud rate for the mount.
- `simulator`: Ports and mechanical imperfections for simulation.
- `validation_hit`: Parameters for hardware interaction testing.
- `validation_ppt`: Parameters for pointing accuracy testing.

Some parameters can also be overridden via environment variables (e.g., `PORT`, `BAUD`) or CLI arguments.
