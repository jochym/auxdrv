# Multi-Point Alignment System

The driver includes an alignment engine based on **Singular Value Decomposition (SVD)**. This system fits a mathematical model of the mount to observed star positions.

## How it Works

The alignment process solves the **Orthogonal Procrustes Problem**: finding a rotation matrix $R$ that maps "sky" unit vectors $\{s_i\}$ to "mount" (encoder) unit vectors $\{m_i\}$.

The driver minimizes the squared error:
$$\text{minimize} \sum w_i \| R s_i - m_i \|^2$$

### Characteristics
- **Robustness**: Handles $N \ge 2$ points and is mathematically stable.
- **RMS Feedback**: Calculates the **Root Mean Square (RMS) Error** in arcseconds.
- **Local Bias**: Allows weighting points near the current position to compensate for local mechanical errors.

## Operation

### 1. Initial Alignment
1. Set **Coord Set Mode** to `SYNC`.
2. Center a star in the eyepiece or camera.
3. Issue a `Sync` command from the client software.
4. Repeat for 2-3 stars distributed across the sky.

### 2. Refinement
You can add points throughout a session. Performing a `Sync` after a plate solve will update the model.

### 3. Grid Thinning
To maintain sky coverage, the driver uses a grid-based algorithm:
- The sky is divided into **15° x 15° sectors**.
- Each sector holds a maximum of **2 points**.
- If a sector is full, the driver keeps the points with the lowest residuals.

### 4. Model Complexity
The complexity scales with the number of points:
- **1-2 Stars**: Rotation only (SVD).
- **3-5 Stars**: 4-parameter model (Rotation + Zero Point Offsets).
- **6+ Stars**: 6-parameter geometric model, compensating for:
  - **Cone Error ($CH$):** Non-perpendicularity between OTA and Dec axis.
  - **NP ($NP$):** Non-perpendicularity between axes.
  - **Altitude Index ($ID$):** Zero-point offset in the Altitude axis.

