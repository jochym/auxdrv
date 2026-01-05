import asyncio
import serial_asyncio
from enum import Enum
import indipydriver
from indipydriver import IPyDriver, Device, SwitchVector, SwitchMember, TextVector, TextMember, NumberVector, NumberMember, LightVector, LightMember

# Enums from auxproto.h
class AUXCommands(Enum):
    MC_GET_POSITION      = 0x01
    MC_GOTO_FAST         = 0x02
    MC_SET_POSITION      = 0x04
    MC_GET_MODEL         = 0x05
    MC_SET_POS_GUIDERATE = 0x06
    MC_SET_NEG_GUIDERATE = 0x07
    MC_LEVEL_START       = 0x0b
    MC_LEVEL_DONE        = 0x12
    MC_SLEW_DONE         = 0x13
    MC_GOTO_SLOW         = 0x17
    MC_SEEK_DONE         = 0x18
    MC_SEEK_INDEX        = 0x19
    MC_MOVE_POS          = 0x24
    MC_MOVE_NEG          = 0x25
    MC_AUX_GUIDE         = 0x26
    MC_AUX_GUIDE_ACTIVE  = 0x27
    MC_ENABLE_CORDWRAP   = 0x38
    MC_DISABLE_CORDWRAP  = 0x39
    MC_SET_CORDWRAP_POS  = 0x3a
    MC_POLL_CORDWRAP     = 0x3b
    MC_GET_CORDWRAP_POS  = 0x3c
    MC_SET_AUTOGUIDE_RATE = 0x46
    MC_GET_AUTOGUIDE_RATE = 0x47
    GET_VER              = 0xfe
    GPS_GET_LAT          = 0x01
    GPS_GET_LONG         = 0x02
    GPS_GET_DATE         = 0x03
    GPS_GET_YEAR         = 0x04
    GPS_GET_TIME         = 0x33
    GPS_TIME_VALID       = 0x36
    GPS_LINKED           = 0x37
    FOC_GET_HS_POSITIONS = 0x2c

class AUXTargets(Enum):
    ANY   = 0x00
    MB    = 0x01
    HC    = 0x04
    HCP   = 0x0d
    AZM   = 0x10
    ALT   = 0x11
    FOCUS = 0x12
    APP   = 0x20
    GPS   = 0xb0
    WiFi  = 0xb5
    BAT   = 0xb6
    CHG   = 0xb7
    LIGHT = 0xbf

class AUXCommand:
    START_BYTE = 0x3b
    MAX_CMD_LEN = 32

    def __init__(self, command: AUXCommands, source: AUXTargets, destination: AUXTargets, data: bytes = b''):
        self.command = command
        self.source = source
        self.destination = destination
        self.data = data
        self.length = 3 + len(self.data)

    def fill_buf(self) -> bytes:
        buf = bytearray()
        buf.append(self.START_BYTE)
        buf.append(self.length)
        buf.append(self.source.value)
        buf.append(self.destination.value)
        buf.append(self.command.value)
        buf.extend(self.data)
        buf.append(self._calculate_checksum(buf[1:]))
        return bytes(buf)

    @classmethod
    def parse_buf(cls, buf: bytes):
        if not buf or buf[0] != cls.START_BYTE:
            raise ValueError(f"Invalid start byte or empty buffer: {buf.hex()}")

        length = buf[1]
        source = AUXTargets(buf[2])
        destination = AUXTargets(buf[3])
        command = AUXCommands(buf[4])
        data = buf[5:-1]
        checksum = buf[-1]

        calculated_checksum = cls._calculate_checksum(buf[1:-1])
        if calculated_checksum != checksum:
            print(f"Checksum error: Expected {calculated_checksum:02X}, Got {checksum:02X} for buffer {buf.hex()}")

        cmd = cls(command, source, destination, data)
        cmd.length = length
        return cmd

    @staticmethod
    def _calculate_checksum(data) -> int:
        cs = sum(data)
        return ((~cs) + 1) & 0xFF

    def get_data_as_int(self) -> int:
        value = 0
        if len(self.data) == 3:
            value = (self.data[0] << 16) | (self.data[1] << 8) | self.data[2]
        elif len(self.data) == 2:
            value = (self.data[0] << 8) | self.data[1]
        elif len(self.data) == 1:
            value = self.data[0]
        return value

    def set_data_from_int(self, value: int, num_bytes: int):
        if num_bytes == 1:
            self.data = value.to_bytes(1, 'big')
        elif num_bytes == 2:
            self.data = value.to_bytes(2, 'big')
        elif num_bytes == 3:
            self.data = value.to_bytes(3, 'big')
        else:
            raise ValueError("num_bytes must be 1, 2, or 3")
        self.length = 3 + len(self.data)

    def __repr__(self):
        return f"AUXCommand(cmd={self.command.name}, src={self.source.name}, dst={self.destination.name}, data={self.data.hex()}, len={self.length})"

