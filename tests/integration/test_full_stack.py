import pytest
import asyncio
import time


@pytest.mark.asyncio
async def test_handshake_and_connect(indi_client):
    """Verifies INDI handshake and connection to the hardware (simulator)."""
    # 1. Handshake: Request properties
    await indi_client.send('<getProperties version="1.7" />')

    # Check if we receive the definition of CONNECTION property
    assert await indi_client.wait_for("defSwitchVector"), (
        "Did not receive defSwitchVector"
    )
    assert await indi_client.wait_for('device="Celestron AUX"'), "Device name mismatch"
    assert await indi_client.wait_for('name="CONNECTION"'), (
        "CONNECTION property not found"
    )

    # 2. Send Connect command
    indi_client.clear_buffer()
    connect_xml = (
        "<newSwitchVector device='Celestron AUX' name='CONNECTION'>\n"
        "  <oneSwitch name='CONNECT'>On</oneSwitch>\n"
        "</newSwitchVector>"
    )
    await indi_client.send(connect_xml)

    # 3. Wait for state="Ok" response for CONNECTION
    # Note: The driver should respond with a setSwitchVector
    assert await indi_client.wait_for("setSwitchVector"), (
        "Did not receive setSwitchVector"
    )
    assert await indi_client.wait_for('name="CONNECTION"'), (
        "CONNECTION property not in response"
    )
    assert await indi_client.wait_for('state="Ok"'), "Connection failed (state not Ok)"


@pytest.mark.asyncio
async def test_slew_and_abort(indi_client):
    """Verifies equatorial slew command and subsequent abort."""
    # 1. Connect first
    await indi_client.send('<getProperties version="1.7" />')
    await indi_client.send(
        "<newSwitchVector device='Celestron AUX' name='CONNECTION'>\n"
        "  <oneSwitch name='CONNECT'>On</oneSwitch>\n"
        "</newSwitchVector>"
    )
    assert await indi_client.wait_for('name="CONNECTION"'), "Failed to connect"
    assert await indi_client.wait_for('state="Ok"'), "Connection state not Ok"

    # 2. Initiate Slew
    indi_client.clear_buffer()
    slew_xml = (
        "<newNumberVector device='Celestron AUX' name='EQUATORIAL_EOD_COORD'>\n"
        "  <oneNumber name='RA'>10.0</oneNumber>\n"
        "  <oneNumber name='DEC'>20.0</oneNumber>\n"
        "</newNumberVector>"
    )
    await indi_client.send(slew_xml)

    # 3. Verify it becomes Busy
    assert await indi_client.wait_for('name="EQUATORIAL_EOD_COORD"'), (
        "Slew command not acknowledged"
    )
    assert await indi_client.wait_for('state="Busy"'), "Slew state not Busy"

    # 4. Initiate Abort
    # Don't clear buffer here, let's just wait for the specific response
    abort_xml = (
        "<newSwitchVector device='Celestron AUX' name='TELESCOPE_ABORT_MOTION'>\n"
        "  <oneSwitch name='ABORT'>On</oneSwitch>\n"
        "</newSwitchVector>"
    )
    await indi_client.send(abort_xml)

    # 5. Verify Abort acknowledged
    assert await indi_client.wait_for('name="TELESCOPE_ABORT_MOTION"'), (
        "Abort not acknowledged"
    )
    assert await indi_client.wait_for('state="Ok"'), "Abort state not Ok"

    # 6. Verify EQUATORIAL_EOD_COORD is no longer Busy
    # We wait specifically for the EOD coord update to Ok or Alert
    assert await indi_client.wait_for('name="EQUATORIAL_EOD_COORD"'), (
        "EOD Coord not updated after abort"
    )
    # Check that it's either Ok or Alert
    assert (
        'state="Ok"' in indi_client.buffer or 'state="Alert"' in indi_client.buffer
    ), "Slew state did not transition from Busy"


@pytest.mark.asyncio
async def test_tracking_mode(indi_client):
    """Verifies that enabling tracking mode updates mount status."""
    # 1. Connect
    await indi_client.send('<getProperties version="1.7" />')
    await indi_client.send(
        "<newSwitchVector device='Celestron AUX' name='CONNECTION'>\n"
        "  <oneSwitch name='CONNECT'>On</oneSwitch>\n"
        "</newSwitchVector>"
    )
    assert await indi_client.wait_for('name="CONNECTION"'), "Failed to connect"

    # 2. Enable Sidereal Tracking
    indi_client.clear_buffer()
    track_xml = (
        "<newSwitchVector device='Celestron AUX' name='TELESCOPE_TRACK_MODE'>\n"
        "  <oneSwitch name='TRACK_SIDEREAL'>On</oneSwitch>\n"
        "</newSwitchVector>"
    )
    await indi_client.send(track_xml)

    # 3. Verify Track Mode acknowledged
    assert await indi_client.wait_for('name="TELESCOPE_TRACK_MODE"'), (
        "Track mode not acknowledged"
    )
    assert await indi_client.wait_for('state="Ok"'), "Track mode state not Ok"

    # 4. Verify MOUNT_STATUS tracking light is Ok
    # The driver updates MOUNT_STATUS when tracking starts
    assert await indi_client.wait_for('name="MOUNT_STATUS"'), "Mount status not updated"
    assert await indi_client.wait_for("TRACKING"), "Tracking light not found"
    assert "Ok" in indi_client.buffer


@pytest.mark.asyncio
async def test_sync_alignment(indi_client):
    """Verifies that syncing the mount adds a point to the alignment model."""
    # 1. Connect
    await indi_client.send('<getProperties version="1.7" />')
    await indi_client.send(
        "<newSwitchVector device='Celestron AUX' name='CONNECTION'>\n"
        "  <oneSwitch name='CONNECT'>On</oneSwitch>\n"
        "</newSwitchVector>"
    )
    assert await indi_client.wait_for('name="CONNECTION"'), "Failed to connect"

    # 2. Set Coord Set Mode to SYNC
    sync_mode_xml = (
        "<newSwitchVector device='Celestron AUX' name='TELESCOPE_ON_COORD_SET'>\n"
        "  <oneSwitch name='SYNC'>On</oneSwitch>\n"
        "</newSwitchVector>"
    )
    await indi_client.send(sync_mode_xml)
    assert await indi_client.wait_for('name="TELESCOPE_ON_COORD_SET"'), (
        "Coord set mode not acknowledged"
    )

    # 3. Perform Sync
    indi_client.clear_buffer()
    sync_xml = (
        "<newNumberVector device='Celestron AUX' name='EQUATORIAL_EOD_COORD'>\n"
        "  <oneNumber name='RA'>5.0</oneNumber>\n"
        "  <oneNumber name='DEC'>10.0</oneNumber>\n"
        "</newNumberVector>"
    )
    await indi_client.send(sync_xml)

    # 4. Verify Sync acknowledged
    assert await indi_client.wait_for('name="EQUATORIAL_EOD_COORD"'), (
        "Sync not acknowledged"
    )
    assert await indi_client.wait_for('state="Ok"'), "Sync state not Ok"

    # 5. Verify ALIGNMENT_STATUS point count is 1
    # Note: POINT_COUNT is a Number member of ALIGNMENT_STATUS
    assert await indi_client.wait_for('name="ALIGNMENT_STATUS"'), (
        "Alignment status not updated"
    )
    assert await indi_client.wait_for("POINT_COUNT"), "POINT_COUNT member not found"
    assert "1" in indi_client.buffer
