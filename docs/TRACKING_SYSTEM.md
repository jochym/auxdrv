# Tracking System Design & Analysis

This document describes the tracking logic implemented in the Python Celestron AUX INDI Driver (v1.6.2+) and provides a comparative analysis against the reference C++ driver (`indi-celestronaux`).

## 1. Tracking Philosophy

The goal of the tracking system is to keep a celestial object (Sidereal, Solar, Lunar, or Satellite) centered in the telescope's Field of View (FOV) by continuously adjusting the motor velocities. 

There are two primary approaches to tracking:
1.  **Passive/Mode-based**: Sending a command to the mount's Motor Controller (MC) to move at a predefined rate (e.g., Sidereal). The MC handles the timing.
2.  **Active/Predictive**: The driver calculates the required Alt/Az velocities in real-time and sends "Guide Rate" commands to the MC. This is necessary for Alt-Az mounts because their tracking rates are non-linear and time-dependent.

## 2. Current Implementation (Python Driver)

The Python driver uses an **Active Predictive Loop**.

### 2.1. Mathematical Model (Velocity Estimation)

To follow an object, we need the first derivative of its Alt/Az position with respect to time:
$$\omega_{azm} = \frac{d(Azm)}{dt}, \quad \omega_{alt} = \frac{d(Alt)}{dt}$$

We estimate these using a **Central Difference** numerical derivative to achieve 2nd-order accuracy ($O(dt^2)$):

1.  **Coordinate Resolution**: Given a target $(RA, Dec)$ at time $T$:
    *   $P_{+} = \text{EquatorialToSteps}(RA, Dec, T + dt)$
    *   $P_{-} = \text{EquatorialToSteps}(RA, Dec, T - dt)$
2.  **Rate Calculation**:
    $$\text{rate} = \frac{P_{+} - P_{-}}{2 \cdot dt} \text{ [steps/sec]}$$
3.  **AUX Protocol Conversion**:
    The Celestron AUX protocol expects guide rates in units of approximately $1/1024$ arcseconds per second.
    $$\text{val} = |\text{rate}| \cdot \frac{360 \cdot 3600 \cdot 1024}{\text{StepsPerRevolution}}$$
4.  **Loop Execution**:
    The loop runs every 1.0 seconds, using a sampling interval $dt = 0.1s$.

### 2.2. Target Locking
To prevent feedback drift (where small errors in position reporting update the target and create a "walking" effect), the driver "locks" the $(RA, Dec)$ target at the moment the tracking is engaged. All future velocity calculations are derived from this fixed coordinate.

---

## 3. Comparative Analysis: Reference C++ Driver

The reference driver (`indi-celestronaux`) uses a more sophisticated **Hybrid Predictive-Corrective** model.

### 3.1. Similarities
*   **Predictive Component**: Like the Python driver, it uses central difference for velocity estimation. It uses a larger $dt$ (5.0s) but the principle is identical.
*   **Active Loop**: It uses an INDI `TimerHit` loop to refresh rates.

### 3.2. Key Differences (Reference Advantages)

#### A. Positional Error Correction (PID)
The C++ driver does not just calculate *where the star is going*; it also checks *where the telescope actually is*.
*   **Logic**: It compares the `IdealAltAz` (where the star should be) with the `EncoderAltAz` (where the mount reports it is).
*   **Math**: 
    $$\text{Error} = \text{Ideal} - \text{Actual}$$
    $$\text{CorrectionRate} = PID(\text{Error})$$
    $$\text{TotalRate} = \text{PredictedRate} + \text{CorrectionRate}$$
*   **Result**: This eliminates cumulative drift caused by mechanical lag, timing jitter, or rounding errors.

#### B. Passive Tracking for GEM
For Equatorial (GEM) mounts, the reference driver uses the mount's built-in sidereal tracking mode (`trackByMode`) and remains passive. It only engages the active loop for Alt-Az mounts.

#### C. Adaptive Tuning
The C++ driver includes an `adaptive_tuner.cpp` which dynamically calculates the PID gains ($K_p, K_i, K_d$) by monitoring the system's response. This allows the driver to optimize itself for different payloads and gear conditions.

---

## 4. Gap Analysis & Proposed Improvements

While the Python driver's current predictive model is stable, it lacks the "closed-loop" feedback found in the reference driver.

### 4.1. Proposed Phase 17+ Architecture
To reach or exceed reference accuracy, we should implement:

1.  **PID Feedback Controller**:
    *   Integrate a simple PID controller into `_tracking_loop`.
    *   State: `error = target_steps - current_steps`.
    *   Correction: `adj = Kp * error + Ki * sum(error) + Kd * d(error)/dt`.
2.  **Dual-Track Mode**:
    *   **Alt-Az**: Active Hybrid (Predictive + PID).
    *   **GEM**: Passive (Hardware Sidereal) with periodic small "Sync" corrections if drift is detected.
3.  **High-Frequency Polling**:
    *   Reduce `read_mount_position` interval during tracking to provide smoother data to the PID controller.

## 5. Summary Table

| Feature | Python Driver (v1.6.2) | Reference C++ |
| :--- | :--- | :--- |
| **Model** | Pure Predictive | Hybrid (Predictive + PID) |
| **Derivative** | Central Difference ($dt=0.1s$) | Central Difference ($dt=5.0s$) |
| **Feedback** | Target Locking only | Full Closed-Loop PID |
| **Tuning** | Static | Adaptive |
| **Drift Resistance**| Good (Short-term) | Excellent (Long-term) |
