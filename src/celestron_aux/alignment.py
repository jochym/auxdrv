"""
Alignment Subsystem for Telescope Mounts

Provides mathematical models for coordinate transformation based on
alignment stars.
"""

import math
import numpy as np
from scipy.optimize import least_squares


def angular_distance(az1, alt1, az2, alt2):
    """Calculates angular distance between two points in degrees."""
    r1 = math.radians(alt1)
    r2 = math.radians(alt2)
    d_az = math.radians(az1 - az2)

    cos_dist = math.sin(r1) * math.sin(r2) + math.cos(r1) * math.cos(r2) * math.cos(
        d_az
    )
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_dist))))


def vector_from_radec(ra_hours, dec_deg):
    """Converts RA/Dec to a 3D unit vector."""
    ra_rad = math.radians(ra_hours * 15.0)
    dec_rad = math.radians(dec_deg)
    return [
        math.cos(dec_rad) * math.cos(ra_rad),
        math.cos(dec_rad) * math.sin(ra_rad),
        math.sin(dec_rad),
    ]


def vector_from_altaz(az_deg, alt_deg):
    """Converts Alt/Az to a 3D unit vector."""
    az_rad = math.radians(az_deg)
    alt_rad = math.radians(alt_deg)
    return [
        math.cos(alt_rad) * math.cos(az_rad),
        math.cos(alt_rad) * math.sin(az_rad),
        math.sin(alt_rad),
    ]


def vector_to_radec(vec):
    """Converts a 3D unit vector to RA (hours) and Dec (degrees)."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm < 1e-9:
        return 0, 0
    vx, vy, vz = [x / norm for x in vec]

    dec_rad = math.asin(max(-1.0, min(1.0, vz)))
    ra_rad = math.atan2(vy, vx)

    dec_deg = math.degrees(dec_rad)
    ra_hours = math.degrees(ra_rad) / 15.0
    return ra_hours % 24.0, dec_deg


def vector_to_altaz(vec):
    """Converts a 3D unit vector to Azimuth and Altitude (degrees)."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm < 1e-9:
        return 0, 0
    vx, vy, vz = [x / norm for x in vec]

    alt_rad = math.asin(max(-1.0, min(1.0, vz)))
    az_rad = math.atan2(vy, vx)

    alt_deg = math.degrees(alt_rad)
    az_deg = math.degrees(az_rad)
    return az_deg % 360.0, alt_deg


