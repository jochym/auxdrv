# INDI Celestron AUX Driver (Python)

[![CI Status](https://github.com/jochym/auxdrv/actions/workflows/ci.yml/badge.svg)](https://github.com/jochym/auxdrv/actions/workflows/ci.yml)
![Version](https://img.shields.io/badge/version-1.7.6-blue)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen)](https://jochym.github.io/auxdrv/)

**WARNING: This is an experimental, vibe-coded driver for research and development purposes. It has not been fully verified on physical hardware.**

An experimental Python INDI driver for Celestron mounts using the AUX protocol. It serves as a platform for testing improvements and new algorithms for potential porting back to the reference C++ driver.

## Project Goals
- **Algorithm Prototyping**: Test new alignment and tracking models in Python.
- **Async Exploration**: Evaluate `asyncio` for low-level protocol handling.
- **Simulator-First Development**: Primary validation against the `caux-sim` physics-aware simulator.

## Quick Start
```bash
pip install .
# Start simulator
caux-sim --text
# Start driver
python src/celestron_aux/celestron_indi_driver.py
```

See the [Getting Started](docs/getting_started.md) guide and the [Full Documentation](https://jochym.github.io/auxdrv/) for more details.

## License
GPL-3.0-or-later
