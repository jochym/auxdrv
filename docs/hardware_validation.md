# Hardware Validation and Compatibility

**CAUTION: Experimental Status**

As of version 1.7.6, this driver is primarily validated against the `caux-sim` simulator. Deployment on physical hardware should be approached with extreme caution. The following scripts are provided for testing purposes.

## Hardware Interaction Test (HIT)

The HIT script (`scripts/hit_validation.py`) verifies safe movement and bus communication.

1.  **Start the INDI Server**:
    ```bash
    python src/celestron_aux/celestron_indi_driver.py
    ```
2.  **Run the Test**:
    ```bash
    python scripts/hit_validation.py
    ```
- **Pulse N/S/E/W**: Verify physical motion matches the command.
- **Abort Test**: Press **Space** during movement to verify immediate stop.

## Photography & Pointing Test (PPT)

The PPT script (`scripts/ppt_accuracy.py`) automates pointing error measurement using a camera and plate solver (requires ASTAP).

```bash
python scripts/ppt_accuracy.py --camera "Your Camera"
```

## Periodic Error (PE) Measurement

The `scripts/pec_measure.py` script measures tracking stability over a long period.

```bash
python scripts/pec_measure.py --duration 20
```

## Feature Parity Checklist

| Feature | Python Status | C++ Parity |
| :--- | :--- | :--- |
| **Serial (Direct AUX)** | ✅ Done | Yes |
| **Serial (via HC)** | ✅ Done | Yes |
| **TCP/IP (WiFi)** | ✅ Done | Yes |
| **Manual Slew** | ✅ Done | Yes |
| **Fast GoTo** | ✅ Done | Yes |
| **Slow Approach** | ✅ Done | Yes |
| **Anti-backlash** | ✅ Done | Yes |
| **Sidereal Tracking** | ✅ Done | Yes |
| **Multi-Point SVD** | ✅ Done | Yes |
| **6-Param Geometric** | ✅ Done | **Improved** |
| **Focuser** | ✅ Done | Yes |
| **GPS / RTC** | ✅ Done | Yes |
| **Power/Battery** | ✅ Done | **New** |

## Readiness Checklist

1.  [ ] **Balance**: OTA perfectly balanced.
2.  [ ] **Cables**: 360-degree clearance.
3.  [ ] **Soft Limits**: `TELESCOPE_LIMITS` configured.
4.  [ ] **Emergency Abort**: Keyboard within reach (Space key).
