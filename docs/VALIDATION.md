# Hardware and Pointing Validation Guide

This document describes how to set up the environment and run the validation scripts for the Celestron AUX driver.

## 1. Hardware Interaction Test (HIT)

The HIT script (`scripts/hit_validation.py`) is used to verify that the driver communicates correctly with the physical mount and that the motion axes are correctly mapped.

### Setup
1.  Connect your mount to your computer (Serial or Network).
2.  Start the INDI server with the Celestron AUX driver:
    ```bash
    python celestron_indi_driver.py
    ```
    *(By default, it listens on port 7624)*.

### Running the Test
```bash
python scripts/hit_validation.py --host localhost --port 7624
```
Follow the interactive prompts. The script will ask you to confirm physical movement in each direction.

---

## 2. Photography & Pointing Test (PPT)

The PPT script (`scripts/ppt_accuracy.py`) measures absolute pointing accuracy using a camera and plate solver.

### Prerequisites
1.  **ASTAP**: Must be installed and available in your PATH.
    - [Download ASTAP](https://www.hnsky.org/astap.htm)
    - Ensure you have the star database (H17 or H18) installed.
2.  **INDI Camera Driver**: A working INDI driver for your camera (e.g., `indi_asi_ccd`, `indi_qhy_ccd`, or `indi_simulator_ccd`).

### Setup
1.  Start the `Celestron AUX` driver.
2.  Start your camera driver.
3.  Ensure both are connected to the same INDI server (or running as standalone drivers on known ports).

### Configuration
Edit the `scripts/ppt_accuracy.py` or use command-line arguments (if implemented) to set:
- `mount_device`: Name of your mount in INDI (default: "Celestron AUX").
- `camera_device`: Name of your camera in INDI (e.g., "ZWO CCD ASI120MM").

### Running the Test
```bash
python scripts/ppt_accuracy.py
```
The script will:
1.  Slew to a grid of targets.
2.  Capture a 2s exposure.
3.  Run ASTAP to find the true coordinates.
4.  Calculate and log the pointing error.

---

## 3. Testing with Simulators (Dry Run)

You can test the entire logic without hardware:

1.  **Start Mount Simulator**:
    ```bash
    python simulator/nse_simulator.py -t -p 2000
    ```
2.  **Start INDI Driver**:
    ```bash
    python celestron_indi_driver.py
    ```
3.  **Start CCD Simulator** (If you have standard INDI tools installed):
    ```bash
    indiserver indi_simulator_ccd
    ```
4.  **Run Scripts**:
    Point the scripts to `localhost`.
