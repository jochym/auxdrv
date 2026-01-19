# Agent Guidelines: INDI Celestron AUX Driver

This repository contains a high-precision INDI driver for Celestron mounts using the AUX protocol, written in Python. It includes a physics-aware simulator and a digital twin visualization system.

## 🛠 Build, Lint, and Test Commands

### Environment Setup
The project uses `hatch` for building and `pytest` for testing.
```bash
# Install with all extras (recommended for development)
pip install -e ".[dev,simulator,web,docs]"
```

### Running Tests
All tests require `PYTHONPATH` to include the `src` directory.
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# Run all tests
pytest

# Run a specific test file
pytest tests/test_functional.py

# Run a specific test case
pytest tests/test_functional.py::TestFunctional::test_1_connection
```

### Linting and Type Checking
The project enforces strict type hinting.
```bash
# Run mypy on the core driver
mypy src/celestron_aux
```

### Documentation
Documentation is built using Sphinx and Furo.
```bash
cd docs
make html
```

---

## 📏 Code Style and Conventions

### Python Requirements
- **Version**: Python 3.11+
- **Type Hints**: Mandatory for all new code. Use `from __future__ import annotations`.

### Naming Conventions
- **Classes**: `CamelCase` (e.g., `CelestronAUXDriver`, `AUXCommunicator`).
- **Methods/Functions**: `snake_case` (e.g., `goto_position`, `pack_int3_steps`).
- **Variables/Constants**: `snake_case` for local variables, `UPPER_SNAKE_CASE` for global constants.
- **Private Members**: Use single underscore prefix `_private_method` for internal logic.

### Imports
Organize imports into three groups separated by a blank line:
1. Standard library imports.
2. Third-party library imports (`indipydriver`, `numpy`, `ephem`).
3. Local module imports (`from .alignment import ...`).

### Error Handling
- Use `asyncio` compatible error handling.
- Wrap hardware communication in `try...except` blocks.
- Log errors using `print` (for simulator TUI) or INDI `LightVector` states.

### Documentation Style
- **Docstrings**: Use **Google Style** docstrings.
- **Complexity**: Prefer clear, readable logic over clever one-liners, especially in mathematical transformations.

---

## 🏗 Architecture and Core Concepts

### 1. The src Layout
All core logic resides in `src/celestron_aux/`. 
- `celestron_indi_driver.py`: The INDI interface and property management.
- `celestron_aux_driver.py`: The low-level AUX protocol and serial/TCP communication.
- `alignment.py`: Mathematical model for coordinate transformations (SVD-based).

### 2. Dead Reckoning Tracking
The driver uses a high-inertia tracking model with a **30-second window** for velocity differentiation. This ensures stability and prevents jitter from encoder quantization.

### 3. Adaptive Alignment
The `AlignmentModel` scales automatically:
- 1-2 points: SVD Rotation only.
- 3-5 points: 4-parameter model.
- 6+ points: Full 6-parameter geometric model (Cone Error, NP, etc.).

### 4. Configuration
**NEVER** hardcode hardware parameters (encoder counts, gear ratios). Use `src/celestron_aux/config.yaml`.

---

## ⚠️ Safety Protocols
Before testing on real hardware:
1. Ensure `scripts/hit_validation.py` passes.
2. Verify `TELESCOPE_ABORT_MOTION` (Emergency Stop) is responsive.
3. Check `TELESCOPE_LIMITS` are enforced in the driver.

---
*Last Updated: 2026-01-19*
