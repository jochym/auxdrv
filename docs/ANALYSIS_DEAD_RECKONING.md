# Analysis: Dead Reckoning Tracking Performance

This document analyzes the "Dead Reckoning" (DR) tracking mode, comparing the Python driver's implementation with the reference C++ driver (`indi-celestronaux`).

## 1. The Quantization Problem

In predictive tracking for Alt-Az mounts, we calculate the motor rates by differentiating the position:
$$\omega = \frac{P(T + dt) - P(T - dt)}{2 \cdot dt}$$

Where $P$ is the position in encoder steps.

### 1.1. Python Driver (v1.6.2)
*   **Interval**: $dt = 0.1s$ (Total span $0.2s$)
*   **Sidereal Motion**: $\approx 15''/s \approx 698$ steps/s.
*   **Quantization Noise**: At $dt=0.1s$, the total displacement is $\approx 140$ steps. If the position is rounded to integer steps *before* differentiation, a $\pm 1$ step rounding error results in a velocity error of:
    $$\text{Error} = \frac{1}{0.2} = 5 \text{ steps/s} \approx 0.11''/s$$
    Over 60 seconds, this accumulates to **$6.6''$ of drift**.

### 1.2. Reference Driver (C++)
*   **Interval**: $dt = 5.0s$ (Total span $10s$)
*   **Sidereal Motion**: $\approx 6980$ steps in 10s.
*   **Quantization Noise**: Even if rounded to integers, a $\pm 1$ step error results in:
    $$\text{Error} = \frac{1}{10} = 0.1 \text{ steps/s} \approx 0.002''/s$$
    Over 60 seconds, this accumulates to **$0.12''$ of drift**.

## 2. Findings

The sub-arcsecond stability is achieved through **High-Inertia Differentiation** and **Sub-step Rate Estimation**. By using a larger time window ($30s$) and calculating the velocity using floating-point intermediate values *before* rounding to the 24-bit AUX command, we effectively filter out the quantization noise inherent in fixed-point coordinate systems.

## 3. Optimization Strategy

To exceed reference performance, the Python driver now:
1.  **Uses dt=30.0s interval**: Provides maximum noise suppression for sidereal rates.
2.  **Maintains Floating-Point Encoders**: Internal coordinate transforms return floats, allowing the tracking loop to see "between" the 24-bit physical steps when calculating velocities.
3.  **High-Precision Rates**: Uses the exact hardware multiplier ($79.1015625$) for the final 24-bit MC rate commands.
