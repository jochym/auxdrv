# Installation and Setup

This guide covers setting up the environment and running the INDI Celestron AUX Driver.

## Requirements

*   Python 3.11+
*   `indipydriver >= 3.0.4`
*   `pyserial-asyncio`
*   `ephem`
*   `numpy`
*   `scipy`
*   `caux-sim` (Standalone simulator package)

## Environment Setup

The project uses `hatch` for building, but local development is typically done in a virtual environment.

```bash
# Setup environment
python -m venv venv
source venv/bin/activate
pip install -e ".[dev,docs]"
```

## Configuration

The system uses a hierarchical TOML configuration:

1.  **`config.default.toml`**: Built-in defaults (always loaded).
2.  **`config.toml`**: User overrides (if present).
3.  **CLI Arguments**: Specific overrides for scripts.

The configuration file is organized into clean sections:
- `observer`: Location and elevation.
- `driver`: Serial port and baud rate for the mount.
- `simulator`: Ports and mechanical imperfections for simulation.
- `validation_hit`: Parameters for hardware interaction testing.
- `validation_ppt`: Parameters for pointing accuracy testing.
- `validation_pec`: Parameters for periodic error measurement.

## First Run (Simulator)

Before connecting to real hardware, it is recommended to test the setup using the `caux-sim` simulator.

1.  **Starting the simulator:**
    ```bash
    caux-sim --text --perfect
    ```
2.  **Starting the INDI driver:**
    ```bash
    python src/celestron_aux/celestron_indi_driver.py
    ```

To connect to the simulator from an INDI client, use the port: `socket://localhost:2000`.
