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
    IPyDriver, Device, SwitchVector, SwitchMember, 
    TextVector, TextMember, NumberVector, NumberMember, 
    LightVector, LightMember
)
import ephem
from datetime import datetime, timezone
import yaml
import os
import math

# Import AUX protocol implementation
from celestron_aux_driver import (
    AUXCommands, AUXTargets, AUXCommand, 
    AUXCommunicator, pack_int3_steps, unpack_int3_steps,
    STEPS_PER_REVOLUTION
)
from alignment import AlignmentModel, vector_from_radec, vector_from_altaz, vector_to_radec, vector_to_altaz

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml')
DEFAULT_CONFIG = {
    "observer": {
        "latitude": 50.1822,
        "longitude": 19.7925,
        "elevation": 400
    }
}

def load_config():
    """Loads configuration from YAML file or returns defaults."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return DEFAULT_CONFIG

config = load_config()
obs_cfg = config.get("observer", DEFAULT_CONFIG["observer"])

class CelestronAUXDriver(IPyDriver):
    """
    INDI Driver for Celestron mounts.
    
    Manages INDI properties, hardware communication via AUX bus, 
    and coordinate transformations with N-point alignment support.
    """
    def __init__(self, driver_name: str = "Celestron AUX"):
        # 1. Define INDI properties
        self._init_properties()

        # 2. Initialize device with properties
        self.device = Device("Celestron AUX", [
            self.connection_vector, self.port_vector, self.baud_vector, self.firmware_vector,
            self.mount_position_vector, self.mount_status_vector, self.slew_rate_vector,
            self.motion_ns_vector, self.motion_we_vector, self.absolute_coord_vector,
            self.guide_rate_vector, self.sync_vector, self.park_vector, self.unpark_vector,
            self.location_vector, self.equatorial_vector,
            self.approach_mode_vector, self.approach_offset_vector,
            self.track_mode_vector, self.align_vector, self.clear_align_vector,
            self.coord_set_vector
        ])

        super().__init__(self.device)
        self.communicator = None
        self.current_azm_steps = 0
        self.current_alt_steps = 0
        self._tracking_task = None
        self._align_model = AlignmentModel()
        
        # Alignment data: list of (RA, Dec, AzmSteps, AltSteps)
        self._alignment_points = []
        
        # 3. ephem Observer for RA/Dec <-> Alt/Az transformations
        self.observer = ephem.Observer()
        self.observer.pressure = 0
        self.update_observer()

    def _init_properties(self):
        """Initializes all INDI property vectors and members."""
        # Connection
        self.conn_connect = SwitchMember("CONNECT", "Connect", "Off")
        self.conn_disconnect = SwitchMember("DISCONNECT", "Disconnect", "On")
        self.connection_vector = SwitchVector("CONNECTION", "Connection", "Main", "rw", "OneOfMany", "Idle", [self.conn_connect, self.conn_disconnect])

        # Port settings
        self.port_name = TextMember("PORT_NAME", "Port Name", "/dev/ttyUSB0")
        self.baud_rate = NumberMember("BAUD_RATE", "Baud Rate", "%d", 9600, 115200, 1, 19200)
        self.port_vector = TextVector("PORT", "Serial Port", "Main", "rw", "Idle", [self.port_name])
        self.baud_vector = NumberVector("BAUD", "Baud Rate", "Main", "rw", "Idle", [self.baud_rate])

        # Firmware Info
        self.model = TextMember("MODEL", "Model", "Unknown")
        self.hc_ver = TextMember("HC_VERSION", "HC Version", "Unknown")
        self.azm_ver = TextMember("AZM_VERSION", "AZM Version", "Unknown")
        self.alt_ver = TextMember("ALT_VERSION", "ALT Version", "Unknown")
        self.firmware_vector = TextVector("FIRMWARE_INFO", "Firmware Info", "Main", "ro", "Idle", [self.model, self.hc_ver, self.azm_ver, self.alt_ver])

        # Raw position (Steps)
        self.azm_steps = NumberMember("AZM_STEPS", "AZM Steps", "%d", 0, STEPS_PER_REVOLUTION - 1, 1, 0)
        self.alt_steps = NumberMember("ALT_STEPS", "ALT Steps", "%d", 0, STEPS_PER_REVOLUTION - 1, 1, 0)
        self.mount_position_vector = NumberVector("MOUNT_POSITION", "Mount Position", "Main", "ro", "Idle", [self.azm_steps, self.alt_steps])

        # Status indicators
        self.slewing_light = LightMember("SLEWING", "Slewing", "Idle")
        self.tracking_light = LightMember("TRACKING", "Tracking", "Idle")
        self.parked_light = LightMember("PARKED", "Parked", "Idle")
        self.mount_status_vector = LightVector("MOUNT_STATUS", "Mount Status", "Main", "Idle", [self.slewing_light, self.tracking_light, self.parked_light])

        # Motion control
        self.slew_rate = NumberMember("RATE", "Rate (1-9)", "%d", 1, 9, 1, 1)
        self.slew_rate_vector = NumberVector("SLEW_RATE", "Slew Rate", "Main", "rw", "Idle", [self.slew_rate])

        self.motion_n = SwitchMember("MOTION_N", "North", "Off")
        self.motion_s = SwitchMember("MOTION_S", "South", "Off")
        self.motion_ns_vector = SwitchVector("TELESCOPE_MOTION_NS", "Motion N/S", "Main", "rw", "AtMostOne", "Idle", [self.motion_n, self.motion_s])

        self.motion_w = SwitchMember("MOTION_W", "West", "Off")
        self.motion_e = SwitchMember("MOTION_E", "East", "Off")
        self.motion_we_vector = SwitchVector("TELESCOPE_MOTION_WE", "Motion W/E", "Main", "rw", "AtMostOne", "Idle", [self.motion_w, self.motion_e])

        # Coordinates
        self.target_azm = NumberMember("AZM_STEPS", "AZM Steps", "%d", 0, STEPS_PER_REVOLUTION - 1, 1, 0)
        self.target_alt = NumberMember("ALT_STEPS", "ALT Steps", "%d", 0, STEPS_PER_REVOLUTION - 1, 1, 0)
        self.absolute_coord_vector = NumberVector("TELESCOPE_ABSOLUTE_COORD", "Absolute Coordinates", "Main", "rw", "Idle", [self.target_azm, self.target_alt])

        self.guide_azm = NumberMember("GUIDE_AZM", "AZM Guide Rate", "%d", 0, 255, 1, 0)
        self.guide_alt = NumberMember("GUIDE_ALT", "ALT Guide Rate", "%d", 0, 255, 1, 0)
        self.guide_rate_vector = NumberVector("TELESCOPE_GUIDE_RATE", "Guide Rates", "Main", "rw", "Idle", [self.guide_azm, self.guide_alt])

        # Standard Mount Actions
        self.sync_switch = SwitchMember("SYNC", "Sync", "Off")
        self.sync_vector = SwitchVector("TELESCOPE_SYNC", "Sync Mount", "Main", "rw", "AtMostOne", "Idle", [self.sync_switch])

        self.park_switch = SwitchMember("PARK", "Park", "Off")
        self.park_vector = SwitchVector("TELESCOPE_PARK", "Park Mount", "Main", "rw", "AtMostOne", "Idle", [self.park_switch])

        self.unpark_switch = SwitchMember("UNPARK", "Unpark", "Off")
        self.unpark_vector = SwitchVector("TELESCOPE_UNPARK", "Unpark Mount", "Main", "rw", "AtMostOne", "Idle", [self.unpark_switch])

        # Geographical location
        self.lat = NumberMember("LAT", "Latitude (deg)", " %06.2f", -90, 90, 0, obs_cfg.get("latitude", 50.1822))
        self.long = NumberMember("LONG", "Longitude (deg)", " %06.2f", -360, 360, 0, obs_cfg.get("longitude", 19.7925))
        self.elev = NumberMember("ELEV", "Elevation (m)", " %04.0f", -1000, 10000, 0, obs_cfg.get("elevation", 400))
        self.location_vector = NumberVector("GEOGRAPHIC_COORD", "Location", "Site", "rw", "Idle", [self.lat, self.long, self.elev])

        # Equatorial coordinates
        self.ra = NumberMember("RA", "Right Ascension (h)", "%08.3f", 0, 24, 0, 0)
        self.dec = NumberMember("DEC", "Declination (deg)", "%08.3f", -90, 90, 0, 0)
        self.equatorial_vector = NumberVector("EQUATORIAL_EOD_COORD", "Equatorial JNow", "Main", "rw", "Idle", [self.ra, self.dec])

        # GoTo Approach settings
        self.approach_disabled = SwitchMember("DISABLED", "Disabled", "On")
        self.approach_fixed = SwitchMember("FIXED_OFFSET", "Fixed Offset", "Off")
        self.approach_tracking = SwitchMember("TRACKING_DIRECTION", "Tracking Direction", "Off")
        self.approach_mode_vector = SwitchVector("GOTO_APPROACH_MODE", "Approach Mode", "Options", "rw", "OneOfMany", "Idle", 
                                               [self.approach_disabled, self.approach_fixed, self.approach_tracking])

        self.approach_azm_offset = NumberMember("AZM_OFFSET", "AZM Offset (steps)", "%d", 0, 1000000, 1, 10000)
        self.approach_alt_offset = NumberMember("ALT_OFFSET", "ALT Offset (steps)", "%d", 0, 1000000, 1, 10000)
        self.approach_offset_vector = NumberVector("GOTO_APPROACH_OFFSET", "Approach Offset", "Options", "rw", "Idle", 
                                                 [self.approach_azm_offset, self.approach_alt_offset])

        # Tracking Modes
        self.track_none = SwitchMember("TRACK_OFF", "Off", "On")
        self.track_sidereal = SwitchMember("TRACK_SIDEREAL", "Sidereal", "Off")
        self.track_solar = SwitchMember("TRACK_SOLAR", "Solar", "Off")
        self.track_lunar = SwitchMember("TRACK_LUNAR", "Lunar", "Off")
        self.track_mode_vector = SwitchVector("TELESCOPE_TRACK_MODE", "Tracking Mode", "Main", "rw", "OneOfMany", "Idle",
                                            [self.track_none, self.track_sidereal, self.track_solar, self.track_lunar])

        # Coordination Set Mode (Slew, Track, Sync)
        self.set_slew = SwitchMember("SLEW", "Slew", "On")
        self.set_track = SwitchMember("TRACK", "Track", "Off")
        self.set_sync = SwitchMember("SYNC", "Sync", "Off")
        self.coord_set_vector = SwitchVector("TELESCOPE_ON_COORD_SET", "Coord Set Mode", "Main", "rw", "OneOfMany", "Idle",
                                           [self.set_slew, self.set_track, self.set_sync])

        # Alignment System
        self.align_star1 = TextMember("STAR1", "Star 1", "None")
        self.align_star2 = TextMember("STAR2", "Star 2", "None")
        self.align_star3 = TextMember("STAR3", "Star 3", "None")
        self.align_vector = TextVector("ALIGNMENT_INFO", "Alignment Stars", "Alignment", "ro", "Idle", 
                                     [self.align_star1, self.align_star2, self.align_star3])
        
        self.clear_align = SwitchMember("CLEAR", "Clear Alignment", "Off")
        self.clear_align_vector = SwitchVector("CLEAR_ALIGNMENT", "Clear Alignment", "Alignment", "rw", "AtMostOne", "Idle", [self.clear_align])

    def update_observer(self, time_offset: float = 0):
        """Updates ephem Observer state from INDI location properties."""
        self.observer.lat = str(self.lat.membervalue)
        self.observer.lon = str(self.long.membervalue)
        self.observer.elevation = float(self.elev.membervalue)
        # Use ephem.now() for better consistency with simulator
        if time_offset == 0:
            self.observer.date = ephem.now()
        else:
            self.observer.date = ephem.now() + time_offset / 86400.0
        
        # Ensure we use JNow (Equinox of Date)
        self.observer.epoch = self.observer.date
        
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
        elif event.vectorname == "CLEAR_ALIGNMENT":
            await self.handle_clear_alignment(event)

    async def handle_connection(self, event):
        """Handles CONNECT/DISCONNECT switches."""
        if event and event.root:
            self.connection_vector.update(event.root)
        if self.conn_connect.membervalue == "On":
            self.communicator = AUXCommunicator(self.port_name.membervalue, int(self.baud_rate.membervalue))
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
        if not self.communicator or not self.communicator.connected: return
        
        # Get Model
        resp = await self.communicator.send_command(AUXCommand(AUXCommands.MC_GET_MODEL, AUXTargets.APP, AUXTargets.AZM))
        if resp:
            model_id = resp.get_data_as_int()
            model_map = {0x0001: "Nexstar GPS", 0x0783: "Nexstar SLT", 0x0b83: "4/5SE", 0x0c82: "6/8SE", 0x1189: "CPC Deluxe", 0x1283: "GT Series", 0x1485: "AVX", 0x1687: "Evolution", 0x1788: "CGX"}
            self.model.membervalue = model_map.get(model_id, f"Unknown (0x{model_id:04X})")
        
        # Get Versions
        for target, member in [(AUXTargets.AZM, self.azm_ver), (AUXTargets.ALT, self.alt_ver), (AUXTargets.HC, self.hc_ver)]:
            resp = await self.communicator.send_command(AUXCommand(AUXCommands.GET_VER, AUXTargets.APP, target))
            if resp and len(resp.data) == 4:
                member.membervalue = f"{resp.data[0]}.{resp.data[1]}.{resp.data[2]*256 + resp.data[3]}"
        
        await self.firmware_vector.send_setVector(state="Ok")

    async def read_mount_position(self):
        """Periodically reads encoder steps and updates RA/Dec."""
        if not self.communicator or not self.communicator.connected: return
        
        # AZM
        resp = await self.communicator.send_command(AUXCommand(AUXCommands.MC_GET_POSITION, AUXTargets.APP, AUXTargets.AZM))
        if resp and len(resp.data) == 3:
            self.current_azm_steps = unpack_int3_steps(resp.data)
            self.azm_steps.membervalue = self.current_azm_steps
            
        # ALT
        resp = await self.communicator.send_command(AUXCommand(AUXCommands.MC_GET_POSITION, AUXTargets.APP, AUXTargets.ALT))
        if resp and len(resp.data) == 3:
            self.current_alt_steps = unpack_int3_steps(resp.data)
            self.alt_steps.membervalue = self.current_alt_steps
            
        await self.mount_position_vector.send_setVector(state="Ok")
        
        # Calculate current RA/Dec
        ra_val, dec_val = await self.steps_to_equatorial(self.current_azm_steps, self.current_alt_steps)
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
        cmd_type = AUXCommands.MC_MOVE_POS if direction == 1 else AUXCommands.MC_MOVE_NEG
        cmd = AUXCommand(cmd_type, AUXTargets.APP, axis, bytes([rate]))
        resp = await self.communicator.send_command(cmd)
        if resp:
            self.slewing_light.membervalue = "Ok" if rate > 0 else "Idle"
            await self.mount_status_vector.send_setVector()

    async def _wait_for_slew(self, axis):
        """Waits until the specified axis finishes slewing."""
        for _ in range(60): # 60 seconds timeout
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
            if d > STEPS_PER_REVOLUTION/2: d -= STEPS_PER_REVOLUTION
            if d < -STEPS_PER_REVOLUTION/2: d += STEPS_PER_REVOLUTION
            return d
            
        return diff_steps(s2_azm, s1_azm)/60.0, diff_steps(s2_alt, s1_alt)/60.0

    async def goto_position(self, target_azm, target_alt, ra=None, dec=None):
        """
        Executes a GoTo movement with optional anti-backlash approach.
        """
        approach_mode = "DISABLED"
        if self.approach_fixed.membervalue == "On": approach_mode = "FIXED"
        elif self.approach_tracking.membervalue == "On": approach_mode = "TRACKING"
        
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
                self._do_slew(AUXTargets.ALT, inter_alt, fast=True)
            )
            
            await asyncio.gather(
                self._wait_for_slew(AUXTargets.AZM),
                self._wait_for_slew(AUXTargets.ALT)
            )

        fast_final = (approach_mode == "DISABLED")
        s1 = await self._do_slew(AUXTargets.AZM, target_azm, fast=fast_final)
        s2 = await self._do_slew(AUXTargets.ALT, target_alt, fast=fast_final)
        
        return s1 and s2

    async def handle_goto(self, event):
        """Handles GoTo command using raw encoder steps."""
        self.absolute_coord_vector.update(event.root)
        await self.absolute_coord_vector.send_setVector(state="Busy")
        
        target_azm = int(self.target_azm.membervalue)
        target_alt = int(self.target_alt.membervalue)
        
        success = await self.goto_position(target_azm, target_alt)
        
        state = "Ok" if success else "Alert"
        await self.absolute_coord_vector.send_setVector(state=state)

    async def slew_to(self, axis, steps, fast=True):
        """Sends a position-based GoTo command to a motor axis."""
        return await self._do_slew(axis, steps, fast)

    async def handle_sync(self, event):
        """Adds current position as an alignment point or performs simple sync."""
        if event and event.root:
            self.sync_vector.update(event.root)
        
        if self.sync_switch.membervalue == "On":
            await self.sync_vector.send_setVector(state="Busy")
            
            # Record current point for alignment
            ra_val = float(self.ra.membervalue)
            dec_val = float(self.dec.membervalue)
            
            # 1. Convert RA/Dec to ideal Alt/Az (using current time/location)
            self.update_observer()
            body = ephem.FixedBody()
            body._ra = math.radians(ra_val * 15.0)
            body._dec = math.radians(dec_val)
            body.compute(self.observer)
            
            ideal_az_deg = math.degrees(float(body.az))
            ideal_alt_deg = math.degrees(float(body.alt))
            
            # 2. Get current raw Alt/Az from encoders
            raw_az_deg = (self.current_azm_steps / STEPS_PER_REVOLUTION) * 360.0
            raw_alt_deg = (self.current_alt_steps / STEPS_PER_REVOLUTION) * 360.0
            
            # 3. Add vectors to alignment model
            sky_vec = vector_from_altaz(ideal_az_deg, ideal_alt_deg)
            mount_vec = vector_from_altaz(raw_az_deg, raw_alt_deg)
            self._align_model.add_point(sky_vec, mount_vec)
            
            # Add to list for GUI info
            self._alignment_points.append({
                'ra': ra_val, 'dec': dec_val,
                'azm': self.current_azm_steps, 'alt': self.current_alt_steps,
                'time': datetime.now(timezone.utc)
            })
            if len(self._alignment_points) > 3:
                self._alignment_points.pop(0)
            
            # Update info
            stars = [self.align_star1, self.align_star2, self.align_star3]
            for i, p in enumerate(self._alignment_points):
                stars[i].membervalue = f"RA:{p['ra']:.2f} Dec:{p['dec']:.2f}"
            await self.align_vector.send_setVector()

            # Physical Sync (sets MC position to current state - effectively a 1-point align in hardware)
            cmd_azm = AUXCommand(AUXCommands.MC_SET_POSITION, AUXTargets.APP, AUXTargets.AZM, pack_int3_steps(self.current_azm_steps))
            cmd_alt = AUXCommand(AUXCommands.MC_SET_POSITION, AUXTargets.APP, AUXTargets.ALT, pack_int3_steps(self.current_alt_steps))
            s1 = await self.communicator.send_command(cmd_azm)
            s2 = await self.communicator.send_command(cmd_alt)
            
            self.sync_switch.membervalue = "Off"
            await self.sync_vector.send_setVector(state="Ok" if s1 and s2 else "Alert")

    async def handle_clear_alignment(self, event):
        """Clears all stored alignment points."""
        if event and event.root:
            self.clear_align_vector.update(event.root)
        if self.clear_align.membervalue == "On":
            self._alignment_points = []
            self._align_model.clear()
            self.align_star1.membervalue = self.align_star2.membervalue = self.align_star3.membervalue = "None"
            await self.align_vector.send_setVector()
            self.clear_align.membervalue = "Off"
            await self.clear_align_vector.send_setVector(state="Ok")

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
        
        target_ra = float(self.ra.membervalue)
        target_dec = float(self.dec.membervalue)

        if self.set_sync.membervalue == "On":
            # Perform SYNC
            await self.equatorial_vector.send_setVector(state="Busy")
            
            # Ensure we have fresh encoder data
            await self.read_mount_position()
            
            # 1. Convert Target RA/Dec to ideal Alt/Az
            self.update_observer()
            body = ephem.FixedBody()
            body._ra = math.radians(target_ra * 15.0)
            body._dec = math.radians(target_dec)
            body.compute(self.observer)
            
            ideal_az_deg = math.degrees(float(body.az))
            ideal_alt_deg = math.degrees(float(body.alt))
            
            # 2. Get current raw Alt/Az from encoders
            raw_az_deg = (self.current_azm_steps / STEPS_PER_REVOLUTION) * 360.0
            raw_alt_deg = (self.current_alt_steps / STEPS_PER_REVOLUTION) * 360.0
            
            # 3. Add vectors to alignment model
            sky_vec = vector_from_altaz(ideal_az_deg, ideal_alt_deg)
            mount_vec = vector_from_altaz(raw_az_deg, raw_alt_deg)
            self._align_model.add_point(sky_vec, mount_vec)
            
            # print(f"SYNC: RA={ra_val} Dec={dec_val} -> IdealAz={ideal_az_deg} IdealAlt={ideal_alt_deg} RawAz={raw_az_deg} RawAlt={raw_alt_deg}")
            
            # Update info
            stars = [self.align_star1, self.align_star2, self.align_star3]
            for i, p in enumerate(self._align_model.points):
                # Back-calculate RA/Dec for the star (approx)
                s_ra, s_dec = vector_to_radec(self._align_model.points[i][0]) # This is simplified
                stars[i].membervalue = f"RA:{s_ra:.2f} Dec:{s_dec:.2f}"
            await self.align_vector.send_setVector()

            # Physical Sync (sets MC position to current state)
            cmd_azm = AUXCommand(AUXCommands.MC_SET_POSITION, AUXTargets.APP, AUXTargets.AZM, pack_int3_steps(self.current_azm_steps))
            cmd_alt = AUXCommand(AUXCommands.MC_SET_POSITION, AUXTargets.APP, AUXTargets.ALT, pack_int3_steps(self.current_alt_steps))
            s1 = await self.communicator.send_command(cmd_azm)
            s2 = await self.communicator.send_command(cmd_alt)
            
            await self.equatorial_vector.send_setVector(state="Ok" if s1 and s2 else "Alert")
        else:
            # Perform GOTO
            await self.equatorial_vector.send_setVector(state="Busy")
            azm_steps, alt_steps = await self.equatorial_to_steps(target_ra, target_dec)
            success = await self.goto_position(azm_steps, alt_steps, ra=target_ra, dec=target_dec)
            await self.equatorial_vector.send_setVector(state="Ok" if success else "Alert")

    async def equatorial_to_steps(self, ra_hours, dec_deg, time_offset: float = 0):
        """Converts RA/Dec to motor encoder steps using current observer state and alignment."""
        import math
        ra_rad = (ra_hours / 24.0) * 2 * math.pi
        dec_rad = (dec_deg / 360.0) * 2 * math.pi
        
        body = ephem.FixedBody()
        body._ra = ra_rad
        body._dec = dec_rad
        
        self.update_observer(time_offset=time_offset)
        body.compute(self.observer)
        
        ideal_az_deg = math.degrees(float(body.az))
        ideal_alt_deg = math.degrees(float(body.alt))
        
        # Apply Alignment Transform
        sky_vec = vector_from_altaz(ideal_az_deg, ideal_alt_deg)
        mount_vec = self._align_model.transform_to_mount(sky_vec)
        real_az_deg, real_alt_deg = vector_to_altaz(mount_vec)
        
        azm_steps = int((real_az_deg / 360.0) * STEPS_PER_REVOLUTION) % STEPS_PER_REVOLUTION
        alt_steps = int((real_alt_deg / 360.0) * STEPS_PER_REVOLUTION) % STEPS_PER_REVOLUTION
        return azm_steps, alt_steps

    async def steps_to_equatorial(self, azm_steps, alt_steps):
        """Converts motor encoder steps to RA/Dec using current observer state and alignment."""
        import math
        real_az_deg = (azm_steps / STEPS_PER_REVOLUTION) * 360.0
        real_alt_deg = (alt_steps / STEPS_PER_REVOLUTION) * 360.0
        
        # Apply Inverse Alignment Transform
        mount_vec = vector_from_altaz(real_az_deg, real_alt_deg)
        sky_vec = self._align_model.transform_to_sky(mount_vec)
        ideal_az_deg, ideal_alt_deg = vector_to_altaz(sky_vec)
        
        self.update_observer()
        ra_rad, dec_rad = self.observer.radec_of(math.radians(ideal_az_deg), math.radians(ideal_alt_deg))
        
        ra_hours = (ra_rad / (2 * math.pi)) * 24
        dec_deg = (dec_rad / (2 * math.pi)) * 360
        return ra_hours, dec_deg

    async def handle_guide_rate(self, event):
        """Updates guiding/tracking rates for both axes."""
        if event and event.root:
            self.guide_rate_vector.update(event.root)
        val_azm = int(self.guide_azm.membervalue)
        val_alt = int(self.guide_alt.membervalue)
        
        cmd_azm = AUXCommand(AUXCommands.MC_SET_POS_GUIDERATE, AUXTargets.APP, AUXTargets.AZM, pack_int3_steps(val_azm))
        cmd_alt = AUXCommand(AUXCommands.MC_SET_POS_GUIDERATE, AUXTargets.APP, AUXTargets.ALT, pack_int3_steps(val_alt))
        
        s1 = await self.communicator.send_command(cmd_azm)
        s2 = await self.communicator.send_command(cmd_alt)
        
        state = "Ok" if s1 and s2 else "Alert"
        if s1 and s2 and (val_azm > 0 or val_alt > 0):
            self.tracking_light.membervalue = "Ok"
        else:
            self.tracking_light.membervalue = "Idle"
            
        await self.mount_status_vector.send_setVector()
        await self.guide_rate_vector.send_setVector(state=state)

    async def handle_track_mode(self, event):
        """Starts or stops the background tracking loop."""
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
        """
        Background loop for object tracking using 2nd order prediction.
        """
        try:
            while True:
                if not self.communicator or not self.communicator.connected:
                    await asyncio.sleep(1)
                    continue

                ra = float(self.ra.membervalue)
                dec = float(self.dec.membervalue)
                
                dt = 1.0 
                s_plus_azm, s_plus_alt = await self.equatorial_to_steps(ra, dec, time_offset=dt)
                s_minus_azm, s_minus_alt = await self.equatorial_to_steps(ra, dec, time_offset=-dt)
                
                def diff_steps(s2, s1):
                    d = s2 - s1
                    if d > STEPS_PER_REVOLUTION/2: d -= STEPS_PER_REVOLUTION
                    if d < -STEPS_PER_REVOLUTION/2: d += STEPS_PER_REVOLUTION
                    return d
                
                rate_azm = diff_steps(s_plus_azm, s_minus_azm) / (2.0 * dt)
                rate_alt = diff_steps(s_plus_alt, s_minus_alt) / (2.0 * dt)
                
                # rate_arcsec_sec = rate_steps_sec * (360 * 3600) / STEPS_PER_REVOLUTION
                # payload = rate_arcsec_sec * 1024
                factor = (360.0 * 3600.0 * 1024.0) / STEPS_PER_REVOLUTION
                val_azm = int(abs(rate_azm) * factor)
                val_alt = int(abs(rate_alt) * factor)
                
                cmd_azm = AUXCommand(
                    AUXCommands.MC_SET_POS_GUIDERATE if rate_azm >= 0 else AUXCommands.MC_SET_NEG_GUIDERATE,
                    AUXTargets.APP, AUXTargets.AZM, pack_int3_steps(min(val_azm, 0xFFFF))
                )
                cmd_alt = AUXCommand(
                    AUXCommands.MC_SET_POS_GUIDERATE if rate_alt >= 0 else AUXCommands.MC_SET_NEG_GUIDERATE,
                    AUXTargets.APP, AUXTargets.ALT, pack_int3_steps(min(val_alt, 0xFFFF))
                )
                
                await self.communicator.send_command(cmd_azm)
                await self.communicator.send_command(cmd_alt)
                
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in tracking loop: {e}")

    async def hardware(self):
        """Periodically called to sync hardware state with INDI properties."""
        if self.communicator and self.communicator.connected:
            await self.read_mount_position()

if __name__ == "__main__":
    driver = CelestronAUXDriver()
    asyncio.run(driver.asyncrun())
