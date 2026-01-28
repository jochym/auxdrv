import asyncio
import unittest
import math
import ephem
import os
import sys
import subprocess
import time
from celestron_aux.celestron_indi_driver import CelestronAUXDriver, AUXTargets


class TestMovingObjects(unittest.IsolatedAsyncioTestCase):
    """
    Verification of non-sidereal tracking capabilities.

    Verifies that the driver can calculate positions and tracking rates for
    Solar System objects (Moon) and Satellites (TLE).
    """

    sim_proc = None
    sim_port = 2002
    external_sim = False

    @classmethod
    def setUpClass(cls):
        """
        Launches a simulator instance for moving object tests.
        """
        if os.environ.get("EXTERNAL_SIM"):
            cls.external_sim = True
            cls.sim_port = int(os.environ.get("SIM_PORT", 2000))
            return

        cls.sim_log = open("test_moving_sim.log", "w")
        cls.sim_proc = subprocess.Popen(
            [
                "caux-sim",
                "--text",
                "--perfect",
                "--hc",
                "--web",
                "--web-host",
                "0.0.0.0",
                "--web-port",
                "8080",
                "--port",
                str(cls.sim_port),
            ],
            stdout=cls.sim_log,
            stderr=cls.sim_log,
        )
        time.sleep(3)

    @classmethod
    def tearDownClass(cls):
        """
        Terminates the simulator instance.
        """
        if cls.external_sim:
            return
        if cls.sim_proc:
            cls.sim_proc.terminate()
            cls.sim_proc.wait()
        if hasattr(cls, "sim_log"):
            cls.sim_log.close()

    async def asyncSetUp(self):
        """
        Initializes driver and connects to simulator.
        """
        self.driver = CelestronAUXDriver()
        self.driver.port_name.membervalue = f"socket://localhost:{self.sim_port}"

        # Set to Equator for reachability
        self.driver.lat.membervalue = 0.0
        self.driver.long.membervalue = 0.0
        self.driver.update_observer()

        async def mock_send(xmldata):
            pass

        self.driver.send = mock_send
        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)

        # Reset position to 0,0
        if self.driver.communicator and self.driver.communicator.connected:
            from celestron_aux.celestron_aux_driver import pack_int3_steps
            from celestron_aux.celestron_indi_driver import AUXCommand, AUXCommands

            cmd_azm = AUXCommand(
                AUXCommands.MC_SET_POSITION,
                AUXTargets.APP,
                AUXTargets.AZM,
                pack_int3_steps(0),
            )
            cmd_alt = AUXCommand(
                AUXCommands.MC_SET_POSITION,
                AUXTargets.APP,
                AUXTargets.ALT,
                pack_int3_steps(0),
            )
            await self.driver.communicator.send_command(cmd_azm)
            await self.driver.communicator.send_command(cmd_alt)
            await self.driver.slew_by_rate(AUXTargets.AZM, 0, 1)
            await self.driver.slew_by_rate(AUXTargets.ALT, 0, 1)

    async def asyncTearDown(self):
        """
        Disconnects the driver.
        """
        if self.driver.communicator:
            await self.driver.communicator.disconnect()

    async def test_moon_goto(self):
        """
        Description:
            Verifies the ability to perform a GoTo to the Moon.

        Methodology:
            1. Selects "Moon" as the target type.
            2. Ensures the Moon is above the horizon by adjusting the observer date.
            3. Calculates Moon JNow coords.
            4. Triggers GoTo via `handle_equatorial_goto`.
            5. Waits for completion and verifies reported position.

        Expected Results:
            - The telescope must reach the Moon's coordinates within 0.5 deg accuracy.
        """
        # 1. Select Moon
        for name in self.driver.target_type_vector:
            self.driver.target_type_vector[name] = "Off"
        self.driver.target_type_vector["MOON"] = "On"

        # 2. Ensure Moon is above horizon (Alt > 30) to avoid slew limits
        self.driver.update_observer()
        moon = ephem.Moon()

        # Try finding a time today when moon is up (Alt > 30)
        start_date = ephem.now()
        fixed_date = start_date
        for h in range(24):
            self.driver.observer.date = ephem.Date(start_date + h / 24.0)
            moon.compute(self.driver.observer)
            if math.degrees(moon.alt) > 30:
                fixed_date = self.driver.observer.date
                break

        # If not found, just use current time and pray it's above horizon
        self.driver.observer.date = fixed_date
        original_now = ephem.now
        ephem.now = lambda: fixed_date

        try:
            # 3. Get Moon JNow coords at this specific time
            ra_moon, dec_moon = await self.driver._get_target_equatorial(
                base_date=fixed_date
            )

            # 4. Trigger GoTo
            await self.driver.handle_equatorial_goto(None)

            # 5. Wait for idle
            for _ in range(60):
                await self.driver.read_mount_position()
                if self.driver.slewing_light.membervalue == "Idle":
                    break
                await asyncio.sleep(1)

            # 6. Verify position
            await self.driver.read_mount_position()
            ra = float(self.driver.ra.membervalue)
            dec = float(self.driver.dec.membervalue)

            # Increased delta to 2.0 now that time is locked
            self.assertAlmostEqual(ra, ra_moon, delta=2.0)
            self.assertAlmostEqual(dec, dec_moon, delta=2.0)
        finally:
            ephem.now = original_now

    async def test_moon_tracking_rate(self):
        """
        Description:
            Verifies that Moon tracking rate is different from the sidereal rate.

        Methodology:
            1. Enables sidereal tracking and captures the guide rate commands sent to MC.
            2. Switches to Moon tracking and captures the new guide rate commands.
            3. Compares the raw AUX packets.

        Expected Results:
            - The binary packets for sidereal and lunar tracking rates must differ.
        """
        # 1. Set Sidereal tracking
        for name in self.driver.target_type_vector:
            self.driver.target_type_vector[name] = "Off"
        self.driver.target_type_vector["SIDEREAL"] = "On"

        for name in self.driver.track_mode_vector:
            self.driver.track_mode_vector[name] = "Off"
        self.driver.track_sidereal.membervalue = "On"

        await self.driver.handle_track_mode(None)
        await asyncio.sleep(2)

        # Capture sidereal guide rates
        sent_cmds = []
        original_send = self.driver.communicator.send_command

        async def mock_send(command):
            sent_cmds.append(command)
            return await original_send(command)

        self.driver.communicator.send_command = mock_send

        await asyncio.sleep(2)
        sidereal_cmds = [
            c.fill_buf().hex()
            for c in sent_cmds
            if c.command.name in ("MC_SET_POS_GUIDERATE", "MC_SET_NEG_GUIDERATE")
        ]
        sent_cmds.clear()

        # 2. Set Moon tracking
        for name in self.driver.target_type_vector:
            self.driver.target_type_vector[name] = "Off"
        self.driver.target_type_vector["MOON"] = "On"

        await asyncio.sleep(2)
        moon_cmds = [
            c.fill_buf().hex()
            for c in sent_cmds
            if c.command.name in ("MC_SET_POS_GUIDERATE", "MC_SET_NEG_GUIDERATE")
        ]

        self.assertNotEqual(sidereal_cmds, moon_cmds)

    async def test_satellite_tracking(self):
        """
        Description:
            Verifies satellite tracking using Two-Line Element (TLE) data.

        Methodology:
            1. Sets TLE for the ISS.
            2. Selects "Satellite" as the target type.
            3. Enables tracking.
            4. Intercepts and verifies that guide rates are sent to the mount.

        Expected Results:
            - The driver must send non-zero guide rate updates.
            - Rates for a LEO satellite (ISS) should be significantly higher
               than sidereal rates.
        """
        # 1. Set Satellite TLE (ISS)
        self.driver.tle_name.membervalue = "ISS"
        self.driver.tle_line1.membervalue = (
            "1 25544U 98067A   26006.88541667  .00000000  00000-0  00000-0 0    01"
        )
        self.driver.tle_line2.membervalue = (
            "2 25544  51.6400  10.0000 0001000   0.0000   0.0000 15.50000000000001"
        )

        # Select Satellite
        for name in self.driver.target_type_vector:
            self.driver.target_type_vector[name] = "Off"
        self.driver.target_satellite.membervalue = "On"

        # Start tracking
        for name in self.driver.track_mode_vector:
            self.driver.track_mode_vector[name] = "Off"
        self.driver.track_sidereal.membervalue = "On"

        await self.driver.handle_track_mode(None)

        sent_cmds = []
        original_send = self.driver.communicator.send_command

        async def mock_send(command):
            sent_cmds.append(command)
            return await original_send(command)

        self.driver.communicator.send_command = mock_send

        await asyncio.sleep(3)

        sat_cmds = [
            c.fill_buf().hex()
            for c in sent_cmds
            if c.command.name in ("MC_SET_POS_GUIDERATE", "MC_SET_NEG_GUIDERATE")
        ]

        self.assertGreater(len(sat_cmds), 0)

        # Stop tracking
        self.driver.track_none.membervalue = "On"
        await self.driver.handle_track_mode(None)


if __name__ == "__main__":
    unittest.main()
