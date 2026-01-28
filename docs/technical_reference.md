# Technical Reference

## Architecture

The driver is asynchronous, using `asyncio` to manage the INDI state machine and AUX protocol communication.

- `celestron_indi_driver.py`: INDI state machine and property mapping.
- `celestron_aux_driver.py`: AUX protocol handling and packet management.
- `alignment.py`: SVD-based coordinate transformations.

## Tracking Logic

The driver uses an active tracking loop.

### Velocity Estimation
The first derivative of Alt/Az positions is estimated using a central difference:
$$\omega = \frac{P(T + dt) - P(T - dt)}{2 \cdot dt}$$

### Noise Reduction
To reduce quantization noise from the 24-bit encoder steps, the driver employs:
1.  **30-second window**: Used for sidereal rates.
2.  **Floating-Point Encoders**: Internal transforms use floats to maintain precision between physical steps.
3.  **Sub-step Rate Estimation**: Velocity is calculated using floating-point values before conversion to 24-bit hardware commands.

### Drift Analysis
A larger time window (up to 30s) reduces the impact of rounding errors, maintaining stability during tracking.

