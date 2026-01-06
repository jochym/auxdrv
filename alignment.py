"""
Alignment Subsystem for Telescope Mounts

Provides mathematical models for coordinate transformation based on 
alignment stars.
"""

import math

def vector_from_radec(ra_hours, dec_deg):
    """Converts RA/Dec to a 3D unit vector."""
    ra_rad = math.radians(ra_hours * 15.0)
    dec_rad = math.radians(dec_deg)
    return [
        math.cos(dec_rad) * math.cos(ra_rad),
        math.cos(dec_rad) * math.sin(ra_rad),
        math.sin(dec_rad)
    ]

def vector_from_altaz(az_deg, alt_deg):
    """Converts Alt/Az to a 3D unit vector."""
    az_rad = math.radians(az_deg)
    alt_rad = math.radians(alt_deg)
    return [
        math.cos(alt_rad) * math.cos(az_rad),
        math.cos(alt_rad) * math.sin(az_rad),
        math.sin(alt_rad)
    ]

def vector_to_radec(vec):
    """Converts a 3D unit vector to RA (hours) and Dec (degrees)."""
    norm = math.sqrt(sum(x*x for x in vec))
    if norm < 1e-9: return 0, 0
    vx, vy, vz = [x/norm for x in vec]
    
    dec_rad = math.asin(max(-1.0, min(1.0, vz)))
    ra_rad = math.atan2(vy, vx)
    
    dec_deg = math.degrees(dec_rad)
    ra_hours = math.degrees(ra_rad) / 15.0
    return ra_hours % 24.0, dec_deg

def vector_to_altaz(vec):
    """Converts a 3D unit vector to Azimuth and Altitude (degrees)."""
    norm = math.sqrt(sum(x*x for x in vec))
    if norm < 1e-9: return 0, 0
    vx, vy, vz = [x/norm for x in vec]
    
    alt_rad = math.asin(max(-1.0, min(1.0, vz)))
    az_rad = math.atan2(vy, vx)
    
    alt_deg = math.degrees(alt_rad)
    az_deg = math.degrees(az_rad)
    return az_deg % 360.0, alt_deg

class AlignmentModel:
    """
    Manages N-point alignment transformation using a 3x3 matrix.
    """
    def __init__(self):
        self.points = [] # List of (SkyVector, MountVector)
        self.matrix = None
        self.inv_matrix = None

    def add_point(self, sky_vec, mount_vec):
        """Adds an alignment point and recomputes the transformation matrix."""
        self.points.append((sky_vec, mount_vec))
        if len(self.points) > 3:
            self.points.pop(0)
        self._compute_matrix()

    def clear(self):
        """Clears all alignment points and resets to identity transformation."""
        self.points = []
        self.matrix = None
        self.inv_matrix = None

    def _compute_matrix(self):
        """Computes the transformation matrix and its inverse using 3 points."""
        if len(self.points) < 3:
            self.matrix = None
            self.inv_matrix = None
            return
        
        S = [p[0] for p in self.points]
        E = [p[1] for p in self.points]
        
        try:
            def invert_3x3(M):
                det = (M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1]) -
                       M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0]) +
                       M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]))
                if abs(det) < 1e-9: return None
                inv_det = 1.0 / det
                return [
                    [(M[1][1] * M[2][2] - M[1][2] * M[2][1]) * inv_det,
                     (M[0][2] * M[2][1] - M[0][1] * M[2][2]) * inv_det,
                     (M[0][1] * M[1][2] - M[0][2] * M[1][1]) * inv_det],
                    [(M[1][2] * M[2][0] - M[1][0] * M[2][2]) * inv_det,
                     (M[0][0] * M[2][2] - M[0][2] * M[2][0]) * inv_det,
                     (M[0][2] * M[1][0] - M[0][0] * M[1][2]) * inv_det],
                    [(M[1][0] * M[2][1] - M[1][1] * M[2][0]) * inv_det,
                     (M[0][1] * M[2][0] - M[0][0] * M[2][1]) * inv_det,
                     (M[0][0] * M[1][1] - M[0][1] * M[1][0]) * inv_det]
                ]

            def mat_mul(A, B):
                C = [[0,0,0],[0,0,0],[0,0,0]]
                for i in range(3):
                    for j in range(3):
                        for k in range(3):
                            C[i][j] += A[i][k] * B[k][j]
                return C

            # mat_S: columns are sky vectors
            mat_S = [[S[j][i] for j in range(3)] for i in range(3)]
            # mat_E: columns are mount vectors
            mat_E = [[E[j][i] for j in range(3)] for i in range(3)]
            
            inv_S = invert_3x3(mat_S)
            if inv_S:
                self.matrix = mat_mul(mat_E, inv_S)
                self.inv_matrix = invert_3x3(self.matrix)
        except Exception:
            self.matrix = None
            self.inv_matrix = None

    def transform_to_mount(self, sky_vec):
        """Applies transformation to a sky vector to get mount vector."""
        if self.matrix is None: return sky_vec
        res = [0, 0, 0]
        for i in range(3):
            for j in range(3):
                res[i] += self.matrix[i][j] * sky_vec[j]
        return res

    def transform_to_sky(self, mount_vec):
        """Applies inverse transformation to a mount vector to get sky vector."""
        if self.inv_matrix is None: return mount_vec
        res = [0, 0, 0]
        for i in range(3):
            for j in range(3):
                res[i] += self.inv_matrix[i][j] * mount_vec[j]
        return res
