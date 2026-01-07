# Celestron AUX INDI Driver - User Manual

This driver provides full control over Celestron telescope mounts using the AUX binary protocol. It is compatible with INDI-enabled clients like KStars, Ekos, and Stellarium.

## Installation

1.  Ensure you have Python 3.8+ installed.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Connect your mount via USB-Serial adapter or TCP bridge.

## Configuration

### Connection
- **Port**: Serial port path (e.g., `/dev/ttyUSB0`) or network address (e.g., `socket://192.168.1.100:2000`).
- **Baud Rate**: Usually `19200` for Celestron AUX.

### Site Settings
Ensure your **Latitude**, **Longitude**, and **Elevation** are correct in the `Site` tab. These are essential for accurate RA/Dec to Alt/Az conversions.

## Operation

### Motion Control
- **Slew Rate**: Select speeds 1-9.
- **Directional Buttons**: Move the mount manually in N/S/E/W directions.

### GoTo and Tracking
- **Sidereal Tracking**: Default for stars and deep-sky objects.
- **Moving Objects**: Support for Sun, Moon, Planets, and Satellites (via TLE).
- **Anti-Backlash**: High-precision GoTo approach to eliminate mechanical slack.

### Safety Features
- **Slew Limits**: Configure maximum and minimum altitude to prevent equipment collisions.
- **Cord Wrap**: Prevents the mount from rotating more than 360 degrees in azimuth to protect cables.

### Alignment
Refer to the [Alignment System Guide](ALIGNMENT_SYSTEM.md) for detailed instructions on multi-point star calibration.

## Advanced Features

### Predictive Tracking (2nd Order)
The driver uses a sophisticated predictive algorithm to calculate the instantaneous velocity of objects. This ensures smooth tracking even for fast-moving targets like the ISS or during atmospheric refraction changes.

### Accessory Support
- **Focuser**: Full control of Celestron AUX focusers.
- **GPS**: Automatic location and time sync from Celestron GPS modules.
