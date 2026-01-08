"""
Celestron AUX Protocol Library

This module implements the binary communication protocol used by Celestron
telescope mounts via the AUX bus. It provides classes for command creation,
parsing, and asynchronous communication over Serial or TCP.

References:
    - NexStar AUX Command Set documentation
    - indi-celestronaux C++ implementation
"""

import struct
import time
import asyncio
import serial_asyncio
from enum import Enum


class AUXCommands(Enum):
    """Enumeration of Celestron AUX bus commands."""

    MC_GET_POSITION = 0x01
    MC_GOTO_FAST = 0x02
    MC_SET_POSITION = 0x04
    MC_GET_MODEL = 0x05
    MC_SET_POS_GUIDERATE = 0x06
    MC_SET_NEG_GUIDERATE = 0x07
    MC_LEVEL_START = 0x0B
    MC_LEVEL_DONE = 0x12
    MC_SLEW_DONE = 0x13
    MC_GOTO_SLOW = 0x17
    MC_SEEK_DONE = 0x18
    MC_SEEK_INDEX = 0x19
    MC_MOVE_POS = 0x24
    MC_MOVE_NEG = 0x25
    MC_AUX_GUIDE = 0x26
    MC_AUX_GUIDE_ACTIVE = 0x27
    MC_ENABLE_CORDWRAP = 0x38
    MC_DISABLE_CORDWRAP = 0x39
    MC_SET_CORDWRAP_POS = 0x3A
    MC_POLL_CORDWRAP = 0x3B
    MC_GET_CORDWRAP_POS = 0x3C
    MC_SET_AUTOGUIDE_RATE = 0x46
    MC_GET_AUTOGUIDE_RATE = 0x47
    GET_VER = 0xFE
    GPS_GET_LAT = 0x01
    GPS_GET_LONG = 0x02
    GPS_SET_LAT = 0x31
    GPS_SET_LONG = 0x32
    GPS_SET_TIME = 0x34
    GPS_GET_TIME = 0x33
    GPS_SET_DATE = 0x3C
    GPS_GET_DATE = 0x3B
    GPS_TIME_VALID = 0x36
    GPS_LINKED = 0x37
    GPS_GET_SATS = 0x38
    FOC_GET_HS_POSITIONS = 0x2C

    # Power/Battery
    PWR_GET_VOLTAGE = 0x01
    PWR_GET_CURRENT = 0x02
    PWR_GET_STATUS = 0x03


class AUXTargets(Enum):
    """Enumeration of devices on the AUX bus."""

    ANY = 0x00
    MB = 0x01  # Main Board
    HC = 0x04  # Hand Controller
    HCP = 0x0D  # Hand Controller Plus?
    AZM = 0x10  # Azimuth / RA Motor
    ALT = 0x11  # Altitude / Dec Motor
    FOCUS = 0x12  # Focuser
    APP = 0x20  # Software Application
    GPS = 0xB0  # GPS Module
    WiFi = 0xB5  # WiFi Module
    BAT = 0xB6  # Battery
    CHG = 0xB7  # Charger
    LIGHT = 0xBF  # Lighting (Evolution)


class AUXCommand:
    """
    Represents a single Celestron AUX bus command packet.

    Attributes:
        command (AUXCommands): The command to execute.
        source (AUXTargets): The sender of the command.
        destination (AUXTargets): The target device.
        data (bytes): Optional payload.
        length (int): Length of (source + destination + command + data).
    """

    START_BYTE = 0x3B
    MAX_CMD_LEN = 32

    def __init__(
        self,
        command: AUXCommands,
        source: AUXTargets,
        destination: AUXTargets,
        data: bytes = b"",
    ):
        self.command = command
        self.source = source
        self.destination = destination
        self.data = data
        self.length = 3 + len(self.data)

    def fill_buf(self) -> bytes:
        """
        Serializes the command into a byte buffer for transmission.

        Returns:
            bytes: The complete packet (START | LEN | SRC | DST | CMD | DATA... | CS).
        """
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
        """
        Parses a byte buffer into an AUXCommand object.

        Args:
            buf (bytes): Received bytes.

        Returns:
            AUXCommand: The parsed command object.

        Raises:
            ValueError: If the start byte is invalid or buffer is too short.
        """
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
            # We log but continue, as some mounts have flaky checksums
            print(
                f"Checksum error: Expected {calculated_checksum:02X}, Got {checksum:02X} for buffer {buf.hex()}"
            )

        cmd = cls(command, source, destination, data)
        cmd.length = length
        return cmd

    @staticmethod
    def _calculate_checksum(data) -> int:
        """
        Calculates the AUX checksum (2's complement of sum).

        Args:
            data (bytes/bytearray): Data to checksum.

        Returns:
            int: 8-bit checksum value.
        """
        cs = sum(data)
        return ((~cs) + 1) & 0xFF

    def get_data_as_int(self) -> int:
        """
        Converts command data bytes to a big-endian integer.

        Returns:
            int: The integer value of the payload.
        """
        value = 0
        if len(self.data) == 3:
            value = (self.data[0] << 16) | (self.data[1] << 8) | self.data[2]
        elif len(self.data) == 2:
            value = (self.data[0] << 8) | self.data[1]
        elif len(self.data) == 1:
            value = self.data[0]
        return value

    def set_data_from_int(self, value: int, num_bytes: int):
        """
        Sets the command data payload from an integer.

        Args:
            value (int): The integer value.
            num_bytes (int): Number of bytes to use (1, 2, or 3).
        """
        if num_bytes == 1:
            self.data = value.to_bytes(1, "big")
        elif num_bytes == 2:
            self.data = value.to_bytes(2, "big")
        elif num_bytes == 3:
            self.data = value.to_bytes(3, "big")
        else:
            raise ValueError("num_bytes must be 1, 2, or 3")
        self.length = 3 + len(self.data)

    def __repr__(self):
        return f"AUXCommand(cmd={self.command.name}, src={self.source.name}, dst={self.destination.name}, data={self.data.hex()}, len={self.length})"


