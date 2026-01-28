# INDI Celestron AUX Driver (Python)

[![CI Status](https://github.com/jochym/auxdrv/actions/workflows/ci.yml/badge.svg)](https://github.com/jochym/auxdrv/actions/workflows/ci.yml)
![Version](https://img.shields.io/badge/version-1.7.6-blue)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen)](https://jochym.github.io/auxdrv/)

A high-precision INDI driver for Celestron mounts using the native AUX protocol.

## Key Features
- **Async Architecture**: Fully non-blocking driver based on `asyncio`.
- **Advanced Alignment**: SVD-based multi-point calibration with 6-parameter geometric error compensation.
- **High-Precision Tracking**: Sub-arcsecond stability via high-inertia differentiation.
- **Digital Twin**: 3D visualization and physics-aware simulation (`caux-sim`).
- **Full Accessory Support**: GPS, RTC, Focuser, and Power telemetry.

## Quick Start
```bash
pip install .
# Start simulator
caux-sim --text
# Start driver
python src/celestron_aux/celestron_indi_driver.py
```

For detailed instructions, see the [Getting Started](docs/getting_started.md) guide and the [Full Documentation](https://jochym.github.io/auxdrv/).

## License
GPL-3.0-or-later
