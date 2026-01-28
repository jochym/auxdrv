# Technical Reference

## Architecture

The driver is fully asynchronous, utilizing `asyncio` to manage the INDI state machine and low-level AUX protocol communication without blocking.

- `celestron_indi_driver.py`: Manages the INDI state machine and property mapping.
- `celestron_aux_driver.py`: Implements the binary packet protocol, checksums, and low-level I/O.
- `alignment.py`: Implements the SVD-based transformation matrix.

## Tracking System Design

The driver uses an **Active Predictive Loop** for tracking.

### Velocity Estimation
We estimate the first derivative of Alt/Az positions using a **Central Difference** numerical derivative:
$$\omega = \frac{P(T + dt) - P(T - dt)}{2 \cdot dt}$$

### High-Inertia Tracking
To eliminate quantization noise from 24-bit encoder steps, the driver employs:
1.  **30-second window**: Provides noise suppression for sidereal rates.
2.  **Floating-Point Encoders**: Internal transforms return floats, allowing the tracking loop to see "between" physical steps.
3.  **Sub-step Rate Estimation**: Calculates velocity using floating-point values before rounding to the 24-bit AUX command.

### Dead Reckoning Analysis
At $dt=0.1s$, a $\pm 1$ step rounding error results in $\approx 6.6''$ of drift per minute. By using $dt=5.0s$ or larger windows (up to 30s), the drift is reduced to $< 0.12''$ per minute, achieving sub-arcsecond stability.