def unpack_int3_steps(d: bytes) -> int:
    """
    Unpacks 3 bytes into a 24-bit unsigned integer (encoder steps).

    Args:
        d (bytes): 3 bytes of data.

    Returns:
        int: Encoder steps.
    """
    if len(d) != 3:
        raise ValueError("Input bytes must be 3 bytes long for unpack_int3_steps")
    return int.from_bytes(d, "big", signed=False)


def pack_int3_steps(val: int) -> bytes:
    """
    Packs an integer into 3 big-endian bytes.

    Args:
        val (int): Integer to pack (0 to 2^24 - 1).

    Returns:
        bytes: 3 bytes of data.
    """
    if not 0 <= val < 2**24:
        raise ValueError("Value out of range for 3-byte unsigned integer")
    return val.to_bytes(3, "big", signed=False)


# Constants for encoder calculations
STEPS_PER_REVOLUTION = 16777216
STEPS_PER_DEGREE = STEPS_PER_REVOLUTION / 360.0
STEPS_PER_ARCSEC = STEPS_PER_DEGREE / 3600.0
DEGREES_PER_STEP = 360.0 / STEPS_PER_REVOLUTION


class AUXCommunicator:
    """
    Handles asynchronous communication with the AUX bus.

    Supports Serial (via pyserial-asyncio) and TCP (via socket:// prefix).
    Implements echo-skipping for one-wire bus environments.

    Attributes:
        port (str): Device path (e.g. /dev/ttyUSB0) or URL (socket://host:port).
        baudrate (int): Communication speed (default 19200).
        timeout (float): Read timeout in seconds.
    """

    def __init__(self, port: str, baudrate: int = 19200, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.reader = None
        self.writer = None
        self.connected = False
        self.lock = asyncio.Lock()

    async def connect(self) -> bool:
        """
        Establishes connection to the AUX bus.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            if self.port.startswith("socket://"):
                host, port = self.port[9:].split(":")
                self.reader, self.writer = await asyncio.open_connection(
                    host, int(port)
                )
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
        """Closes the connection."""
        if self.writer and self.connected:
            self.writer.close()
            await self.writer.wait_closed()
            self.connected = False
            print(f"Communicator: Disconnected from {self.port}")

    async def send_command(self, command: AUXCommand) -> AUXCommand | None:
        """
        Sends an AUX command and waits for a response.

        Implements echo skipping: if the received packet matches the sent one
        (common on AUX bus), it is ignored, and the next packet is read.

        Args:
            command (AUXCommand): Command to send.

        Returns:
            AUXCommand: The response packet, or None on failure/timeout.
        """
        if not self.connected or not self.writer:
            return None

        async with self.lock:
            tx_buf = command.fill_buf()
            try:
                self.writer.write(tx_buf)
                await self.writer.drain()

                while True:
                    # 1. Wait for Start Byte
                    start_byte = await asyncio.wait_for(
                        self.reader.readexactly(1), timeout=self.timeout
                    )
                    if start_byte[0] != AUXCommand.START_BYTE:
                        continue

                    # 2. Read Length
                    length_byte = await asyncio.wait_for(
                        self.reader.readexactly(1), timeout=self.timeout
                    )
                    response_length = length_byte[0]

                    # 3. Read payload + Checksum
                    remaining_bytes = await asyncio.wait_for(
                        self.reader.readexactly(response_length + 1),
                        timeout=self.timeout,
                    )

                    rx_buf = start_byte + length_byte + remaining_bytes
                    resp = AUXCommand.parse_buf(rx_buf)

                    # 4. Skip Echo
                    if (
                        resp.source == command.source
                        and resp.destination == command.destination
                        and resp.command == command.command
                    ):
                        continue
                    return resp
            except Exception as e:
                print(f"Communicator: Error in send_command: {type(e).__name__}: {e}")
                return None
