import time
import asyncio
import serial_asyncio
from enum import Enum

from indipydriver import IPyDriver, INDIProperty, ISwitch, IText, INumber, ILight, ISState, IPState

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
    MAX_CMD_LEN = 32 # From auxproto.cpp

    def __init__(self, command: AUXCommands, source: AUXTargets, destination: AUXTargets, data: bytes = b''):
        self.command = command
        self.source = source
        self.destination = destination
        self.data = data
        self.length = 3 + len(self.data) # source + destination + command + data_len

    def fill_buf(self) -> bytes:
        # Message structure: START_BYTE | len | source | destination | command | data... | checksum
        buf = bytearray()
        buf.append(self.START_BYTE)
        buf.append(self.length)
        buf.append(self.source.value)
        buf.append(self.destination.value)
        buf.append(self.command.value)
        buf.extend(self.data)
        buf.append(self._calculate_checksum(buf[1:])) # Checksum is calculated from len byte onwards
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
            # For now, just print, might need to handle gracefully
            # raise ValueError("Checksum mismatch")

        cmd = cls(command, source, destination, data)
        cmd.length = length # Ensure parsed length matches
        return cmd

    @staticmethod
    def _calculate_checksum(data: bytes) -> int:
        cs = sum(data)
        return ((~cs) + 1) & 0xFF

    def get_data_as_int(self) -> int:
        # Corresponds to getData() in C++ auxproto.cpp
        value = 0
        if len(self.data) == 3:
            value = (self.data[0] << 16) | (self.data[1] << 8) | self.data[2]
        elif len(self.data) == 2:
            value = (self.data[0] << 8) | self.data[1]
        elif len(self.data) == 1:
            value = self.data[0]
        return value

    def set_data_from_int(self, value: int, num_bytes: int):
        # Corresponds to setData() in C++ auxproto.cpp
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

# Helper functions for packing/unpacking 3-byte integers (steps), similar to nse_telescope.py
def unpack_int3_steps(d: bytes) -> int:
    # Converts 3 bytes to an integer value (representing steps)
    if len(d) != 3:
        raise ValueError("Input bytes must be 3 bytes long for unpack_int3_steps")
    # Celestron uses unsigned 24-bit values for positions
    val = int.from_bytes(d, 'big', signed=False)
    return val

def pack_int3_steps(val: int) -> bytes:
    # Converts an integer value (steps) to 3 bytes
    if not 0 <= val < 2**24: # Ensure it fits in 24 bits
        raise ValueError("Value out of range for 3-byte unsigned integer")
    return val.to_bytes(3, 'big', signed=False)

# Constants from celestronaux.h
STEPS_PER_REVOLUTION = 16777216
STEPS_PER_DEGREE = STEPS_PER_REVOLUTION / 360.0
STEPS_PER_ARCSEC = STEPS_PER_DEGREE / 3600.0
DEGREES_PER_STEP = 360.0 / STEPS_PER_REVOLUTION

# Communication class
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
            self.reader, self.writer = await serial_asyncio.open_serial_connection(
                url=self.port, baudrate=self.baudrate, timeout=self.timeout
            )
            self.connected = True
            print(f"Communicator: Connected to {self.port} at {self.baudrate} baud.")
            return True
        except serial_asyncio.SerialException as e:
            print(f"Communicator: Error connecting to serial port: {e}")
            self.connected = False
            return False
        except Exception as e:
            print(f"Communicator: An unexpected error occurred during connection: {e}")
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
            print("Communicator: Not connected.")
            return None

        tx_buf = command.fill_buf()
        print(f"Communicator: Sending: {tx_buf.hex()}")
        try:
            self.writer.write(tx_buf)
            await self.writer.drain()

            # Read response
            # A more robust solution would involve knowing the expected response length for each command.
            # For now, we'll read the start byte, length, and then the rest.
            
            # Read the start byte (0x3b)
            start_byte = await asyncio.wait_for(self.reader.readexactly(1), timeout=self.timeout)
            if start_byte[0] != AUXCommand.START_BYTE:
                print(f"Communicator: Received unexpected start byte: {start_byte.hex()}")
                return None

            # Read length byte
            length_byte = await asyncio.wait_for(self.reader.readexactly(1), timeout=self.timeout)
            response_length = length_byte[0]

            # Read the rest of the message (source, dest, cmd, data, checksum)
            # Total bytes to read = response_length (which includes source, dest, cmd, data) + 1 (for checksum)
            # So, we already read 1 byte (start_byte) and 1 byte (length_byte)
            # Remaining bytes = response_length + 1 - 2 = response_length - 1
            remaining_bytes = await asyncio.wait_for(self.reader.readexactly(response_length - 1), timeout=self.timeout)

            rx_buf = start_byte + length_byte + remaining_bytes
            print(f"Communicator: Received: {rx_buf.hex()}")
            return AUXCommand.parse_buf(rx_buf)
        except asyncio.TimeoutError:
            print("Communicator: Read timeout.")
            return None
        except Exception as e:
            print(f"Communicator: Error during send/receive: {e}")
            return None

