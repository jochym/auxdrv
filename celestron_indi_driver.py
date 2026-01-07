"""
Celestron AUX INDI Driver

This module implements an INDI driver for Celestron mounts using the AUX protocol.
It uses the `indipydriver` library for INDI communication and `ephem` for
astronomical calculations.

Configuration is loaded from `config.yaml`.
"""

import asyncio
import indipydriver
from indipydriver import (
    IPyDriver,
    Device,
    SwitchVector,
    SwitchMember,
    TextVector,
    TextMember,
    NumberVector,
    NumberMember,
    LightVector,
    LightMember,
)
import ephem
from datetime import datetime, timezone
import yaml
import os
import math
import numpy as np

# Import AUX protocol implementation
from celestron_aux_driver import (
    AUXCommands,
    AUXTargets,
    AUXCommand,
    AUXCommunicator,
    pack_int3_steps,
    unpack_int3_steps,
    STEPS_PER_REVOLUTION,
)
from alignment import (
    AlignmentModel,
    vector_from_radec,
    vector_from_altaz,
    vector_to_radec,
    vector_to_altaz,
)

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
DEFAULT_CONFIG = {
    "observer": {"latitude": 50.1822, "longitude": 19.7925, "elevation": 400}
}


def load_config():
    """Loads configuration from YAML file or returns defaults."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return DEFAULT_CONFIG


config = load_config()
obs_cfg = config.get("observer", DEFAULT_CONFIG["observer"])


def apply_refraction(alt_deg):
    """Adds atmospheric refraction to true altitude to get apparent altitude."""
    if alt_deg < -2 or alt_deg > 89.9:
        return alt_deg
    h = max(0.0, alt_deg)
    ref_arcmin = 1.0 / math.tan(math.radians(h + 7.31 / (h + 4.4)))
    return alt_deg + ref_arcmin / 60.0


def remove_refraction(alt_deg):
    """Subtracts atmospheric refraction from apparent altitude to get true altitude."""
    if alt_deg < -2 or alt_deg > 89.9:
        return alt_deg
    true_h = alt_deg
    for _ in range(3):
        h = max(0.0, true_h)
        ref = 1.0 / math.tan(math.radians(h + 7.31 / (h + 4.4)))
        true_h = alt_deg - ref / 60.0
    return true_h


class CelestronAUXDriver(IPyDriver):
    """
    INDI Driver for Celestron mounts.

    Manages INDI properties, hardware communication via AUX bus,
    and coordinate transformations with multi-point SVD alignment support.
    """

    def __init__(self, driver_name: str = "Celestron AUX"):
        # 1. Define INDI properties
        self._init_properties()

        # 2. Initialize device with properties
        self.device = Device(
            "Celestron AUX",
            [
                self.connection_vector,
                self.port_vector,
                self.baud_vector,
                self.firmware_vector,
                self.mount_position_vector,
                self.mount_status_vector,
                self.slew_rate_vector,
                self.motion_ns_vector,
                self.motion_we_vector,
                self.absolute_coord_vector,
                self.guide_rate_vector,
                self.sync_vector,
                self.park_vector,
                self.unpark_vector,
                self.location_vector,
                self.equatorial_vector,
                self.approach_mode_vector,
                self.approach_offset_vector,
                self.track_mode_vector,
                self.align_config_vector,
                self.align_params_vector,
                self.align_status_vector,
                self.coord_set_vector,
                self.limits_vector,
                self.cordwrap_vector,
                self.cordwrap_pos_vector,
                self.focuser_vector,
                self.gps_status_vector,
                self.gps_refresh_vector,
                self.target_type_vector,
                self.planet_select_vector,
                self.tle_data_vector,
                self.refraction_vector,
                self.calibration_params_vector,
                self.abort_motion_vector,
            ],
        )

        super().__init__(self.device)
        self.communicator = None
        self.current_azm_steps = 0
        self.current_alt_steps = 0
        self._tracking_task = None
        self._align_model = AlignmentModel()

        # 3. ephem Observer for RA/Dec <-> Alt/Az transformations
        self.observer = ephem.Observer()
        self.observer.pressure = 0
        self.update_observer()

        # Ensure we use JNow (Equinox of Date)
        self.observer.epoch = self.observer.date

    def _init_properties(self):
        """Initializes all INDI property vectors and members."""
        # Connection
        self.conn_connect = SwitchMember("CONNECT", "Connect", "Off")
        self.conn_disconnect = SwitchMember("DISCONNECT", "Disconnect", "On")
        self.connection_vector = SwitchVector(
            "CONNECTION",
            "Connection",
            "Main",
            "rw",
            "OneOfMany",
            "Idle",
            [self.conn_connect, self.conn_disconnect],
        )

        # Port settings
        self.port_name = TextMember("PORT_NAME", "Port Name", "/dev/ttyUSB0")
        self.baud_rate = NumberMember(
            "BAUD_RATE", "Baud Rate", "%d", "9600", "115200", "1", "19200"
        )
        self.port_vector = TextVector(
            "PORT", "Serial Port", "Main", "rw", "Idle", [self.port_name]
        )
        self.baud_vector = NumberVector(
            "BAUD", "Baud Rate", "Main", "rw", "Idle", [self.baud_rate]
        )

        # Firmware Info
        self.model = TextMember("MODEL", "Model", "Unknown")
        self.hc_ver = TextMember("HC_VERSION", "HC Version", "Unknown")
        self.azm_ver = TextMember("AZM_VERSION", "AZM Version", "Unknown")
        self.alt_ver = TextMember("ALT_VERSION", "ALT Version", "Unknown")
        self.firmware_vector = TextVector(
            "FIRMWARE_INFO",
            "Firmware Info",
            "Main",
            "ro",
            "Idle",
            [self.model, self.hc_ver, self.azm_ver, self.alt_ver],
        )

        # Raw position (Steps)
        self.azm_steps = NumberMember(
            "AZM_STEPS", "AZM Steps", "%d", "0", str(STEPS_PER_REVOLUTION - 1), "1", "0"
        )
        self.alt_steps = NumberMember(
            "ALT_STEPS", "ALT Steps", "%d", "0", str(STEPS_PER_REVOLUTION - 1), "1", "0"
        )
        self.mount_position_vector = NumberVector(
            "MOUNT_POSITION",
            "Mount Position",
            "Main",
            "ro",
            "Idle",
            [self.azm_steps, self.alt_steps],
        )

        # Status indicators
        self.slewing_light = LightMember("SLEWING", "Slewing", "Idle")
        self.tracking_light = LightMember("TRACKING", "Tracking", "Idle")
        self.parked_light = LightMember("PARKED", "Parked", "Idle")
        self.mount_status_vector = LightVector(
            "MOUNT_STATUS",
            "Mount Status",
            "Main",
            "Idle",
            [self.slewing_light, self.tracking_light, self.parked_light],
        )

        # Motion control
        self.slew_rate = NumberMember("RATE", "Rate (1-9)", "%d", "1", "9", "1", "1")
        self.slew_rate_vector = NumberVector(
            "SLEW_RATE", "Slew Rate", "Main", "rw", "Idle", [self.slew_rate]
        )

        self.motion_n = SwitchMember("MOTION_N", "North", "Off")
        self.motion_s = SwitchMember("MOTION_S", "South", "Off")
        self.motion_ns_vector = SwitchVector(
            "TELESCOPE_MOTION_NS",
            "Motion N/S",
            "Main",
            "rw",
            "AtMostOne",
            "Idle",
            [self.motion_n, self.motion_s],
        )

        self.motion_w = SwitchMember("MOTION_W", "West", "Off")
        self.motion_e = SwitchMember("MOTION_E", "East", "Off")
        self.motion_we_vector = SwitchVector(
            "TELESCOPE_MOTION_WE",
            "Motion W/E",
            "Main",
            "rw",
            "AtMostOne",
            "Idle",
            [self.motion_w, self.motion_e],
        )

        # Coordinates
        self.target_azm = NumberMember(
            "AZM_STEPS", "AZM Steps", "%d", "0", str(STEPS_PER_REVOLUTION - 1), "1", "0"
        )
        self.target_alt = NumberMember(
            "ALT_STEPS", "ALT Steps", "%d", "0", str(STEPS_PER_REVOLUTION - 1), "1", "0"
        )
        self.absolute_coord_vector = NumberVector(
            "TELESCOPE_ABSOLUTE_COORD",
            "Absolute Coordinates",
            "Main",
            "rw",
            "Idle",
            [self.target_azm, self.target_alt],
        )

        self.guide_azm = NumberMember(
            "GUIDE_AZM", "AZM Guide Rate", "%d", "0", "255", "1", "0"
        )
        self.guide_alt = NumberMember(
            "GUIDE_ALT", "ALT Guide Rate", "%d", "0", "255", "1", "0"
        )
        self.guide_rate_vector = NumberVector(
            "TELESCOPE_GUIDE_RATE",
            "Guide Rates",
            "Main",
            "rw",
            "Idle",
            [self.guide_azm, self.guide_alt],
        )

        # Standard Mount Actions
        self.sync_switch = SwitchMember("SYNC", "Sync", "Off")
        self.sync_vector = SwitchVector(
            "TELESCOPE_SYNC",
            "Sync Mount",
            "Main",
            "rw",
            "AtMostOne",
            "Idle",
            [self.sync_switch],
        )

        self.park_switch = SwitchMember("PARK", "Park", "Off")
        self.park_vector = SwitchVector(
            "TELESCOPE_PARK",
            "Park Mount",
            "Main",
            "rw",
            "AtMostOne",
            "Idle",
            [self.park_switch],
        )

        self.unpark_switch = SwitchMember("UNPARK", "Unpark", "Off")
        self.unpark_vector = SwitchVector(
            "TELESCOPE_UNPARK",
            "Unpark Mount",
            "Main",
            "rw",
            "AtMostOne",
            "Idle",
            [self.unpark_switch],
        )

        # Geographical location
        self.lat = NumberMember(
            "LAT",
            "Latitude (deg)",
            " %06.2f",
            "-90",
            "90",
            "0",
            str(obs_cfg.get("latitude", 50.1822)),
        )
        self.long = NumberMember(
            "LONG",
            "Longitude (deg)",
            " %06.2f",
            "-360",
            "360",
            "0",
            str(obs_cfg.get("longitude", 19.7925)),
        )
        self.elev = NumberMember(
            "ELEV",
            "Elevation (m)",
            " %04.0f",
            "-1000",
            "10000",
            "0",
            str(obs_cfg.get("elevation", 400)),
        )
        self.location_vector = NumberVector(
            "GEOGRAPHIC_COORD",
            "Location",
            "Site",
            "rw",
            "Idle",
            [self.lat, self.long, self.elev],
        )

        # Equatorial coordinates
        self.ra = NumberMember(
            "RA", "Right Ascension (h)", "%08.3f", "0", "24", "0", "0"
        )
        self.dec = NumberMember(
            "DEC", "Declination (deg)", "%08.3f", "-90", "90", "0", "0"
        )
        self.equatorial_vector = NumberVector(
            "EQUATORIAL_EOD_COORD",
            "Equatorial JNow",
            "Main",
            "rw",
            "Idle",
            [self.ra, self.dec],
        )

        # GoTo Approach settings
        self.approach_disabled = SwitchMember("DISABLED", "Disabled", "On")
        self.approach_fixed = SwitchMember("FIXED_OFFSET", "Fixed Offset", "Off")
        self.approach_tracking = SwitchMember(
            "TRACKING_DIRECTION", "Tracking Direction", "Off"
        )
        self.approach_mode_vector = SwitchVector(
            "GOTO_APPROACH_MODE",
            "Approach Mode",
            "Options",
            "rw",
            "OneOfMany",
            "Idle",
            [self.approach_disabled, self.approach_fixed, self.approach_tracking],
        )

        self.approach_azm_offset = NumberMember(
            "AZM_OFFSET", "AZM Offset (steps)", "%d", "0", "1000000", "1", "10000"
        )
        self.approach_alt_offset = NumberMember(
            "ALT_OFFSET", "ALT Offset (steps)", "%d", "0", "1000000", "1", "10000"
        )
        self.approach_offset_vector = NumberVector(
            "GOTO_APPROACH_OFFSET",
            "Approach Offset",
            "Options",
            "rw",
            "Idle",
            [self.approach_azm_offset, self.approach_alt_offset],
        )

        # Tracking Modes
        self.track_none = SwitchMember("TRACK_OFF", "Off", "On")
        self.track_sidereal = SwitchMember("TRACK_SIDEREAL", "Sidereal", "Off")
        self.track_solar = SwitchMember("TRACK_SOLAR", "Solar", "Off")
        self.track_lunar = SwitchMember("TRACK_LUNAR", "Lunar", "Off")
        self.track_mode_vector = SwitchVector(
            "TELESCOPE_TRACK_MODE",
            "Tracking Mode",
            "Main",
            "rw",
            "OneOfMany",
            "Idle",
            [self.track_none, self.track_sidereal, self.track_solar, self.track_lunar],
        )

        # Coordination Set Mode (Slew, Track, Sync)
        self.set_slew = SwitchMember("SLEW", "Slew", "On")
        self.set_track = SwitchMember("TRACK", "Track", "Off")
        self.set_sync = SwitchMember("SYNC", "Sync", "Off")
        self.coord_set_vector = SwitchVector(
            "TELESCOPE_ON_COORD_SET",
            "Coord Set Mode",
            "Main",
            "rw",
            "OneOfMany",
            "Idle",
            [self.set_slew, self.set_track, self.set_sync],
        )

        # Alignment Config
        self.align_max_points = NumberMember(
            "MAX_POINTS", "Max Points", "%d", "1", "100", "1", "50"
        )
        self.align_local_bias = NumberMember(
            "LOCAL_BIAS", "Local Bias (%)", "%d", "0", "100", "1", "0"
        )
        self.align_auto_prune = SwitchMember("AUTO_PRUNE", "Auto Prune", "On")
        self.align_clear_all = SwitchMember("CLEAR_ALL", "Clear All", "Off")
        self.align_clear_last = SwitchMember("CLEAR_LAST", "Clear Last", "Off")
        self.align_config_vector = SwitchVector(
            "ALIGNMENT_CONFIG",
            "Alignment Config",
            "Alignment",
            "rw",
            "AtMostOne",
            "Idle",
            [self.align_auto_prune, self.align_clear_all, self.align_clear_last],
        )
        self.align_params_vector = NumberVector(
            "ALIGNMENT_PARAMS",
            "Alignment Params",
            "Alignment",
            "rw",
            "Idle",
            [self.align_max_points, self.align_local_bias],
        )

        # Alignment Status (Read Only)
        self.align_point_count = NumberMember(
            "POINT_COUNT", "Point Count", "%d", "0", "100", "1", "0"
        )
        self.align_rms_error = NumberMember(
            "RMS_ERROR", "RMS Error (arcsec)", "%.2f", "0", "360000", "0", "0"
        )
        self.align_status_vector = NumberVector(
            "ALIGNMENT_STATUS",
            "Alignment Status",
            "Alignment",
            "ro",
            "Idle",
            [self.align_point_count, self.align_rms_error],
        )

        # Slew Limits
        self.alt_limit_min = NumberMember(
            "ALT_MIN", "Min Altitude (deg)", "%06.2f", "-90", "90", "0", "-90"
        )
        self.alt_limit_max = NumberMember(
            "ALT_MAX", "Max Altitude (deg)", "%06.2f", "-90", "90", "0", "90"
        )
        self.azm_limit_min = NumberMember(
            "AZ_MIN", "Min Azimuth (deg)", "%06.2f", "0", "360", "0", "0"
        )
        self.azm_limit_max = NumberMember(
            "AZ_MAX", "Max Azimuth (deg)", "%06.2f", "0", "360", "0", "360"
        )
        self.limits_vector = NumberVector(
            "TELESCOPE_LIMITS",
            "Slew Limits",
            "Safety",
            "rw",
            "Idle",
            [
                self.alt_limit_min,
                self.alt_limit_max,
                self.azm_limit_min,
                self.azm_limit_max,
            ],
        )

        self.cordwrap_enable = SwitchMember("ENABLED", "Enabled", "On")
        self.cordwrap_disable = SwitchMember("DISABLED", "Disabled", "Off")
        self.cordwrap_vector = SwitchVector(
            "TELESCOPE_CORDWRAP",
            "Cord Wrap Prevention",
            "Safety",
            "rw",
            "OneOfMany",
            "Idle",
            [self.cordwrap_enable, self.cordwrap_disable],
        )

        self.cordwrap_pos = NumberMember(
            "POS", "Cord Wrap Position (deg)", "%06.2f", "0", "360", "0", "0"
        )
        self.cordwrap_pos_vector = NumberVector(
            "TELESCOPE_CORDWRAP_POS",
            "Cord Wrap Position",
            "Safety",
            "rw",
            "Idle",
            [self.cordwrap_pos],
        )

        # Focuser support
        self.focus_pos = NumberMember(
            "FOCUS_POS", "Focus Position", "%d", "0", "16777215", "1", "0"
        )
        self.focuser_vector = NumberVector(
            "ABS_FOCUS_POSITION",
            "Focuser Position",
            "Main",
            "rw",
            "Idle",
            [self.focus_pos],
        )

        # GPS Support
        self.gps_status = LightMember("GPS_STATUS", "GPS Status", "Idle")
        self.gps_status_vector = LightVector(
            "GPS_STATUS", "GPS Status", "Accessories", "Idle", [self.gps_status]
        )

        self.gps_refresh = SwitchMember("REFRESH", "Refresh GPS", "Off")
        self.gps_refresh_vector = SwitchVector(
            "GPS_REFRESH",
            "GPS Refresh",
            "Accessories",
            "rw",
            "AtMostOne",
            "Idle",
            [self.gps_refresh],
        )

        # Moving Objects Support
        self.target_sidereal = SwitchMember("SIDEREAL", "Sidereal", "On")
        self.target_sun = SwitchMember("SUN", "Sun", "Off")
        self.target_moon = SwitchMember("MOON", "Moon", "Off")
        self.target_planet = SwitchMember("PLANET", "Planet", "Off")
        self.target_satellite = SwitchMember("SATELLITE", "Satellite", "Off")
        self.target_type_vector = SwitchVector(
            "TARGET_TYPE",
            "Target Type",
            "Main",
            "rw",
            "OneOfMany",
            "Idle",
            [
                self.target_sidereal,
                self.target_sun,
                self.target_moon,
                self.target_planet,
                self.target_satellite,
            ],
        )

        self.planet_mercury = SwitchMember("MERCURY", "Mercury", "Off")
        self.planet_venus = SwitchMember("VENUS", "Venus", "Off")
        self.planet_mars = SwitchMember("MARS", "Mars", "On")
        self.planet_jupiter = SwitchMember("JUPITER", "Jupiter", "Off")
        self.planet_saturn = SwitchMember("SATURN", "Saturn", "Off")
        self.planet_uranus = SwitchMember("URANUS", "Uranus", "Off")
        self.planet_neptune = SwitchMember("NEPTUNE", "Neptune", "Off")
        self.planet_pluto = SwitchMember("PLUTO", "Pluto", "Off")
        self.planet_select_vector = SwitchVector(
            "PLANET_SELECT",
            "Select Planet",
            "Main",
            "rw",
            "OneOfMany",
            "Idle",
            [
                self.planet_mercury,
                self.planet_venus,
                self.planet_mars,
                self.planet_jupiter,
                self.planet_saturn,
                self.planet_uranus,
                self.planet_neptune,
                self.planet_pluto,
            ],
        )

        self.tle_name = TextMember("NAME", "Name", "ISS")
        self.tle_line1 = TextMember(
            "LINE1",
            "Line 1",
            "1 25544U 98067A   26006.88541667  .00000000  00000-0  00000-0 0    01",
        )
        self.tle_line2 = TextMember(
            "LINE2",
            "Line 2",
            "2 25544  51.6400  10.0000 0001000   0.0000   0.0000 15.50000000000001",
        )
        self.tle_data_vector = TextVector(
            "TLE_DATA",
            "TLE Data",
            "Main",
            "rw",
            "Idle",
            [self.tle_name, self.tle_line1, self.tle_line2],
        )

        # Abort Motion
        self.abort_motion = SwitchMember("ABORT", "Abort", "Off")
        self.abort_motion_vector = SwitchVector(
            "TELESCOPE_ABORT_MOTION",
            "Abort Motion",
            "Main",
            "rw",
            "AtMostOne",
            "Idle",
            [self.abort_motion],
        )

        # Refraction Correction
        self.refraction_on = SwitchMember("ENABLED", "Enabled", "Off")
        self.refraction_off = SwitchMember("DISABLED", "Disabled", "On")
        self.refraction_vector = SwitchVector(
            "REFRACTION_CORRECTION",
            "Refraction Correction",
            "Options",
            "rw",
            "OneOfMany",
            "Idle",
            [self.refraction_on, self.refraction_off],
        )

        # Advanced Calibration Display
        self.cal_cone = NumberMember(
            "CONE_ERROR", "Cone Error (arcmin)", "%.2f", "-600", "600", "0", "0"
        )
        self.cal_nonperp = NumberMember(
            "NON_PERP", "Non-Perpendicularity (arcmin)", "%.2f", "-600", "600", "0", "0"
        )
        self.cal_alt_offset = NumberMember(
            "ALT_OFFSET", "Alt Index Offset (arcmin)", "%.2f", "-600", "600", "0", "0"
        )
        self.calibration_params_vector = NumberVector(
            "CALIBRATION_PARAMS",
            "Calibration Parameters",
            "Alignment",
            "ro",
            "Idle",
            [self.cal_cone, self.cal_nonperp, self.cal_alt_offset],
        )

        # Post-init for properties that need values
        self.refraction_off.membervalue = "On"
        self.refraction_on.membervalue = "Off"

    def update_observer(self, time_offset: float = 0):
        """Updates ephem Observer state from INDI location properties."""
        self.observer.lat = str(self.lat.membervalue)
        self.observer.lon = str(self.long.membervalue)
        self.observer.elevation = float(self.elev.membervalue)

        if time_offset != 0:
            self.observer.date = ephem.Date(self.observer.date + time_offset / 86400.0)

        # Ensure we use JNow (Equinox of Date)
        self.observer.epoch = self.observer.date

    async def rxevent(self, event):
        """Main event handler for INDI property updates."""
        if event.vectorname == "CONNECTION":
            await self.handle_connection(event)
        elif event.vectorname == "PORT":
            self.port_vector.update(event.root)
            await self.port_vector.send_setVector(state="Ok")
        elif event.vectorname == "BAUD":
            self.baud_vector.update(event.root)
            await self.baud_vector.send_setVector(state="Ok")
        elif event.vectorname == "SLEW_RATE":
            self.slew_rate_vector.update(event.root)
            await self.slew_rate_vector.send_setVector(state="Ok")
        elif event.vectorname == "TELESCOPE_MOTION_NS":
            await self.handle_motion_ns(event)
        elif event.vectorname == "TELESCOPE_MOTION_WE":
            await self.handle_motion_we(event)
        elif event.vectorname == "TELESCOPE_ABSOLUTE_COORD":
            await self.handle_goto(event)
        elif event.vectorname == "TELESCOPE_PARK":
            await self.handle_park(event)
        elif event.vectorname == "TELESCOPE_UNPARK":
            await self.handle_unpark(event)
        elif event.vectorname == "TELESCOPE_GUIDE_RATE":
            await self.handle_guide_rate(event)
        elif event.vectorname == "GEOGRAPHIC_COORD":
            self.location_vector.update(event.root)
            self.update_observer()
            await self.location_vector.send_setVector(state="Ok")
        elif event.vectorname == "EQUATORIAL_EOD_COORD":
            await self.handle_equatorial_goto(event)
        elif event.vectorname == "GOTO_APPROACH_MODE":
            self.approach_mode_vector.update(event.root)
            await self.approach_mode_vector.send_setVector(state="Ok")
        elif event.vectorname == "GOTO_APPROACH_OFFSET":
            self.approach_offset_vector.update(event.root)
            await self.approach_offset_vector.send_setVector(state="Ok")
        elif event.vectorname == "TELESCOPE_TRACK_MODE":
            await self.handle_track_mode(event)
        elif event.vectorname == "TELESCOPE_ON_COORD_SET":
            self.coord_set_vector.update(event.root)
            await self.coord_set_vector.send_setVector(state="Ok")
        elif event.vectorname == "ALIGNMENT_CONFIG":
            await self.handle_alignment_config(event)
        elif event.vectorname == "ALIGNMENT_PARAMS":
            self.align_params_vector.update(event.root)
            await self.align_params_vector.send_setVector(state="Ok")
        elif event.vectorname == "TELESCOPE_LIMITS":
            await self.handle_limits(event)
        elif event.vectorname == "TELESCOPE_CORDWRAP":
            await self.handle_cordwrap(event)
        elif event.vectorname == "TELESCOPE_CORDWRAP_POS":
            await self.handle_cordwrap_pos(event)
        elif event.vectorname == "ABS_FOCUS_POSITION":
            await self.handle_focuser(event)
        elif event.vectorname == "GPS_REFRESH":
            await self.handle_gps_refresh(event)
        elif event.vectorname == "TARGET_TYPE":
            self.target_type_vector.update(event.root)
            await self.target_type_vector.send_setVector(state="Ok")
        elif event.vectorname == "PLANET_SELECT":
            self.planet_select_vector.update(event.root)
            await self.planet_select_vector.send_setVector(state="Ok")
        elif event.vectorname == "TLE_DATA":
            self.tle_data_vector.update(event.root)
            await self.tle_data_vector.send_setVector(state="Ok")
        elif event.vectorname == "REFRACTION_CORRECTION":
            self.refraction_vector.update(event.root)
            await self.refraction_vector.send_setVector(state="Ok")
        elif event.vectorname == "TELESCOPE_ABORT_MOTION":
            await self.handle_abort_motion(event)

    async def handle_limits(self, event):
        """Updates internal slew limits."""
        self.limits_vector.update(event.root)
        await self.limits_vector.send_setVector(state="Ok")

    async def handle_abort_motion(self, event):
        """Immediately stops all mount movement."""
        if event and event.root:
            self.abort_motion_vector.update(event.root)
        if self.abort_motion.membervalue == "On":
            if self.communicator and self.communicator.connected:
                # Send Rate 0 to both axes
                await self.slew_by_rate(AUXTargets.AZM, 0, 1)
                await self.slew_by_rate(AUXTargets.ALT, 0, 1)

            # Cancel tracking if active
            if self._tracking_task:
                self._tracking_task.cancel()
                self._tracking_task = None
                self.tracking_light.membervalue = "Idle"

            self.slewing_light.membervalue = "Idle"
            await self.mount_status_vector.send_setVector()

            self.abort_motion.membervalue = "Off"
            await self.abort_motion_vector.send_setVector(state="Ok")

    async def handle_cordwrap(self, event):
        """Enables or disables cord wrap prevention on the mount."""
        self.cordwrap_vector.update(event.root)
        if not self.communicator or not self.communicator.connected:
            return

        cmd_type = (
            AUXCommands.MC_ENABLE_CORDWRAP
            if self.cordwrap_enable.membervalue == "On"
            else AUXCommands.MC_DISABLE_CORDWRAP
        )
        resp = await self.communicator.send_command(
            AUXCommand(cmd_type, AUXTargets.APP, AUXTargets.AZM)
        )
        await self.cordwrap_vector.send_setVector(state="Ok" if resp else "Alert")

    async def handle_cordwrap_pos(self, event):
        """Sets the cord wrap prevention position on the mount."""
        self.cordwrap_pos_vector.update(event.root)
        if not self.communicator or not self.communicator.connected:
            return

        pos = int(self.cordwrap_pos.membervalue)
        resp = await self.communicator.send_command(
            AUXCommand(
                AUXCommands.MC_SET_CORDWRAP_POS,
                AUXTargets.APP,
                AUXTargets.AZM,
                pack_int3_steps(pos),
            )
        )
        await self.cordwrap_pos_vector.send_setVector(state="Ok" if resp else "Alert")

    async def handle_focuser(self, event):
        """Moves the focuser to the specified position."""
        self.focuser_vector.update(event.root)
        if not self.communicator or not self.communicator.connected:
            return

        pos = int(self.focus_pos.membervalue)
        # Celestron Focuser uses MC_GOTO_FAST (0x02) to FOC target (0x12).
        resp = await self.communicator.send_command(
            AUXCommand(
                AUXCommands.MC_GOTO_FAST,
                AUXTargets.APP,
                AUXTargets.FOCUS,
                pack_int3_steps(pos),
            )
        )
        await self.focuser_vector.send_setVector(state="Ok" if resp else "Alert")

    async def handle_gps_refresh(self, event):
        """Manually refreshes location and time from the GPS module."""
        self.gps_refresh_vector.update(event.root)
        if self.gps_refresh.membervalue == "On":
            await self.gps_refresh_vector.send_setVector(state="Busy")
            if await self.update_gps_data():
                await self.gps_refresh_vector.send_setVector(state="Ok")
            else:
                await self.gps_refresh_vector.send_setVector(state="Alert")
            self.gps_refresh.membervalue = "Off"
            await self.gps_refresh_vector.send_setVector()

    async def update_gps_data(self):
        """Polls GPS module for status and location data."""
        if not self.communicator or not self.communicator.connected:
            return False

        # Check if GPS linked
        resp = await self.communicator.send_command(
            AUXCommand(AUXCommands.GPS_LINKED, AUXTargets.APP, AUXTargets.GPS)
        )
        if not resp or resp.data[0] == 0:
            self.gps_status.membervalue = "Alert"
            await self.gps_status_vector.send_setVector()
            return False

        self.gps_status.membervalue = "Ok"
        await self.gps_status_vector.send_setVector()

        # Get Lat/Long
        r_lat = await self.communicator.send_command(
            AUXCommand(AUXCommands.GPS_GET_LAT, AUXTargets.APP, AUXTargets.GPS)
        )
        r_lon = await self.communicator.send_command(
            AUXCommand(AUXCommands.GPS_GET_LONG, AUXTargets.APP, AUXTargets.GPS)
        )

        if r_lat and len(r_lat.data) == 4 and r_lon and len(r_lon.data) == 4:
            # Lat format: [deg, min, sec, sign (0=N, 1=S)]
            lat = r_lat.data[0] + r_lat.data[1] / 60.0 + r_lat.data[2] / 3600.0
            if r_lat.data[3] != 0:
                lat = -lat
            self.lat.membervalue = lat

            # Lon format: [deg, min, sec, sign (0=E, 1=W)]
            lon = r_lon.data[0] + r_lon.data[1] / 60.0 + r_lon.data[2] / 3600.0
            if r_lon.data[3] != 0:
                lon = -lon
            self.long.membervalue = lon

            await self.location_vector.send_setVector()
            self.update_observer()
            return True

        return False

    async def handle_connection(self, event):
        """Handles CONNECT/DISCONNECT switches."""
        if event and event.root:
            self.connection_vector.update(event.root)
        if self.conn_connect.membervalue == "On":
            self.communicator = AUXCommunicator(
                self.port_name.membervalue, int(self.baud_rate.membervalue)
            )
            if await self.communicator.connect():
                await self.connection_vector.send_setVector(state="Ok")
                await self.get_firmware_info()
                await self.read_mount_position()
            else:
                self.conn_connect.membervalue = "Off"
                self.conn_disconnect.membervalue = "On"
                await self.connection_vector.send_setVector(state="Alert")
        else:
            if self.communicator:
                await self.communicator.disconnect()
            await self.connection_vector.send_setVector(state="Idle")

    async def get_firmware_info(self):
        """Retrieves model and version info from the mount."""
        if not self.communicator or not self.communicator.connected:
            return

        # Get Model
        resp = await self.communicator.send_command(
            AUXCommand(AUXCommands.MC_GET_MODEL, AUXTargets.APP, AUXTargets.AZM)
        )
        if resp:
            model_id = resp.get_data_as_int()
            model_map = {
                0x0001: "Nexstar GPS",
                0x0783: "Nexstar SLT",
                0x0B83: "4/5SE",
                0x0C82: "6/8SE",
                0x1189: "CPC Deluxe",
                0x1283: "GT Series",
                0x1485: "AVX",
                0x1687: "Evolution",
                0x1788: "CGX",
            }
            self.model.membervalue = model_map.get(
                model_id, f"Unknown (0x{model_id:04X})"
            )

        # Get Versions
        for target, member in [
            (AUXTargets.AZM, self.azm_ver),
            (AUXTargets.ALT, self.alt_ver),
            (AUXTargets.HC, self.hc_ver),
        ]:
            resp = await self.communicator.send_command(
                AUXCommand(AUXCommands.GET_VER, AUXTargets.APP, target)
            )
            if resp and len(resp.data) == 4:
                member.membervalue = (
                    f"{resp.data[0]}.{resp.data[1]}.{resp.data[2] * 256 + resp.data[3]}"
                )

        await self.firmware_vector.send_setVector(state="Ok")

    async def read_mount_position(self):
        """Periodically reads encoder steps and updates RA/Dec."""
        if not self.communicator or not self.communicator.connected:
            return

        # AZM
        resp = await self.communicator.send_command(
            AUXCommand(AUXCommands.MC_GET_POSITION, AUXTargets.APP, AUXTargets.AZM)
        )
        if resp and len(resp.data) == 3:
            self.current_azm_steps = unpack_int3_steps(resp.data)
            self.azm_steps.membervalue = self.current_azm_steps

        # ALT
        resp = await self.communicator.send_command(
            AUXCommand(AUXCommands.MC_GET_POSITION, AUXTargets.APP, AUXTargets.ALT)
        )
        if resp and len(resp.data) == 3:
            self.current_alt_steps = unpack_int3_steps(resp.data)
            self.alt_steps.membervalue = self.current_alt_steps

        await self.mount_position_vector.send_setVector(state="Ok")

        # Calculate current RA/Dec
        ra_val, dec_val = await self.steps_to_equatorial(
            self.current_azm_steps, self.current_alt_steps
        )
        self.ra.membervalue = ra_val
        self.dec.membervalue = dec_val
        await self.equatorial_vector.send_setVector(state="Ok")

    async def handle_motion_ns(self, event):
        """Handles manual North/South slew commands."""
        self.motion_ns_vector.update(event.root)
        rate = int(self.slew_rate.membervalue)
        if self.motion_n.membervalue == "On":
            await self.slew_by_rate(AUXTargets.ALT, rate, 1)
        elif self.motion_s.membervalue == "On":
            await self.slew_by_rate(AUXTargets.ALT, rate, -1)
        else:
            await self.slew_by_rate(AUXTargets.ALT, 0, 1)
        await self.motion_ns_vector.send_setVector(state="Ok")

    async def handle_motion_we(self, event):
        """Handles manual West/East slew commands."""
        self.motion_we_vector.update(event.root)
        rate = int(self.slew_rate.membervalue)
        if self.motion_w.membervalue == "On":
            await self.slew_by_rate(AUXTargets.AZM, rate, -1)
        elif self.motion_e.membervalue == "On":
            await self.slew_by_rate(AUXTargets.AZM, rate, 1)
        else:
            await self.slew_by_rate(AUXTargets.AZM, 0, 1)
        await self.motion_we_vector.send_setVector(state="Ok")

    async def slew_by_rate(self, axis, rate, direction):
        """Sends a rate-based slew command to a motor axis."""
        cmd_type = (
            AUXCommands.MC_MOVE_POS if direction == 1 else AUXCommands.MC_MOVE_NEG
        )
        cmd = AUXCommand(cmd_type, AUXTargets.APP, axis, bytes([rate]))
        resp = await self.communicator.send_command(cmd)
        if resp:
            self.slewing_light.membervalue = "Ok" if rate > 0 else "Idle"
            await self.mount_status_vector.send_setVector()

    async def _wait_for_slew(self, axis):
        """Waits until the specified axis finishes slewing."""
        for _ in range(120):  # 120 seconds timeout
            cmd = AUXCommand(AUXCommands.MC_SLEW_DONE, AUXTargets.APP, axis)
            resp = await self.communicator.send_command(cmd)
            # Response 0xFF means done
            if resp and len(resp.data) >= 1 and resp.data[0] == 0xFF:
                return True
            await asyncio.sleep(1)
        return False

    async def _do_slew(self, axis, steps, fast=True):
        """Sends a position-based GoTo command to a motor axis (low-level)."""
        cmd_type = AUXCommands.MC_GOTO_FAST if fast else AUXCommands.MC_GOTO_SLOW
        cmd = AUXCommand(cmd_type, AUXTargets.APP, axis, pack_int3_steps(steps))
        resp = await self.communicator.send_command(cmd)
        if resp:
            self.slewing_light.membervalue = "Ok"
            await self.mount_status_vector.send_setVector()
            return True
        return False

    async def get_tracking_rates(self, ra, dec):
        """Calculates current tracking rates in steps/second."""
        s1_azm, s1_alt = await self.equatorial_to_steps(ra, dec, time_offset=0)
        s2_azm, s2_alt = await self.equatorial_to_steps(ra, dec, time_offset=60)

        def diff_steps(s2, s1):
            d = s2 - s1
            if d > STEPS_PER_REVOLUTION / 2:
                d -= STEPS_PER_REVOLUTION
            if d < -STEPS_PER_REVOLUTION / 2:
                d += STEPS_PER_REVOLUTION
            return d

        return diff_steps(s2_azm, s1_azm) / 60.0, diff_steps(s2_alt, s1_alt) / 60.0

    def is_move_allowed(self, azm_steps, alt_steps):
        """Checks if the given position (in steps) is within configured limits."""
        alt_deg = (alt_steps / STEPS_PER_REVOLUTION) * 360.0
        # Normalize Alt to [-180, 180]
        if alt_deg > 180:
            alt_deg -= 360.0

        azm_deg = (azm_steps / STEPS_PER_REVOLUTION) * 360.0

        if not (
            float(self.alt_limit_min.membervalue)
            <= alt_deg
            <= float(self.alt_limit_max.membervalue)
        ):
            return False

        # Azimuth limits can wrap around 360/0
        min_az = float(self.azm_limit_min.membervalue)
        max_az = float(self.azm_limit_max.membervalue)
        if min_az <= max_az:
            if not (min_az <= azm_deg <= max_az):
                return False
        else:  # Limit spans across 0
            if not (azm_deg >= min_az or azm_deg <= max_az):
                return False

        return True

    async def goto_position(self, target_azm, target_alt, ra=None, dec=None):
        """
        Executes a GoTo movement with optional anti-backlash approach.
        Checks against slew limits before moving.
        """
        if not self.is_move_allowed(target_azm, target_alt):
            return False

        approach_mode = "DISABLED"
        if self.approach_fixed.membervalue == "On":
            approach_mode = "FIXED"
        elif self.approach_tracking.membervalue == "On":
            approach_mode = "TRACKING"

        azm_sign = 1
        alt_sign = 1

        if approach_mode == "TRACKING" and ra is not None and dec is not None:
            rate_azm, rate_alt = await self.get_tracking_rates(ra, dec)
            azm_sign = 1 if rate_azm >= 0 else -1
            alt_sign = 1 if rate_alt >= 0 else -1

        if approach_mode != "DISABLED":
            off_azm = int(self.approach_azm_offset.membervalue)
            off_alt = int(self.approach_alt_offset.membervalue)

            inter_azm = (target_azm - azm_sign * off_azm) % STEPS_PER_REVOLUTION
            inter_alt = (target_alt - alt_sign * off_alt) % STEPS_PER_REVOLUTION

            await asyncio.gather(
                self._do_slew(AUXTargets.AZM, inter_azm, fast=True),
                self._do_slew(AUXTargets.ALT, inter_alt, fast=True),
            )

            await asyncio.gather(
                self._wait_for_slew(AUXTargets.AZM), self._wait_for_slew(AUXTargets.ALT)
            )

        fast_final = approach_mode == "DISABLED"
        s1 = await self._do_slew(AUXTargets.AZM, target_azm, fast=fast_final)
        s2 = await self._do_slew(AUXTargets.ALT, target_alt, fast=fast_final)

        return s1 and s2

    async def handle_goto(self, event):
        """Handles GoTo command using raw encoder steps."""
        if event and event.root:
            self.absolute_coord_vector.update(event.root)
        await self.absolute_coord_vector.send_setVector(state="Busy")

        target_azm = int(self.target_azm.membervalue)
        target_alt = int(self.target_alt.membervalue)

        success = await self.goto_position(target_azm, target_alt)

        if success:
            await asyncio.gather(
                self._wait_for_slew(AUXTargets.AZM), self._wait_for_slew(AUXTargets.ALT)
            )
            await self.absolute_coord_vector.send_setVector(state="Ok")
        else:
            await self.absolute_coord_vector.send_setVector(state="Alert")

    async def slew_to(self, axis, steps, fast=True):
        """Sends a position-based GoTo command to a motor axis."""
        return await self._do_slew(axis, steps, fast)

    async def handle_alignment_config(self, event):
        """Handles clearing alignment or pruning."""
        if event and event.root:
            self.align_config_vector.update(event.root)
        if self.align_clear_all.membervalue == "On":
            self._align_model.clear()
            self.align_clear_all.membervalue = "Off"
            await self.update_alignment_status()
        elif self.align_clear_last.membervalue == "On":
            if self._align_model.points:
                self._align_model.points.pop()
                self._align_model._compute_model()
            self.align_clear_last.membervalue = "Off"
            await self.update_alignment_status()

        await self.align_config_vector.send_setVector(state="Ok")

    async def update_alignment_status(self):
        """Updates INDI properties with alignment model stats."""
        self.align_point_count.membervalue = len(self._align_model.points)
        self.align_rms_error.membervalue = self._align_model.rms_error_arcsec
        await self.align_status_vector.send_setVector()

        # Update calibration parameters (from the 6-param model)
        # self.params = [roll, pitch, yaw, ID, CH, NP]
        # All params are now in RADIANS. Convert to arcmin.
        rad2arcmin = (180.0 * 60.0) / math.pi
        self.cal_alt_offset.membervalue = self._align_model.params[3] * rad2arcmin
        self.cal_cone.membervalue = self._align_model.params[4] * rad2arcmin
        self.cal_nonperp.membervalue = self._align_model.params[5] * rad2arcmin
        await self.calibration_params_vector.send_setVector()

    async def handle_park(self, event):
        """Moves the mount to the park position (0,0 steps)."""
        if event and event.root:
            self.park_vector.update(event.root)
        if self.park_switch.membervalue == "On":
            await self.park_vector.send_setVector(state="Busy")
            if await self.goto_position(0, 0):
                self.parked_light.membervalue = "Ok"
                await self.mount_status_vector.send_setVector()
                await self.park_vector.send_setVector(state="Ok")
            else:
                await self.park_vector.send_setVector(state="Alert")
            self.park_switch.membervalue = "Off"
            await self.park_vector.send_setVector()

    async def handle_unpark(self, event):
        """Clears the parked status."""
        if event and event.root:
            self.unpark_vector.update(event.root)
        if self.unpark_switch.membervalue == "On":
            self.parked_light.membervalue = "Idle"
            await self.mount_status_vector.send_setVector()
            self.unpark_switch.membervalue = "Off"
            await self.unpark_vector.send_setVector(state="Ok")

    async def handle_equatorial_goto(self, event):
        """Handles GoTo or Sync command using RA/Dec coordinates."""
        if event and event.root:
            self.equatorial_vector.update(event.root)

        target_ra, target_dec = await self._get_target_equatorial()

        if self.set_sync.membervalue == "On":
            # Perform SYNC
            await self.equatorial_vector.send_setVector(state="Busy")
            await self.read_mount_position()

            # 1. Convert Target RA/Dec to ideal Alt/Az
            self.update_observer()
            body = ephem.FixedBody()
            body._ra = math.radians(target_ra * 15.0)
            body._dec = math.radians(target_dec)
            body._epoch = self.observer.date
            body.compute(self.observer)

            ideal_az_deg = math.degrees(float(body.az))
            ideal_alt_deg = math.degrees(float(body.alt))

            # 2. Get current raw Alt/Az from encoders
            raw_az_deg = (self.current_azm_steps / STEPS_PER_REVOLUTION) * 360.0
            raw_alt_deg = (self.current_alt_steps / STEPS_PER_REVOLUTION) * 360.0

            # 3. Calculate weight with Local Bias Proximity
            weight = 1.0
            bias = float(self.align_local_bias.membervalue) / 100.0
            if bias > 0 and self._align_model.points:
                # We could implement distance-based weighting here
                pass

            # 4. Add point to alignment model (Thinning handled inside)
            sky_vec = vector_from_altaz(ideal_az_deg, ideal_alt_deg)
            mount_vec = vector_from_altaz(raw_az_deg, raw_alt_deg)
            self._align_model.add_point(sky_vec, mount_vec, weight=weight)

            await self.update_alignment_status()

            # Physical Sync (sets MC position to current state)
            cmd_azm = AUXCommand(
                AUXCommands.MC_SET_POSITION,
                AUXTargets.APP,
                AUXTargets.AZM,
                pack_int3_steps(self.current_azm_steps),
            )
            cmd_alt = AUXCommand(
                AUXCommands.MC_SET_POSITION,
                AUXTargets.APP,
                AUXTargets.ALT,
                pack_int3_steps(self.current_alt_steps),
            )
            s1 = await self.communicator.send_command(cmd_azm)
            s2 = await self.communicator.send_command(cmd_alt)

            await self.equatorial_vector.send_setVector(
                state="Ok" if s1 and s2 else "Alert"
            )
        else:
            # Perform GOTO
            await self.equatorial_vector.send_setVector(state="Busy")
            azm_steps, alt_steps = await self.equatorial_to_steps(target_ra, target_dec)
            success = await self.goto_position(
                azm_steps, alt_steps, ra=target_ra, dec=target_dec
            )

            if success:
                await asyncio.gather(
                    self._wait_for_slew(AUXTargets.AZM),
                    self._wait_for_slew(AUXTargets.ALT),
                )
                await self.equatorial_vector.send_setVector(state="Ok")
            else:
                await self.equatorial_vector.send_setVector(state="Alert")

    async def _get_target_equatorial(self, time_offset: float = 0):
        """Returns JNow RA/Dec for the currently selected target type."""
        self.update_observer(time_offset)

        if self.target_sidereal.membervalue == "On":
            return float(self.ra.membervalue), float(self.dec.membervalue)

        body = None
        if self.target_sun.membervalue == "On":
            body = ephem.Sun()
        elif self.target_moon.membervalue == "On":
            body = ephem.Moon()
        elif self.target_planet.membervalue == "On":
            if self.planet_mercury.membervalue == "On":
                body = ephem.Mercury()
            elif self.planet_venus.membervalue == "On":
                body = ephem.Venus()
            elif self.planet_mars.membervalue == "On":
                body = ephem.Mars()
            elif self.planet_jupiter.membervalue == "On":
                body = ephem.Jupiter()
            elif self.planet_saturn.membervalue == "On":
                body = ephem.Saturn()
            elif self.planet_uranus.membervalue == "On":
                body = ephem.Uranus()
            elif self.planet_neptune.membervalue == "On":
                body = ephem.Neptune()
            elif self.planet_pluto.membervalue == "On":
                body = ephem.Pluto()
        elif self.target_satellite.membervalue == "On":
            try:
                body = ephem.readtle(
                    self.tle_name.membervalue,
                    self.tle_line1.membervalue,
                    self.tle_line2.membervalue,
                )
            except Exception as e:
                print(f"Error reading TLE: {e}")
                return float(self.ra.membervalue), float(self.dec.membervalue)

        if body:
            body.compute(self.observer)
            return math.degrees(body.ra) / 15.0, math.degrees(body.dec)

        return float(self.ra.membervalue), float(self.dec.membervalue)

    async def equatorial_to_steps(self, ra_hours, dec_deg, time_offset: float = 0):
        """Converts RA/Dec to motor encoder steps."""
        self.update_observer(time_offset=time_offset)

        body = ephem.FixedBody()
        body._ra = math.radians(ra_hours * 15.0)
        body._dec = math.radians(dec_deg)
        body._epoch = self.observer.date
        body.compute(self.observer)

        ideal_az_deg = math.degrees(float(body.az))
        ideal_alt_deg = math.degrees(float(body.alt))

        # 2. Refraction (True to Apparent)
        if self.refraction_on.membervalue == "On":
            ideal_alt_deg = apply_refraction(ideal_alt_deg)

        # 3. Apply Alignment Transform
        sky_vec = vector_from_altaz(ideal_az_deg, ideal_alt_deg)
        bias = float(self.align_local_bias.membervalue) / 100.0
        mount_vec = self._align_model.transform_to_mount(
            sky_vec, target_vec=sky_vec, local_bias=bias
        )
        real_az_deg, real_alt_deg = vector_to_altaz(mount_vec)

        azm_steps = (
            int((real_az_deg / 360.0) * STEPS_PER_REVOLUTION) % STEPS_PER_REVOLUTION
        )
        alt_steps = (
            int((real_alt_deg / 360.0) * STEPS_PER_REVOLUTION) % STEPS_PER_REVOLUTION
        )
        return azm_steps, alt_steps

    async def steps_to_equatorial(self, azm_steps, alt_steps):
        """Converts motor encoder steps to RA/Dec."""
        real_az_deg = (azm_steps / STEPS_PER_REVOLUTION) * 360.0
        real_alt_deg = (alt_steps / STEPS_PER_REVOLUTION) * 360.0

        mount_vec = vector_from_altaz(real_az_deg, real_alt_deg)
        sky_vec = self._align_model.transform_to_sky(mount_vec)
        ideal_az_deg, ideal_alt_deg = vector_to_altaz(sky_vec)

        # 2. Refraction (Apparent to True)
        if self.refraction_on.membervalue == "On":
            ideal_alt_deg = remove_refraction(ideal_alt_deg)

        self.update_observer()
        ra_rad, dec_rad = self.observer.radec_of(
            math.radians(ideal_az_deg), math.radians(ideal_alt_deg)
        )

        return (ra_rad / (2 * math.pi)) * 24, (dec_rad / (2 * math.pi)) * 360

    async def handle_guide_rate(self, event):
        """Updates guiding/tracking rates."""
        if event and event.root:
            self.guide_rate_vector.update(event.root)
        val_azm = int(self.guide_azm.membervalue)
        val_alt = int(self.guide_alt.membervalue)

        cmd_azm = AUXCommand(
            AUXCommands.MC_SET_POS_GUIDERATE,
            AUXTargets.APP,
            AUXTargets.AZM,
            pack_int3_steps(val_azm),
        )
        cmd_alt = AUXCommand(
            AUXCommands.MC_SET_POS_GUIDERATE,
            AUXTargets.APP,
            AUXTargets.ALT,
            pack_int3_steps(val_alt),
        )

        s1 = await self.communicator.send_command(cmd_azm)
        s2 = await self.communicator.send_command(cmd_alt)

        if s1 and s2 and (val_azm > 0 or val_alt > 0):
            self.tracking_light.membervalue = "Ok"
        else:
            self.tracking_light.membervalue = "Idle"

        await self.mount_status_vector.send_setVector()
        await self.guide_rate_vector.send_setVector(
            state="Ok" if s1 and s2 else "Alert"
        )

    async def handle_track_mode(self, event):
        """Starts or stops tracking."""
        if event and event.root:
            self.track_mode_vector.update(event.root)

        if self.track_none.membervalue == "On":
            if self._tracking_task:
                self._tracking_task.cancel()
                self._tracking_task = None
            if self.communicator and self.communicator.connected:
                await self.slew_by_rate(AUXTargets.AZM, 0, 1)
                await self.slew_by_rate(AUXTargets.ALT, 0, 1)
            self.tracking_light.membervalue = "Idle"
        else:
            if not self._tracking_task:
                self._tracking_task = asyncio.create_task(self._tracking_loop())
            self.tracking_light.membervalue = "Ok"

        await self.mount_status_vector.send_setVector()
        await self.track_mode_vector.send_setVector(state="Ok")

    async def _tracking_loop(self):
        """Background loop for tracking."""
        try:
            while True:
                if not self.communicator or not self.communicator.connected:
                    await asyncio.sleep(1)
                    continue

                dt = 1.0
                ra_plus, dec_plus = await self._get_target_equatorial(time_offset=dt)
                ra_minus, dec_minus = await self._get_target_equatorial(time_offset=-dt)

                s_plus_azm, s_plus_alt = await self.equatorial_to_steps(
                    ra_plus, dec_plus, time_offset=dt
                )
                s_minus_azm, s_minus_alt = await self.equatorial_to_steps(
                    ra_minus, dec_minus, time_offset=-dt
                )

                def diff_steps(s2, s1):
                    d = s2 - s1
                    if d > STEPS_PER_REVOLUTION / 2:
                        d -= STEPS_PER_REVOLUTION
                    if d < -STEPS_PER_REVOLUTION / 2:
                        d += STEPS_PER_REVOLUTION
                    return d

                rate_azm = diff_steps(s_plus_azm, s_minus_azm) / (2.0 * dt)
                rate_alt = diff_steps(s_plus_alt, s_minus_alt) / (2.0 * dt)

                factor = (360.0 * 3600.0 * 1024.0) / STEPS_PER_REVOLUTION
                val_azm = int(abs(rate_azm) * factor)
                val_alt = int(abs(rate_alt) * factor)

                cmd_azm = AUXCommand(
                    AUXCommands.MC_SET_POS_GUIDERATE
                    if rate_azm >= 0
                    else AUXCommands.MC_SET_NEG_GUIDERATE,
                    AUXTargets.APP,
                    AUXTargets.AZM,
                    pack_int3_steps(min(val_azm, 0xFFFF)),
                )
                cmd_alt = AUXCommand(
                    AUXCommands.MC_SET_POS_GUIDERATE
                    if rate_alt >= 0
                    else AUXCommands.MC_SET_NEG_GUIDERATE,
                    AUXTargets.APP,
                    AUXTargets.ALT,
                    pack_int3_steps(min(val_alt, 0xFFFF)),
                )

                await self.communicator.send_command(cmd_azm)
                await self.communicator.send_command(cmd_alt)

                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in tracking loop: {e}")

    async def hardware(self):
        """Periodically poll hardware status."""
        if self.communicator and self.communicator.connected:
            self.observer.date = ephem.now()
            self.update_observer()
            await self.read_mount_position()

            r_azm = await self.communicator.send_command(
                AUXCommand(AUXCommands.MC_SLEW_DONE, AUXTargets.APP, AUXTargets.AZM)
            )
            r_alt = await self.communicator.send_command(
                AUXCommand(AUXCommands.MC_SLEW_DONE, AUXTargets.APP, AUXTargets.ALT)
            )

            if r_azm and r_alt:
                if r_azm.data[0] != 0xFF or r_alt.data[0] != 0xFF:
                    self.slewing_light.membervalue = "Ok"
                else:
                    self.slewing_light.membervalue = "Idle"

                if not self.is_move_allowed(
                    self.current_azm_steps, self.current_alt_steps
                ):
                    await self.slew_by_rate(AUXTargets.AZM, 0, 1)
                    await self.slew_by_rate(AUXTargets.ALT, 0, 1)
                    self.slewing_light.membervalue = "Alert"

                await self.mount_status_vector.send_setVector()

            # Update alignment stats periodically
            await self.update_alignment_status()


if __name__ == "__main__":
    driver = CelestronAUXDriver()
    asyncio.run(driver.asyncrun())
