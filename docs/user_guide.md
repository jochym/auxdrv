# User Guide

This driver provides control over Celestron telescope mounts using the AUX protocol. It is compatible with INDI clients like KStars, Ekos, and Stellarium.

## Connection

- **Port**: Serial port path (e.g., `/dev/ttyUSB0`) or network address (e.g., `socket://192.168.1.100:2000`).
- **Baud Rate**: Usually `19200` (9600 via Hand Controller).

## Operation

### Motion Control
- **Slew Rate**: Select speeds 1-9.
- **Directional Buttons**: Move the mount manually in N/S/E/W directions.

### GoTo and Tracking
- **Sidereal Tracking**: Used for stars and deep-sky objects.
- **Moving Objects**: Support for Sun, Moon, Planets, and Satellites (via TLE).
- **Anti-Backlash**: Approach logic to reduce mechanical slack.

## Safety Features

- **Slew Limits**: Configurable altitude limits via `TELESCOPE_LIMITS`.
- **Cord Wrap**: Prevents rotation beyond 360 degrees to protect cables.
- **Abort Motion**: `TELESCOPE_ABORT_MOTION` stops both axes.

## Features

### Predictive Tracking
The driver uses a predictive algorithm to calculate the velocity of objects. This is used to maintain tracking for moving targets or during atmospheric refraction changes.

### Accessory Support
- **Focuser**: Support for Celestron AUX focusers.
- **GPS**: Location and time sync from GPS modules.
- **RTC**: Reading and writing Real-Time Clock data.
- **Power**: Voltage and current telemetry for battery-equipped mounts.