class CelestronAUXDriver(IPyDriver):
    def __init__(self, driver_name: str = "Celestron AUX"):
        super().__init__(driver_name)
        self.communicator = None
        self.port_name = "/dev/ttyUSB0" # Default serial port
        self.baud_rate = 19200

        # INDI Properties (simplified for now, will expand)
        self.connection_property = INDIProperty(
            "CONNECTION", "Connection", "Main", IPState.IDLE,
            [
                ISwitch("CONNECT", "Connect", ISState.OFF),
                ISwitch("DISCONNECT", "Disconnect", ISState.ON)
            ],
            self.set_connection
        )
        self.add_property(self.connection_property)

        self.port_property = INDIProperty(
            "PORT", "Serial Port", "Main", IPState.IDLE,
            [
                IText("PORT_NAME", "Port Name", self.port_name),
                INumber("BAUD_RATE", "Baud Rate", self.baud_rate, 9600, 115200, 1, 1)
            ],
            self.set_port_settings
        )
        self.add_property(self.port_property)

        self.firmware_property = INDIProperty(
            "FIRMWARE_INFO", "Firmware Info", "Main", IPState.IDLE,
            [
                IText("MODEL", "Model", "Unknown"),
                IText("HC_VERSION", "HC Version", "Unknown"),
                IText("AZM_VERSION", "AZM Version", "Unknown"),
                IText("ALT_VERSION", "ALT Version", "Unknown"),
            ]
        )
        self.add_property(self.firmware_property)

        self.mount_position_property = INDIProperty(
            "MOUNT_POSITION", "Mount Position", "Main", IPState.IDLE,
            [
                INumber("AZM_STEPS", "AZM Steps", 0, 0, STEPS_PER_REVOLUTION - 1, 1, 0),
                INumber("ALT_STEPS", "ALT Steps", 0, 0, STEPS_PER_REVOLUTION - 1, 1, 0),
            ]
        )
        self.add_property(self.mount_position_property)

        self.mount_status_property = INDIProperty(
            "MOUNT_STATUS", "Mount Status", "Main", IPState.IDLE,
            [
                ILight("SLEWING", "Slewing", ISState.OFF),
                ILight("TRACKING", "Tracking", ISState.OFF),
                ILight("PARKED", "Parked", ISState.OFF),
            ]
        )
        self.add_property(self.mount_status_property)

        self.current_azm_steps = 0
        self.current_alt_steps = 0
        self.current_slew_rate = 1 # Default slew rate

        self.slew_rate_property = INDIProperty(
            "SLEW_RATE", "Slew Rate", "Main", IPState.IDLE,
            [
                INumber("RATE", "Rate (1-9)", self.current_slew_rate, 1, 9, 1, 1)
            ],
            self.set_slew_rate
        )
        self.add_property(self.slew_rate_property)

        self.motion_ns_property = INDIProperty(
            "TELESCOPE_MOTION_NS", "Motion N/S", "Main", IPState.IDLE,
            [
                ISwitch("MOTION_N", "North", ISState.OFF),
                ISwitch("MOTION_S", "South", ISState.OFF)
            ],
            self.move_ns
        )
        self.add_property(self.motion_ns_property)

        self.motion_we_property = INDIProperty(
            "TELESCOPE_MOTION_WE", "Motion W/E", "Main", IPState.IDLE,
            [
                ISwitch("MOTION_W", "West", ISState.OFF),
                ISwitch("MOTION_E", "East", ISState.OFF)
            ],
            self.move_we
        )
        self.add_property(self.motion_we_property)

        self.absolute_coord_property = INDIProperty(
            "TELESCOPE_ABSOLUTE_COORD", "Absolute Coordinates", "Main", IPState.IDLE,
            [
                INumber("AZM_STEPS", "AZM Steps", 0, 0, STEPS_PER_REVOLUTION - 1, 1, 0),
                INumber("ALT_STEPS", "ALT Steps", 0, 0, STEPS_PER_REVOLUTION - 1, 1, 0),
            ],
            self.set_absolute_coord
        )
        self.add_property(self.absolute_coord_property)

        self.sync_property = INDIProperty(
            "TELESCOPE_SYNC", "Sync Mount", "Main", IPState.IDLE,
            [
                ISwitch("SYNC", "Sync", ISState.OFF)
            ],
            self.sync_mount
        )
        self.add_property(self.sync_property)

        self.park_property = INDIProperty(
            "TELESCOPE_PARK", "Park Mount", "Main", IPState.IDLE,
            [
                ISwitch("PARK", "Park", ISState.OFF)
            ],
            self.park_mount
        )
        self.add_property(self.park_property)

        self.unpark_property = INDIProperty(
            "TELESCOPE_UNPARK", "Unpark Mount", "Main", IPState.IDLE,
            [
                ISwitch("UNPARK", "Unpark", ISState.OFF)
            ],
            self.unpark_mount
        )
        self.add_property(self.unpark_property)

    async def slew_by_rate(self, axis: AUXTargets, rate: int, direction: int) -> bool:
        # direction: 1 for positive (MC_MOVE_POS), -1 for negative (MC_MOVE_NEG)
        if not 0 <= rate <= 9:
            print(f"Invalid slew rate: {rate}. Must be between 0 and 9.")
            return False

        command_type = AUXCommands.MC_MOVE_POS if direction == 1 else AUXCommands.MC_MOVE_NEG
        data = rate.to_bytes(1, 'big')
        slew_cmd = AUXCommand(command_type, AUXTargets.APP, axis, data)
        response = await self.communicator.send_command(slew_cmd)
        if response:
            if rate > 0:
                self.mount_status_property.get_light("SLEWING").s = ISState.ON
            else:
                # If rate is 0, it means stop. Check if other axis is still slewing.
                # For simplicity, we'll just set SLEWING to OFF for now.
                self.mount_status_property.get_light("SLEWING").s = ISState.OFF
            self.update_property(self.mount_status_property)
            return True
        return False

    async def slew_to(self, axis: AUXTargets, steps: int, fast: bool = True) -> bool:
        command_type = AUXCommands.MC_GOTO_FAST if fast else AUXCommands.MC_GOTO_SLOW
        data = pack_int3_steps(steps)
        slew_cmd = AUXCommand(command_type, AUXTargets.APP, axis, data)
        response = await self.communicator.send_command(slew_cmd)
        if response:
            self.mount_status_property.get_light("SLEWING").s = ISState.ON
            self.update_property(self.mount_status_property)
            return True
        return False

    async def stop_axis(self, axis: AUXTargets) -> bool:
        return await self.slew_by_rate(axis, 0, 1) # Rate 0 stops movement

    async def set_absolute_coord(self, property: INDIProperty):
        azm_steps = int(property.get_number("AZM_STEPS").value)
        alt_steps = int(property.get_number("ALT_STEPS").value)

        property.set_state(IPState.BUSY)
        self.update_property(property)

        azm_slew_success = await self.slew_to(AUXTargets.AZM, azm_steps)
        alt_slew_success = await self.slew_to(AUXTargets.ALT, alt_steps)

        if azm_slew_success and alt_slew_success:
            property.set_state(IPState.OK)
        else:
            property.set_state(IPState.ALERT)
        self.update_property(property)

    async def sync_mount(self, property: INDIProperty):
        if property.get_switch("SYNC").s == ISState.ON:
            property.set_state(IPState.BUSY)
            self.update_property(property)

            # Send MC_SET_POSITION for both axes with current steps
            azm_set_pos_cmd = AUXCommand(AUXCommands.MC_SET_POSITION, AUXTargets.APP, AUXTargets.AZM, pack_int3_steps(self.current_azm_steps))
            alt_set_pos_cmd = AUXCommand(AUXCommands.MC_SET_POSITION, AUXTargets.APP, AUXTargets.ALT, pack_int3_steps(self.current_alt_steps))

            azm_success = await self.communicator.send_command(azm_set_pos_cmd)
            alt_success = await self.communicator.send_command(alt_set_pos_cmd)

            if azm_success and alt_success:
                property.set_state(IPState.OK)
            else:
                property.set_state(IPState.ALERT)
            
            # Reset the switch
            property.get_switch("SYNC").s = ISState.OFF
            self.update_property(property)

    async def park_mount(self, property: INDIProperty):
        if property.get_switch("PARK").s == ISState.ON:
            property.set_state(IPState.BUSY)
            self.update_property(property)

            # For simplicity, park to 0,0 steps
            azm_park_success = await self.slew_to(AUXTargets.AZM, 0)
            alt_park_success = await self.slew_to(AUXTargets.ALT, 0)

            if azm_park_success and alt_park_success:
                self.mount_status_property.get_light("PARKED").s = ISState.ON
                self.update_property(self.mount_status_property)
                property.set_state(IPState.OK)
            else:
                property.set_state(IPState.ALERT)
            
            # Reset the switch
            property.get_switch("PARK").s = ISState.OFF
            self.update_property(property)

    async def unpark_mount(self, property: INDIProperty):
        if property.get_switch("UNPARK").s == ISState.ON:
            property.set_state(IPState.BUSY)
            self.update_property(property)

            self.mount_status_property.get_light("PARKED").s = ISState.OFF
            self.update_property(self.mount_status_property)
            property.set_state(IPState.OK)
            
            # Reset the switch
            property.get_switch("UNPARK").s = ISState.OFF
            self.update_property(property)

    async def set_slew_rate(self, property: INDIProperty):
        self.current_slew_rate = int(property.get_number("RATE").value)
        self.slew_rate_property.set_state(IPState.OK)
        self.update_property(self.slew_rate_property)

    async def move_ns(self, property: INDIProperty):
        slew_rate = self.current_slew_rate
        if property.get_switch("MOTION_N").s == ISState.ON:
            await self.slew_by_rate(AUXTargets.ALT, slew_rate, 1) # North is positive ALT
        elif property.get_switch("MOTION_S").s == ISState.ON:
            await self.slew_by_rate(AUXTargets.ALT, slew_rate, -1) # South is negative ALT
        else:
            await self.stop_axis(AUXTargets.ALT)
        self.motion_ns_property.set_state(IPState.OK)
        self.update_property(self.motion_ns_property)

    async def move_we(self, property: INDIProperty):
        slew_rate = self.current_slew_rate
        if property.get_switch("MOTION_W").s == ISState.ON:
            await self.slew_by_rate(AUXTargets.AZM, slew_rate, -1) # West is negative AZM
        elif property.get_switch("MOTION_E").s == ISState.ON:
            await self.slew_by_rate(AUXTargets.AZM, slew_rate, 1) # East is positive AZM
        else:
            await self.stop_axis(AUXTargets.AZM)
        self.motion_we_property.set_state(IPState.OK)
        self.update_property(self.motion_we_property)

    async def set_connection(self, property: INDIProperty):
        if property.get_switch("CONNECT").s == ISState.ON:
            self.port_name = self.port_property.get_text("PORT_NAME").value
            self.baud_rate = int(self.port_property.get_number("BAUD_RATE").value)
            self.communicator = AUXCommunicator(self.port_name, self.baud_rate)
            if await self.communicator.connect():
                self.connection_property.set_state(IPState.OK)
                self.connection_property.get_switch("CONNECT").s = ISState.ON
                self.connection_property.get_switch("DISCONNECT").s = ISState.OFF
                self.update_property(self.connection_property)
                await self.get_firmware_info()
                await self.read_mount_position()
            else:
                self.connection_property.set_state(IPState.ALERT)
                self.connection_property.get_switch("CONNECT").s = ISState.OFF
                self.connection_property.get_switch("DISCONNECT").s = ISState.ON
                self.update_property(self.connection_property)
        else: # DISCONNECT is ON
            if self.communicator:
                await self.communicator.disconnect()
            self.connection_property.set_state(IPState.IDLE)
            self.connection_property.get_switch("CONNECT").s = ISState.OFF
            self.connection_property.get_switch("DISCONNECT").s = ISState.ON
            self.update_property(self.connection_property)

    async def set_port_settings(self, property: INDIProperty):
        self.port_name = property.get_text("PORT_NAME").value
        self.baud_rate = int(property.get_number("BAUD_RATE").value)
        self.port_property.set_state(IPState.OK)
        self.update_property(self.port_property)

    async def get_firmware_info(self):
        self.firmware_property.set_state(IPState.BUSY)
        self.update_property(self.firmware_property)

        # Get Model (for AZM)
        model_cmd = AUXCommand(AUXCommands.MC_GET_MODEL, AUXTargets.APP, AUXTargets.AZM)
        response = await self.communicator.send_command(model_cmd)
        if response and response.data:
            model_id = response.get_data_as_int()
            # This mapping is from celestronaux.cpp formatModelString
            model_map = {
                0x0001: "Nexstar GPS", 0x0783: "Nexstar SLT", 0x0b83: "4/5SE",
                0x0c82: "6/8SE", 0x1189: "CPC Deluxe", 0x1283: "GT Series",
                0x1485: "AVX", 0x1687: "Nexstar Evolution", 0x1788: "CGX"
            }
            self.firmware_property.get_text("MODEL").value = model_map.get(model_id, f"Unknown (0x{model_id:04X})")
        else:
            self.firmware_property.get_text("MODEL").value = "Failed to get model"

        # Get Version for AZM
        azm_ver_cmd = AUXCommand(AUXCommands.GET_VER, AUXTargets.APP, AUXTargets.AZM)
        response = await self.communicator.send_command(azm_ver_cmd)
        if response and response.data and len(response.data) == 4:
            self.firmware_property.get_text("AZM_VERSION").value = f"{response.data[0]}.{response.data[1]}.{response.data[2]*256 + response.data[3]}"
        else:
            self.firmware_property.get_text("AZM_VERSION").value = "Failed"

        # Get Version for ALT
        alt_ver_cmd = AUXCommand(AUXCommands.GET_VER, AUXTargets.APP, AUXTargets.ALT)
        response = await self.communicator.send_command(alt_ver_cmd)
        if response and response.data and len(response.data) == 4:
            self.firmware_property.get_text("ALT_VERSION").value = f"{response.data[0]}.{response.data[1]}.{response.data[2]*256 + response.data[3]}"
        else:
            self.firmware_property.get_text("ALT_VERSION").value = "Failed"
        
        # Get Version for HC (Hand Controller)
        hc_ver_cmd = AUXCommand(AUXCommands.GET_VER, AUXTargets.APP, AUXTargets.HC)
        response = await self.communicator.send_command(hc_ver_cmd)
        if response and response.data and len(response.data) == 4:
            self.firmware_property.get_text("HC_VERSION").value = f"{response.data[0]}.{response.data[1]}.{response.data[2]*256 + response.data[3]}"
        else:
            self.firmware_property.get_text("HC_VERSION").value = "Failed"

        self.firmware_property.set_state(IPState.OK)
        self.update_property(self.firmware_property)

    async def read_mount_position(self):
        if not self.communicator or not self.communicator.connected:
            return

        self.mount_position_property.set_state(IPState.BUSY)
        self.update_property(self.mount_position_property)

        # Get AZM position
        azm_pos_cmd = AUXCommand(AUXCommands.MC_GET_POSITION, AUXTargets.APP, AUXTargets.AZM)
        response = await self.communicator.send_command(azm_pos_cmd)
        if response and response.data and len(response.data) == 3:
            self.current_azm_steps = unpack_int3(response.data)
            self.mount_position_property.get_number("AZM_STEPS").value = self.current_azm_steps
        else:
            print("Failed to get AZM position")
            self.mount_position_property.set_state(IPState.ALERT)
            self.update_property(self.mount_position_property)
            return

        # Get ALT position
        alt_pos_cmd = AUXCommand(AUXCommands.MC_GET_POSITION, AUXTargets.APP, AUXTargets.ALT)
        response = await self.communicator.send_command(alt_pos_cmd)
        if response and response.data and len(response.data) == 3:
            self.current_alt_steps = unpack_int3(response.data)
            self.mount_position_property.get_number("ALT_STEPS").value = self.current_alt_steps
        else:
            print("Failed to get ALT position")
            self.mount_position_property.set_state(IPState.ALERT)
            self.update_property(self.mount_position_property)
            return

        self.mount_position_property.set_state(IPState.OK)
        self.update_property(self.mount_position_property)

    async def rxevent(self, property: INDIProperty):
        if property.name == self.connection_property.name:
            await self.set_connection(property)
        elif property.name == self.port_property.name:
            await self.set_port_settings(property)
        elif property.name == self.slew_rate_property.name:
            await self.set_slew_rate(property)
        elif property.name == self.motion_ns_property.name:
            await self.move_ns(property)
        elif property.name == self.motion_we_property.name:
            await self.move_we(property)
        elif property.name == self.absolute_coord_property.name:
            await self.set_absolute_coord(property)
        elif property.name == self.sync_property.name:
            await self.sync_mount(property)
        elif property.name == self.park_property.name:
            await self.park_mount(property)
        elif property.name == self.unpark_property.name:
            await self.unpark_mount(property)
        # Add more handlers for other properties as they are implemented

    async def hardware(self):
        # This method is called periodically by indipydriver
        if self.communicator and self.communicator.connected:
            await self.read_mount_position()
            # Add other periodic updates here (e.g., mount status, tracking)

# To run the driver
if __name__ == "__main__":
    driver = CelestronAUXDriver()
    asyncio.run(driver.start())