class AlignmentModel:
    """
    Manages N-point alignment transformation using a 6-parameter geometric model.
    Compensates for Rotation, Cone Error, Non-Perpendicularity, and Index Offsets.
    """

    def __init__(self):
        self.points = []  # List of dicts: {'sky': vec, 'mount': vec, 'weight': float}
        self.matrix = np.identity(3)
        self.params = np.zeros(6)  # [roll, pitch, yaw, ID, CH, NP]
        self.rms_error_arcsec = 0.0

    def add_point(
        self, sky_vec, mount_vec, weight=1.0, sector_size=15.0, max_per_sector=2
    ):
        """
        Adds an alignment point using Residual-Aware Grid Thinning.
        Ensures even sky coverage by managing points in angular sectors.
        """
        new_az, new_alt = vector_to_altaz(sky_vec)

        # Determine sector ID
        s_az = int(new_az / sector_size)
        s_alt = int((new_alt + 90.0) / sector_size)
        sector_id = (s_az, s_alt)

        # Find points in the same sector
        sector_indices = []
        for i, p in enumerate(self.points):
            p_az, p_alt = vector_to_altaz(p["sky"])
            if (
                int(p_az / sector_size),
                int((p_alt + 90.0) / sector_size),
            ) == sector_id:
                sector_indices.append(i)

        new_pt = {
            "sky": np.array(sky_vec),
            "mount": np.array(mount_vec),
            "weight": weight,
        }

        if len(sector_indices) < max_per_sector:
            self.points.append(new_pt)
        else:
            # Sector is full. Evaluate residuals and drop the worst point.
            # We compare existing points in sector + the new point.
            candidates = [self.points[idx] for idx in sector_indices] + [new_pt]
            residuals = []
            for pt in candidates:
                # Use current model to evaluate consistency
                if len(self.points) < 6:
                    m_pred = self.matrix @ pt["sky"]
                else:
                    m_pred = self._transform_internal(pt["sky"], self.params)

                dot = np.dot(m_pred, pt["mount"])
                dot = np.clip(dot, -1.0, 1.0)
                residuals.append(math.acos(dot))

            worst_local_idx = np.argmax(residuals)

            if worst_local_idx < max_per_sector:
                # One of the existing points is worse than the new one
                self.points[sector_indices[worst_local_idx]] = new_pt
            # else: the new point is the worst in its sector, so we ignore it.

        self._compute_model()

    def clear(self):
        """Clears all alignment points and resets to identity."""
        self.points = []
        self.matrix = np.identity(3)
        self.params = np.zeros(6)
        self.rms_error_arcsec = 0.0

    def _get_rotation_matrix(self, r, p, y):
        """Creates a 3D rotation matrix from Euler angles."""
        # Roll, Pitch, Yaw
        c1, s1 = math.cos(r), math.sin(r)
        c2, s2 = math.cos(p), math.sin(p)
        c3, s3 = math.cos(y), math.sin(y)

        R_x = np.array([[1, 0, 0], [0, c1, -s1], [0, s1, c1]])
        R_y = np.array([[c2, 0, s2], [0, 1, 0], [-s2, 0, c2]])
        R_z = np.array([[c3, -s3, 0], [s3, c3, 0], [0, 0, 1]])

        return R_z @ R_y @ R_x

    def _transform_internal(self, sky_vec, params):
        """Applies the 6-parameter model transformation."""
        # 1. Rotation
        R = self._get_rotation_matrix(params[0], params[1], params[2])
        v = R @ sky_vec

        # 2. Extract Alt/Az
        az, alt = vector_to_altaz(v)
        alt_rad = math.radians(alt)

        # 3. Apply mechanical corrections (ID, CH, NP)
        # All params are in RADIANS for better solver convergence
        cos_alt = max(0.01, math.cos(alt_rad))
        tan_alt = math.tan(alt_rad)

        az_corr_rad = params[4] / cos_alt + params[5] * tan_alt
        alt_corr_rad = params[3]

        return vector_from_altaz(
            az + math.degrees(az_corr_rad), alt + math.degrees(alt_corr_rad)
        )

    def _compute_model(self):
        """Fits the adaptive geometric model to the collected points."""
        if len(self.points) == 0:
            self.matrix = np.identity(3)
            self.params = np.zeros(6)
            self.rms_error_arcsec = 0.0
            return

        # Baseline: SVD rotation
        self._compute_svd_only()

        # Phase 1: 1-2 points -> SVD only (already done above)
        if len(self.points) < 3:
            return

        # Phase 2: 3-5 points -> 4-parameter model (Rotation + ID)
        # Phase 3: 6+ points -> 6-parameter model (Rotation + ID + CH + NP)
        solve_params = 6 if len(self.points) >= 6 else 4

        # Refine model using Non-linear Least Squares
        def residuals(p):
            # p might be 4 or 6 elements
            full_p = np.zeros(6)
            full_p[: len(p)] = p
            res = []
            for pt in self.points:
                m_pred = self._transform_internal(pt["sky"], full_p)
                dot = np.dot(m_pred, pt["mount"])
                dot = np.clip(dot, -1.0, 1.0)
                res.append(math.acos(dot) * pt["weight"])
            return np.array(res)

        # Initial guess from SVD matrix
        sy = math.sqrt(
            self.matrix[0, 0] * self.matrix[0, 0]
            + self.matrix[1, 0] * self.matrix[1, 0]
        )
        singular = sy < 1e-6
        if not singular:
            r = math.atan2(self.matrix[2, 1], self.matrix[2, 2])
            p = math.atan2(-self.matrix[2, 0], sy)
            y = math.atan2(self.matrix[1, 0], self.matrix[0, 0])
        else:
            r = math.atan2(-self.matrix[1, 2], self.matrix[1, 1])
            p = math.atan2(-self.matrix[2, 0], sy)
            y = 0

        initial_p = np.array([r, p, y, 0.0, 0.0, 0.0])[:solve_params]

        # Use a robust solver
        res = least_squares(
            residuals, initial_p, method="trf", ftol=1e-12, xtol=1e-12, diff_step=1e-4
        )

        self.params = np.zeros(6)
        self.params[: len(res.x)] = res.x

        # Update base rotation matrix from the solved Euler angles
        self.matrix = self._get_rotation_matrix(
            self.params[0], self.params[1], self.params[2]
        )
        self._calculate_rms()

    def _compute_svd_only(self):
        """Computes optimal rotation matrix using SVD (fallback)."""
        if len(self.points) < 1:
            self.matrix = np.identity(3)
            self.params = np.zeros(6)
            self.rms_error_arcsec = 0.0
            return

        if len(self.points) == 1:
            s = self.points[0]["sky"]
            m = self.points[0]["mount"]
            v = np.cross(s, m)
            sine = np.linalg.norm(v)
            cosine = np.dot(s, m)
            if sine < 1e-9:
                self.matrix = np.identity(3) if cosine > 0 else -np.identity(3)
            else:
                v = v / sine
                K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
                self.matrix = np.identity(3) + sine * K + (1 - cosine) * (K @ K)
        else:
            S = np.array([p["sky"] for p in self.points]).T
            M = np.array([p["mount"] for p in self.points]).T
            W = np.array([p["weight"] for p in self.points])
            W = W / np.sum(W)
            H = (M * W) @ S.T
            U, _, Vt = np.linalg.svd(H)
            R = U @ Vt
            if np.linalg.det(R) < 0:
                V = Vt.T.copy()
                V[:, 2] *= -1
                R = U @ V.T
            self.matrix = R

        self.params = np.zeros(6)
        self._calculate_rms()

    def _calculate_rms(self):
        """Calculates RMS error of the fit in arcseconds."""
        if not self.points:
            self.rms_error_arcsec = 0.0
            return

        total_sq_error = 0.0
        for p in self.points:
            if len(self.points) < 3:
                pred_mount = self.matrix @ p["sky"]
            else:
                pred_mount = self._transform_internal(p["sky"], self.params)

            dot = np.dot(pred_mount, p["mount"])
            dot = max(-1.0, min(1.0, dot))
            angle_rad = math.acos(dot)
            total_sq_error += angle_rad**2

        rms_rad = math.sqrt(total_sq_error / len(self.points))
        self.rms_error_arcsec = math.degrees(rms_rad) * 3600.0

    def transform_to_mount(self, sky_vec, target_vec=None, local_bias=0.0):
        """Applies transformation with optional local weighting."""
        if len(self.points) < 3:
            R = self.matrix
            if target_vec is not None and local_bias > 0:
                R = self.get_local_matrix(
                    target_sky_vec=target_vec, local_bias=local_bias
                )
            res = R @ np.array(sky_vec)
            return res.tolist()

        return self._transform_internal(np.array(sky_vec), self.params)

    def transform_to_sky(self, mount_vec):
        """Applies inverse transformation."""
        res = self.matrix.T @ np.array(mount_vec)
        return res.tolist()

    def get_local_matrix(self, target_sky_vec, local_bias):
        """Returns a weighted SVD matrix (Fallback for small point counts)."""
        if local_bias <= 0 or len(self.points) < 2:
            return self.matrix

        target = np.array(target_sky_vec)
        sigma_sq = 0.5
        S = np.array([p["sky"] for p in self.points]).T
        M = np.array([p["mount"] for p in self.points]).T
        dots = target @ S
        dist_sq = 2.0 * (1.0 - dots)
        prox_weights = np.exp(-dist_sq / sigma_sq)
        W = np.array([p["weight"] for p in self.points]) * (
            1.0 + 10.0 * local_bias * prox_weights
        )
        W = W / np.sum(W)
        H = (M * W) @ S.T
        U, _, Vt = np.linalg.svd(H)
        R = U @ Vt
        if np.linalg.det(R) < 0:
            V = Vt.T.copy()
            V[:, 2] *= -1
            R = U @ V.T
        return R
