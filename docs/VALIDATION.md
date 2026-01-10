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

### 2.1 Periodic Error (PE) Measurement
The `scripts/pec_measure.py` script specifically measures the tracking stability over a long period (e.g., 20 minutes) to identify Periodic Error. It uses ASTAP to solve a sequence of frames.

```bash
python scripts/pec_measure.py --duration 20 --interval 30 --mount "Celestron AUX" --camera "Your Camera"
```

---

## 3. Adaptive Alignment Analysis

The driver uses an adaptive model that improves as more points are added. Below is the typical accuracy improvement measured in the high-fidelity simulator (with 5' Cone Error and 3' Non-Perpendicularity active):

| Points | Local Error (5°) | Global Error | Model Active |
| :--- | :--- | :--- | :--- |
| 1 | ~48" | ~28000" | SVD (Rotation only) |
| 2 | ~35" | ~28000" | SVD (Rotation only) |
| 3 | ~41" | ~28000" | 4-Param (Rotation + ID) |
| 6+ | ~60" | ~28000" | 6-Param (Full Geometric) |

*Note: Global error remains high in this test because points are clustered locally. For global accuracy, points must be distributed across the sky.*

---

## 4. Testing with Simulators (Dry Run)

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
