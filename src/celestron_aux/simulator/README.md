# Celestron AUX Mount Simulator

This is a high-fidelity simulator for telescope mounts using the Celestron AUX binary protocol. It is designed for testing INDI drivers and planetarium software without requiring physical hardware.

## Features

- **Protocol Support**: Full implementation of the Celestron AUX binary protocol.
- **Modern TUI**: Interactive Text User Interface built with `Textual`.
- **Physical Model**: Realistic simulation of motor encoders, slew speeds, and acceleration.
- **Networking**:
  - **Command Port**: TCP port 2000 (standard for Celestron WiFi/Ethernet).
  - **Discovery**: UDP port 55555 for auto-discovery by apps like SkyPortal.
  - **Stellarium**: TCP port 10001 for direct connection using Stellarium's telescope protocol.
- **Safety**: Supports slew limits and cord-wrap simulation.

## Architecture

The simulator consists of two main components:
1.  **NSE Telescope (`nse_telescope.py`)**: The core physics engine. It manages encoder steps, slewing state, and calculates coordinates.
2.  **NSE Simulator (`nse_simulator.py`)**: The TUI and networking layer. It handles multiple concurrent TCP/UDP connections and translates protocol commands into telescope actions.

## Realistic Speed Profile

The simulator is calibrated to match the **Celestron NexStar Evolution** mount:
- **Maximum Slew Rate**: 4.0 degrees per second (Rate 9).
- **Precision Approach Rate**: 1.0 degree per second (Rate 7).
- **Acceleration**: Simulated inertia for realistic movement starts and stops.

*Source: [Official Celestron Evolution Specifications](https://www.celestron.com/products/nexstar-evolution-8-telescope)*

## Usage

### Interactive TUI Mode
```bash
python simulator/nse_simulator.py
```

### Headless Mode (for automated testing)
```bash
python simulator/nse_simulator.py -t
```

### Options
- `-p, --port`: Command TCP port (default: 2000).
- `-t, --text`: Run in headless mode (no TUI).
