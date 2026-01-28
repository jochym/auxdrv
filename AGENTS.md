# Agent Guidelines: INDI Celestron AUX Driver

This repository contains a high-precision INDI driver for Celestron mounts using the AUX protocol, written in Python. It includes a physics-aware simulator and a digital twin visualization system.

## 🛠 Build, Lint, and Test Commands

### Environment Setup
The project uses `hatch` for building, but local development is typically done in the provided `venv`.
```bash
# Setup environment
python -m venv venv
source venv/bin/activate
pip install -e ".[dev,docs]"
```

### Running Tests
All tests require `PYTHONPATH` to include the `src` directory.
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# Run all standard tests (unit and integration)
pytest

# Run only integration tests (full stack: client <-> driver <-> caux-sim)
pytest tests/integration/test_full_stack.py

# Run experimental tests (might require manual synchronization)
pytest tests/experimental/test_experimental_mismatches.py
```

### Linting and Type Checking
Strict type hinting is mandatory. We use `mypy` for static analysis.
```bash
# Run mypy on core modules
mypy src/celestron_aux
```

### Documentation
Built using Sphinx with Furo theme and MathJax for LaTeX equations.
```bash
cd docs
make html
```

---

## 📏 Code Style and Conventions

### Python Requirements
- **Version**: Python 3.11+
- **Type Hints**: Mandatory for all signatures. Use `from __future__ import annotations` to support PEP 563.
- **Asyncio**: The driver is fully asynchronous. Avoid blocking calls (`time.sleep`) in the main loop. Use `await asyncio.sleep()`.

### Naming Conventions
- **Classes**: `CamelCase` (e.g., `CelestronAUXDriver`, `AUXCommunicator`).
- **Methods/Functions**: `snake_case` (e.g., `goto_position`, `pack_int3_steps`).
- **Variables**: `snake_case` for local variables.
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `STEPS_PER_REVOLUTION`).
- **INDI Properties**: Follow INDI convention (e.g., `CONNECTION`, `EQUATORIAL_EOD_COORD`). Member names should be concise.

### Imports
Organize into three distinct blocks:
1. Standard library (e.g., `asyncio`, `struct`).
2. Third-party (e.g., `indipydriver`, `numpy`, `ephem`).
3. Local project modules (e.g., `from .alignment import ...`).

### Error Handling
- **Hardware Layer**: Wrap AUX commands in `try...except` blocks. Use `AUXCommunicator.lock` to ensure atomic bus access.
- **INDI Layer**: Use `LightVector` states (Ok, Busy, Alert) to communicate hardware status to the client.
- **Logging**: Use `print` only in simulator TUI context. In the driver, favor INDI-native logging or structured logs.

---

## 🏗 Architecture and Core Concepts

### 1. The Core Driver (`src/celestron_aux/`)
- `celestron_indi_driver.py`: Manages the INDI state machine and property mapping.
- `celestron_aux_driver.py`: Implements the binary packet protocol, checksums, and low-level I/O.
- `alignment.py`: Implements the SVD-based transformation matrix.

### 2. High-Inertia Tracking
We use a **30-second window** for velocity differentiation. This is critical for Celestron mounts because:
- Encoder quantization is significant.
- Low-frequency mechanical jitter can cause "shaking" if the differentiation window is too small.
- The model maintains a 2nd-order prediction of target RA/Dec to ensure smooth motion.

### 3. Adaptive Alignment Model
The `AlignmentModel` automatically upgrades its complexity based on the number of stars:
- **1-2 Stars**: Simple SVD Rotation (fixed axes).
- **3-5 Stars**: 4-parameter model (Rotation + Zero Point Offsets).
- **6+ Stars**: Full 6-parameter geometric model, compensating for:
  - **Cone Error ($CH$):** Non-perpendicularity between OTA and Dec axis.
  - **NP ($NP$):** Non-perpendicularity between Azm/Alt (or RA/Dec) axes.
  - **Altitude Index ($ID$):** Zero-point offset in the Altitude axis.

---

## 🖥 The Simulator & Digital Twin

### Running the Simulator
The project uses the standalone `caux-sim` simulator (closer to real hardware).
```bash
# Start simulator in headless mode
caux-sim --text --perfect
```
Options:
- `--text`: Headless mode (no TUI).
- `--debug`: Enable verbose packet logging to `stderr`.
- `--perfect`: Disable mechanical imperfections for clean testing.
- `--web`: Enable the 3D Web Console.

### Digital Twin
The 3D view is served via FastAPI. Access it at `http://localhost:8000` when the simulator is running with `--web`. It visualizes:
- Real-time mount position.
- Horizon limits and safety "keep-out" zones.
- Nearby bright stars (via `ephem`).

---

## 🏗 Integration Testing
Integration tests use `caux-sim` automatically via the `simulator_process` fixture in `tests/integration/conftest.py`.
```bash
pytest tests/integration/test_full_stack.py
```

---

## ⚠️ Safety and Validation Protocols

### Pre-Hardware Check
Before deploying changes to a physical mount:
1. **HIT Validation**: Run `scripts/hit_validation.py`. This script performs a "Hardware Interaction Test" (pulsing axes, checking abort response).
2. **Limit Verification**: Ensure `TELESCOPE_LIMITS` correctly blocks slews into the pier or ground.
3. **Dead-Man's Switch**: Verify that `TELESCOPE_ABORT_MOTION` sends `MC_MOVE_POS/NEG` with Rate 0 immediately.

### Configuration Policy
**DO NOT** hardcode:
- Encoder counts per revolution.
- Gear ratios.
- Maximum slew speeds.
These belong in `src/celestron_aux/config.yaml`.

---

## 🤖 Information for AI Agents

- **Grep Pattern**: Use `grep -r "TODO"` to find pending implementation phases (currently Phase 17).
- **Math**: Most transformations involve `np.array` and matrix multiplication. Ensure unit vectors are always normalized.
- **Coordinates**: The mount uses Alt/Az internally. The driver converts these to 24-bit AUX step counts using `equatorial_to_steps`.
- **INDI Library**: We use `indipydriver`. When adding properties, ensure you update both the initialization in `CelestronAUXDriver.__init__` and the `on_xxx` handlers.
- **Git Policy**: Never commit `*.log` files or the `venv/` directory.
- **Documentation Language**: All files on disk (code, comments, documentation, logs) MUST be in English, regardless of the conversation language.
- **Task Management**: Use the `todowrite` tool to document and track the progress of complex tasks. Mark steps as completed immediately after finishing.

---
*Last Updated: 2026-01-27*
*Version: 1.7.5*
*Contact: jochym@gmail.com*
