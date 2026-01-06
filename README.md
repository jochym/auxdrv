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

Installation of dependencies:
```bash
pip install indipydriver pyserial-asyncio ephem pyyaml textual rich
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

## Alignment System

The driver supports 3-point star alignment. To perform calibration:
1.  Set `Coord Set Mode` to **SYNC**.
2.  Select a star in your planetarium and issue a **Sync** command.
3.  Repeat for 2-3 stars in different parts of the sky. The driver will automatically calculate a transformation matrix to improve GoTo accuracy.

## Configuration

Observer location and ports are defined in the `config.yaml` file. Default coordinates are set for **Beblo, Poland**.
