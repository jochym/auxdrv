"""
Alignment Subsystem for Telescope Mounts

Provides mathematical models for coordinate transformation based on
alignment stars.
"""

import math
import numpy as np


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
    Manages N-point alignment transformation using SVD-based rotation fitting.
    Supports weighting and automatic pruning.
    """

    def __init__(self):
        self.points = []  # List of dicts: {'sky': vec, 'mount': vec, 'weight': float}
        self.matrix = np.identity(3)
        self.rms_error_arcsec = 0.0

    def add_point(self, sky_vec, mount_vec, weight=1.0):
        """Adds an alignment point and recomputes the transformation."""
        self.points.append(
            {"sky": np.array(sky_vec), "mount": np.array(mount_vec), "weight": weight}
        )
        self._compute_matrix()

    def clear(self):
        """Clears all alignment points and resets to identity."""
        self.points = []
        self.matrix = np.identity(3)
        self.rms_error_arcsec = 0.0

    def prune(self, max_points):
        """Removes oldest points to keep the count within limit."""
        if len(self.points) > max_points:
            self.points = self.points[-max_points:]
            self._compute_matrix()

    def _compute_matrix(self):
        """Computes the optimal rotation matrix using SVD."""
        if len(self.points) < 2:
            self.matrix = np.identity(3)
            self.rms_error_arcsec = 0.0
            return

        S = np.array([p["sky"] for p in self.points]).T  # 3xN
        M = np.array([p["mount"] for p in self.points]).T  # 3xN
        W = np.array([p["weight"] for p in self.points])

        # Normalize weights
        W = W / np.sum(W)

        # Weighted covariance matrix H = M * diag(W) * S.T
        H = (M * W) @ S.T

        U, _, Vt = np.linalg.svd(H)
        R = U @ Vt

        # Check for reflection
        if np.linalg.det(R) < 0:
            V = Vt.T.copy()
            V[:, 2] *= -1
            R = U @ V.T

        self.matrix = R
        self._calculate_rms()

    def _calculate_rms(self):
        """Calculates RMS error of the fit in arcseconds."""
        if not self.points:
            self.rms_error_arcsec = 0.0
            return

        total_sq_error = 0.0
        for p in self.points:
            pred_mount = self.matrix @ p["sky"]
            # Angular error between pred_mount and p['mount']
            dot = np.dot(pred_mount, p["mount"])
            dot = max(-1.0, min(1.0, dot))
            angle_rad = math.acos(dot)
            total_sq_error += angle_rad**2

        rms_rad = math.sqrt(total_sq_error / len(self.points))
        self.rms_error_arcsec = math.degrees(rms_rad) * 3600.0

    def get_local_matrix(self, target_sky_vec, local_bias):
        """
        Returns a rotation matrix weighted by proximity to the target vector.
        local_bias: float from 0.0 to 1.0 (influence of proximity).
        """
        if local_bias <= 0 or len(self.points) < 3:
            return self.matrix

        target = np.array(target_sky_vec)
        # Calculate proximity weights: Gaussian centered on target
        # sigma=0.5 corresponds to roughly 40 degrees spread
        sigma_sq = 0.5

        S = np.array([p["sky"] for p in self.points]).T
        M = np.array([p["mount"] for p in self.points]).T

        # Proximity weights
        dots = target @ S
        dist_sq = 2.0 * (1.0 - dots)
        prox_weights = np.exp(-dist_sq / sigma_sq)

        # Combine with original weights
        W = np.array([p["weight"] for p in self.points]) * (
            1.0 + 10.0 * local_bias * prox_weights
        )
        W = W / np.sum(W)

        # Weighted SVD
        H = (M * W) @ S.T
        U, _, Vt = np.linalg.svd(H)
        R = U @ Vt
        if np.linalg.det(R) < 0:
            V = Vt.T.copy()
            V[:, 2] *= -1
            R = U @ V.T
        return R

    def transform_to_mount(self, sky_vec, target_vec=None, local_bias=0.0):
        """
        Applies transformation. If target_vec and local_bias provided,
        uses proximity weighting.
        """
        R = self.matrix
        if target_vec is not None and local_bias > 0:
            R = self.get_local_matrix(target_vec, local_bias)

        res = R @ np.array(sky_vec)
        return res.tolist()

    def transform_to_sky(self, mount_vec):
        """Applies inverse transformation to a mount vector to get sky vector."""
        res = self.matrix.T @ np.array(mount_vec)
        return res.tolist()