def unpack_int3_steps(d: bytes) -> int:
    if len(d) != 3:
        raise ValueError("Input bytes must be 3 bytes long for unpack_int3_steps")
    val = int.from_bytes(d, 'big', signed=False)
    return val

def pack_int3_steps(val: int) -> bytes:
    if not 0 <= val < 2**24:
        raise ValueError("Value out of range for 3-byte unsigned integer")
    return val.to_bytes(3, 'big', signed=False)

STEPS_PER_REVOLUTION = 16777216
STEPS_PER_DEGREE = STEPS_PER_REVOLUTION / 360.0
STEPS_PER_ARCSEC = STEPS_PER_DEGREE / 3600.0
DEGREES_PER_STEP = 360.0 / STEPS_PER_REVOLUTION

class AUXCommunicator:
    def __init__(self, port: str, baudrate: int = 19200, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.reader = None
        self.writer = None
        self.connected = False

    async def connect(self):
        try:
            if self.port.startswith("socket://"):
                host, port = self.port[9:].split(':')
                self.reader, self.writer = await asyncio.open_connection(host, int(port))
            else:
                self.reader, self.writer = await serial_asyncio.open_serial_connection(
                    url=self.port, baudrate=self.baudrate
                )
            self.connected = True
            print(f"Communicator: Connected to {self.port} at {self.baudrate} baud.")
            return True
        except Exception as e:
            print(f"Communicator: Error connecting: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        if self.writer and self.connected:
            self.writer.close()
            await self.writer.wait_closed()
            self.connected = False
            print(f"Communicator: Disconnected from {self.port}")

    async def send_command(self, command: AUXCommand) -> AUXCommand | None:
        if not self.connected or not self.writer:
            return None

        tx_buf = command.fill_buf()
        try:
            self.writer.write(tx_buf)
            await self.writer.drain()

            while True:
                start_byte = await asyncio.wait_for(self.reader.readexactly(1), timeout=self.timeout)
                if start_byte[0] != AUXCommand.START_BYTE:
                    continue

                length_byte = await asyncio.wait_for(self.reader.readexactly(1), timeout=self.timeout)
                response_length = length_byte[0]
                remaining_bytes = await asyncio.wait_for(self.reader.readexactly(response_length + 1), timeout=self.timeout)

                rx_buf = start_byte + length_byte + remaining_bytes
                resp = AUXCommand.parse_buf(rx_buf)
                if resp.source == command.source:
                    continue
                return resp
        except Exception as e:
            print(f"Communicator: Error: {e}")
            return None

class CelestronAUXDriver(IPyDriver):
    def __init__(self, driver_name: str = "Celestron AUX"):
        # Define properties and members
        self.conn_connect = SwitchMember("CONNECT", "Connect", "Off")
        self.conn_disconnect = SwitchMember("DISCONNECT", "Disconnect", "On")
        self.connection_vector = SwitchVector("CONNECTION", "Connection", "Main", "rw", "OneOfMany", "Idle", [self.conn_connect, self.conn_disconnect])

        self.port_name = TextMember("PORT_NAME", "Port Name", "/dev/ttyUSB0")
        self.baud_rate = NumberMember("BAUD_RATE", "Baud Rate", "%d", 9600, 115200, 1, 19200)
        self.port_vector = TextVector("PORT", "Serial Port", "Main", "rw", "Idle", [self.port_name])
        self.baud_vector = NumberVector("BAUD", "Baud Rate", "Main", "rw", "Idle", [self.baud_rate])

        self.model = TextMember("MODEL", "Model", "Unknown")
        self.hc_ver = TextMember("HC_VERSION", "HC Version", "Unknown")
        self.azm_ver = TextMember("AZM_VERSION", "AZM Version", "Unknown")
        self.alt_ver = TextMember("ALT_VERSION", "ALT Version", "Unknown")
        self.firmware_vector = TextVector("FIRMWARE_INFO", "Firmware Info", "Main", "ro", "Idle", [self.model, self.hc_ver, self.azm_ver, self.alt_ver])

        self.azm_steps = NumberMember("AZM_STEPS", "AZM Steps", "%d", 0, STEPS_PER_REVOLUTION - 1, 1, 0)
        self.alt_steps = NumberMember("ALT_STEPS", "ALT Steps", "%d", 0, STEPS_PER_REVOLUTION - 1, 1, 0)
        self.mount_position_vector = NumberVector("MOUNT_POSITION", "Mount Position", "Main", "ro", "Idle", [self.azm_steps, self.alt_steps])

        self.slewing_light = LightMember("SLEWING", "Slewing", "Idle")
        self.tracking_light = LightMember("TRACKING", "Tracking", "Idle")
        self.parked_light = LightMember("PARKED", "Parked", "Idle")
        self.mount_status_vector = LightVector("MOUNT_STATUS", "Mount Status", "Main", "Idle", [self.slewing_light, self.tracking_light, self.parked_light])

        self.slew_rate = NumberMember("RATE", "Rate (1-9)", "%d", 1, 9, 1, 1)
        self.slew_rate_vector = NumberVector("SLEW_RATE", "Slew Rate", "Main", "rw", "Idle", [self.slew_rate])

        self.motion_n = SwitchMember("MOTION_N", "North", "Off")
        self.motion_s = SwitchMember("MOTION_S", "South", "Off")
        self.motion_ns_vector = SwitchVector("TELESCOPE_MOTION_NS", "Motion N/S", "Main", "rw", "AtMostOne", "Idle", [self.motion_n, self.motion_s])

        self.motion_w = SwitchMember("MOTION_W", "West", "Off")
        self.motion_e = SwitchMember("MOTION_E", "East", "Off")
        self.motion_we_vector = SwitchVector("TELESCOPE_MOTION_WE", "Motion W/E", "Main", "rw", "AtMostOne", "Idle", [self.motion_w, self.motion_e])

        self.target_azm = NumberMember("AZM_STEPS", "AZM Steps", "%d", 0, STEPS_PER_REVOLUTION - 1, 1, 0)
        self.target_alt = NumberMember("ALT_STEPS", "ALT Steps", "%d", 0, STEPS_PER_REVOLUTION - 1, 1, 0)
        self.absolute_coord_vector = NumberVector("TELESCOPE_ABSOLUTE_COORD", "Absolute Coordinates", "Main", "rw", "Idle", [self.target_azm, self.target_alt])

        self.sync_switch = SwitchMember("SYNC", "Sync", "Off")
        self.sync_vector = SwitchVector("TELESCOPE_SYNC", "Sync Mount", "Main", "rw", "AtMostOne", "Idle", [self.sync_switch])

        self.park_switch = SwitchMember("PARK", "Park", "Off")
        self.park_vector = SwitchVector("TELESCOPE_PARK", "Park Mount", "Main", "rw", "AtMostOne", "Idle", [self.park_switch])

        self.unpark_switch = SwitchMember("UNPARK", "Unpark", "Off")
        self.unpark_vector = SwitchVector("TELESCOPE_UNPARK", "Unpark Mount", "Main", "rw", "AtMostOne", "Idle", [self.unpark_switch])

        # Create device
        self.device = Device("Celestron AUX", [
            self.connection_vector, self.port_vector, self.baud_vector, self.firmware_vector,
            self.mount_position_vector, self.mount_status_vector, self.slew_rate_vector,
            self.motion_ns_vector, self.motion_we_vector, self.absolute_coord_vector,
            self.sync_vector, self.park_vector, self.unpark_vector
        ])

        super().__init__(self.device)
        self.communicator = None
        self.current_azm_steps = 0
        self.current_alt_steps = 0

    async def rxevent(self, event):
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
        elif event.vectorname == "TELESCOPE_SYNC":
            await self.handle_sync(event)
        elif event.vectorname == "TELESCOPE_PARK":
            await self.handle_park(event)
        elif event.vectorname == "TELESCOPE_UNPARK":
            await self.handle_unpark(event)

    async def handle_connection(self, event):
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
        if not self.communicator or not self.communicator.connected: return
        
        # Model
        resp = await self.communicator.send_command(AUXCommand(AUXCommands.MC_GET_MODEL, AUXTargets.APP, AUXTargets.AZM))
        if resp:
            model_id = resp.get_data_as_int()
            model_map = {0x0001: "Nexstar GPS", 0x0783: "Nexstar SLT", 0x0b83: "4/5SE", 0x0c82: "6/8SE", 0x1189: "CPC Deluxe", 0x1283: "GT Series", 0x1485: "AVX", 0x1687: "Evolution", 0x1788: "CGX"}
            self.model.membervalue = model_map.get(model_id, f"Unknown (0x{model_id:04X})")
        
        # Versions
        for target, member in [(AUXTargets.AZM, self.azm_ver), (AUXTargets.ALT, self.alt_ver), (AUXTargets.HC, self.hc_ver)]:
            resp = await self.communicator.send_command(AUXCommand(AUXCommands.GET_VER, AUXTargets.APP, target))
            if resp and len(resp.data) == 4:
                member.membervalue = f"{resp.data[0]}.{resp.data[1]}.{resp.data[2]*256 + resp.data[3]}"
        
        await self.firmware_vector.send_setVector(state="Ok")

    async def read_mount_position(self):
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

    async def handle_motion_ns(self, event):
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
        cmd_type = AUXCommands.MC_MOVE_POS if direction == 1 else AUXCommands.MC_MOVE_NEG
        cmd = AUXCommand(cmd_type, AUXTargets.APP, axis, bytes([rate]))
        resp = await self.communicator.send_command(cmd)
        if resp:
            self.slewing_light.membervalue = "Ok" if rate > 0 else "Idle"
            await self.mount_status_vector.send_setVector()

    async def handle_goto(self, event):
        self.absolute_coord_vector.update(event.root)
        await self.absolute_coord_vector.send_setVector(state="Busy")
        
        azm_success = await self.slew_to(AUXTargets.AZM, int(self.target_azm.membervalue))
        alt_success = await self.slew_to(AUXTargets.ALT, int(self.target_alt.membervalue))
        
        state = "Ok" if azm_success and alt_success else "Alert"
        await self.absolute_coord_vector.send_setVector(state=state)

    async def slew_to(self, axis, steps, fast=True):
        cmd_type = AUXCommands.MC_GOTO_FAST if fast else AUXCommands.MC_GOTO_SLOW
        cmd = AUXCommand(cmd_type, AUXTargets.APP, axis, pack_int3_steps(steps))
        resp = await self.communicator.send_command(cmd)
        if resp:
            self.slewing_light.membervalue = "Ok"
            await self.mount_status_vector.send_setVector()
            return True
        return False

    async def handle_sync(self, event):
        self.sync_vector.update(event.root)
        if self.sync_switch.membervalue == "On":
            await self.sync_vector.send_setVector(state="Busy")
            cmd_azm = AUXCommand(AUXCommands.MC_SET_POSITION, AUXTargets.APP, AUXTargets.AZM, pack_int3_steps(self.current_azm_steps))
            cmd_alt = AUXCommand(AUXCommands.MC_SET_POSITION, AUXTargets.APP, AUXTargets.ALT, pack_int3_steps(self.current_alt_steps))
            s1 = await self.communicator.send_command(cmd_azm)
            s2 = await self.communicator.send_command(cmd_alt)
            state = "Ok" if s1 and s2 else "Alert"
            self.sync_switch.membervalue = "Off"
            await self.sync_vector.send_setVector(state=state)

    async def handle_park(self, event):
        self.park_vector.update(event.root)
        if self.park_switch.membervalue == "On":
            await self.park_vector.send_setVector(state="Busy")
            if await self.slew_to(AUXTargets.AZM, 0) and await self.slew_to(AUXTargets.ALT, 0):
                self.parked_light.membervalue = "Ok"
                await self.mount_status_vector.send_setVector()
                await self.park_vector.send_setVector(state="Ok")
            else:
                await self.park_vector.send_setVector(state="Alert")
            self.park_switch.membervalue = "Off"
            await self.park_vector.send_setVector()

    async def handle_unpark(self, event):
        self.unpark_vector.update(event.root)
        if self.unpark_switch.membervalue == "On":
            self.parked_light.membervalue = "Idle"
            await self.mount_status_vector.send_setVector()
            self.unpark_switch.membervalue = "Off"
            await self.unpark_vector.send_setVector(state="Ok")

    async def hardware(self):
        if self.communicator and self.communicator.connected:
            await self.read_mount_position()
            # Check if slew is done
            # (Simplification: for now we just read position)

if __name__ == "__main__":
    driver = CelestronAUXDriver()
    asyncio.run(driver.asyncrun())
