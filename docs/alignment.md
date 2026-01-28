# Multi-Point Alignment System

The Celestron AUX INDI driver features an advanced alignment engine based on **Singular Value Decomposition (SVD)**. This system allows for high pointing accuracy by fitting a mathematical model of the mount to multiple observed star positions.

## How it Works

The alignment process solves the **Orthogonal Procrustes Problem**: finding the optimal rotation matrix $R$ that maps a set of "sky" unit vectors $\{s_i\}$ to a set of "mount" (encoder) unit vectors $\{m_i\}$.

The driver minimizes the total squared error:
$$\text{minimize} \sum w_i \| R s_i - m_i \|^2$$

### Key Advantages
- **Robustness**: Unlike simple 3-star alignment, SVD handles any number of points ($N \ge 2$) and is mathematically stable.
- **RMS Feedback**: The driver calculates the **Root Mean Square (RMS) Error**, providing an immediate estimate of pointing accuracy in arcseconds.
- **Local Bias**: Allows heavier weighting of alignment points near the current telescope position, compensating for local mechanical errors.

## Using the Alignment System

### 1. Initial Alignment
1. Set **Coord Set Mode** to `SYNC`.
2. Center a known star in your eyepiece or camera.
3. Issue a `Sync` command from your planetarium software.
4. The star is added to the model. Repeat for at least 2-3 stars distributed across the sky.

### 2. Multi-Point Refinement
You can continue adding points throughout your session. For example, after every plate solve, performing a `Sync` will refine the model further.

### 3. Residual-Aware Grid Thinning
To ensure even sky coverage, the driver employs a grid-based thinning algorithm:
- The sky is divided into **15° x 15° sectors**.
- Each sector holds a maximum of **2 points**.
- If a sector is full, the driver evaluates the mathematical consistency and keeps only the two most reliable points.

### 4. Adaptive Model Complexity
The `AlignmentModel` automatically upgrades its complexity based on the number of stars:
- **1-2 Stars**: Simple SVD Rotation (fixed axes).
- **3-5 Stars**: 4-parameter model (Rotation + Zero Point Offsets).
- **6+ Stars**: Full 6-parameter geometric model, compensating for:
  - **Cone Error ($CH$):** Non-perpendicularity between OTA and Dec axis.
  - **NP ($NP$):** Non-perpendicularity between axes.
  - **Altitude Index ($ID$):** Zero-point offset in the Altitude axis.
