# Hardware Testing Guide (Step-by-Step)

Follow these steps to safely verify the Celestron AUX driver with real hardware.

## Prerequisites
- **Python Environment**: Ensure you have installed the requirements:
  ```bash
  pip install -r requirements.txt
  ```
- **ASTAP (for PPT only)**: Install ASTAP and at least the H17 star database.
- **Hardware**: Mount connected via Serial (USB) or Network (WiFi/Ethernet).

---

## Step 1: Baseline Hardware Interaction (HIT)

This test ensures the mount moves correctly and safely.

1.  **Start the INDI Server**:
    Run the driver. It will act as an INDI server on port 7624.
    ```bash
    python celestron_indi_driver.py
    ```
2.  **Configure the Connection**:
    Open another terminal and run the HIT script:
    ```bash
    python scripts/hit_validation.py
    ```
3.  **Perform the Audit**:
    - **Connection**: Confirm the script connects. Center the mount manually if needed.
    - **Safety Check**: Verify you have enough cable length for 360-degree rotation.
    - **Pulse N/S/E/W**: The script will pulse each direction. **Watch the mount**. Acknowledge in the CLI only if the physical motion matches the command.
    - **Rate Audit**: Confirm that "Rate 9" is significantly faster than "Rate 2".
    - **Abort Test**: Press **Space** during any movement to verify the mount stops immediately.

---

## Step 2: Photography & Pointing Accuracy (PPT)

This test measures the absolute precision of the geometric model.

1.  **Prepare the Setup**:
    - Mount with Telescope and Camera attached.
    - Balanced and roughly polar aligned (if EQ).
    - Camera driver running (e.g., `indi_asi_ccd`).
2.  **Initial Alignment**:
    - Center a bright star.
    - Plate-solve and **Sync** using your favorite planetarium (KStars/Ekos) OR let the PPT script handle it.
3.  **Run PPT Script**:
    ```bash
    python scripts/ppt_accuracy.py --camera "Your Camera Name"
    ```
4.  **Verification**:
    - The script will slew to several targets.
    - At each stop, it captures an image and invokes ASTAP.
    - **Do not touch the mount** during this process.
    - Review the final report. An RMS error < 60 arcsec is excellent for this mount class.

---

## Troubleshooting

### HIT fails to connect
- Check if `celestron_indi_driver.py` is still running.
- Ensure no other software (like KStars) is already using port 7624 on the same host.

### ASTAP fails to solve
- Check if the camera is focused.
- Ensure the `UPLOAD_DIR` in `scripts/ppt_accuracy.py` is writable.
- Verify ASTAP can solve a single image manually: `astap -f sample.fits -solve`.

### Emergency Stop
If the mount behaves unexpectedly:
1.  Press **Space** in the script terminal.
2.  Power off the mount if needed.
3.  The driver also enforces software slew limits configured in `config.yaml`.
