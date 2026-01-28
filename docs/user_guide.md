# User Guide

This driver provides full control over Celestron telescope mounts using the AUX binary protocol. It is compatible with INDI-enabled clients like KStars, Ekos, and Stellarium.

## Connection

- **Port**: Serial port path (e.g., `/dev/ttyUSB0`) or network address (e.g., `socket://192.168.1.100:2000`).
- **Baud Rate**: Usually `19200` for Celestron AUX (9600 via Hand Controller).

## Operation

### Motion Control
- **Slew Rate**: Select speeds 1-9 (Guide, Centering, Find, Max).
- **Directional Buttons**: Move the mount manually in N/S/E/W directions.

### GoTo and Tracking
- **Sidereal Tracking**: Default for stars and deep-sky objects.
- **Moving Objects**: Support for Sun, Moon, Planets, and Satellites (via TLE).
- **Anti-Backlash**: High-precision GoTo approach to eliminate mechanical slack.

## Safety Features

- **Slew Limits**: Configure maximum and minimum altitude in the `TELESCOPE_LIMITS` property to prevent equipment collisions.
- **Cord Wrap**: Prevents the mount from rotating more than 360 degrees in azimuth to protect cables.
- **Abort Motion**: The `TELESCOPE_ABORT_MOTION` command sends an immediate stop signal to both axes.

## Advanced Features

### Predictive Tracking (2nd Order)
The driver uses a sophisticated predictive algorithm to calculate the instantaneous velocity of objects. This ensures smooth tracking even for fast-moving targets like the ISS or during atmospheric refraction changes.

### Accessory Support
- **Focuser**: Full control of Celestron AUX focusers.
- **GPS**: Automatic location and time sync from Celestron GPS modules.
- **RTC**: Support for reading and writing Real-Time Clock data to the mount.
- **Power**: Voltage and current telemetry (for Evolution battery modules).
