# Multi-Point Alignment System

The Celestron AUX INDI driver features an advanced alignment engine based on **Singular Value Decomposition (SVD)**. This system allows for high pointing accuracy by fitting a mathematical model of the mount to multiple observed star positions.

## How it Works

The alignment process solves the **Orthogonal Procrustes Problem**: finding the optimal rotation matrix $R$ that maps a set of "sky" unit vectors $\{s_i\}$ to a set of "mount" (encoder) unit vectors $\{m_i\}$.

The driver minimizes the total squared error:
$$\text{minimize} \sum w_i \| R s_i - m_i \|^2$$

### Key Advantages
- **Robustness**: Unlike simple 3-star alignment, SVD handles any number of points ($N \ge 2$) and is mathematically stable.
- **RMS Feedback**: The driver calculates the **Root Mean Square (RMS) Error**, providing an immediate estimate of pointing accuracy in arcseconds.
- **Local Bias**: Allows heavier weighting of alignment points near the current telescope position, compensating for local mechanical errors like mirror flop or flexure.

## Using the Alignment System

### 1. Initial Alignment
1. Set **Coord Set Mode** to `SYNC`.
2. Center a known star in your eyepiece or camera.
3. Issue a `Sync` command from your planetarium software (e.g., KStars, Stellarium).
4. The star is added to the model. Repeat for at least 2-3 stars distributed across the sky for a good global model.

### 2. Multi-Point Refinement
You can continue adding points throughout your session. For example, after every plate solve, performing a `Sync` will refine the model further.

### 3. Advanced Configuration
Located in the **Alignment** tab:
- **Max Points**: Limits the number of points in the model (Circular Buffer). Default is 50.
- **Auto Prune**: If enabled, the oldest point is removed when `Max Points` is reached.
- **Local Bias (%)**:
  - `0%`: Global model (all points equal).
  - `>0%`: Points closer to the current target are prioritized. This is ideal for high-precision GoTo in a specific area of the sky.

### 4. Diagnostics
- **Point Count**: Total number of stars currently in the model.
- **RMS Error**: The mathematical "fit quality." A high RMS (e.g., > 120 arcsec) may indicate a bad sync point. Use `Clear Last` to remove the most recent point if it degraded the model.
