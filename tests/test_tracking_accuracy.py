import asyncio
import unittest
import math
import ephem
import numpy as np
import time
import subprocess
import os
from celestron_aux.celestron_indi_driver import CelestronAUXDriver, STEPS_PER_REVOLUTION


class TestTrackingAccuracy(unittest.IsolatedAsyncioTestCase):
    """
    Automated verification of tracking accuracy, drift, and slew stability.
    This replaces the 'visual check' with programmatic telemetry analysis.
    """

    sim_port = 2000
    sim_process = None

    @classmethod
    def setUpClass(cls):
        """Starts the simulator once for the whole test suite."""
        if os.environ.get("EXTERNAL_SIM"):
            cls.sim_port = int(os.environ.get("SIM_PORT", 2000))
            return

        cls.sim_port = 2002  # Use a different port than functional tests
        cls.sim_log = open("test_accuracy_sim.log", "w")
        cls.sim_process = subprocess.Popen(
            [
                "./venv/bin/python",
                "src/celestron_aux/simulator/nse_simulator.py",
                "-t",
                "-d",
                "--perfect",
                "-p",
                str(cls.sim_port),
            ],
            stdout=cls.sim_log,
            stderr=cls.sim_log,
        )
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):
        """Stops the simulator."""
        if cls.sim_process:
            cls.sim_process.terminate()
            cls.sim_process.wait()
            cls.sim_log.close()

    async def asyncSetUp(self):
        self.driver = CelestronAUXDriver()
        self.driver.port_name.membervalue = f"socket://localhost:{self.sim_port}"

        async def mock_send(xmldata):
            pass

        self.driver.send = mock_send

        self.driver.conn_connect.membervalue = "On"
        await self.driver.handle_connection(None)

        # Reset position to 0,0
        if self.driver.communicator and self.driver.communicator.connected:
            from celestron_aux.celestron_indi_driver import (
                AUXCommand,
                AUXCommands,
                AUXTargets,
                pack_int3_steps,
            )

            await self.driver.communicator.send_command(
                AUXCommand(
                    AUXCommands.MC_SET_POSITION,
                    AUXTargets.APP,
                    AUXTargets.AZM,
                    pack_int3_steps(0),
                )
            )
            await self.driver.communicator.send_command(
                AUXCommand(
                    AUXCommands.MC_SET_POSITION,
                    AUXTargets.APP,
                    AUXTargets.ALT,
                    pack_int3_steps(0),
                )
            )

    async def asyncTearDown(self):
        if self.driver.communicator:
            await self.driver.communicator.disconnect()

    async def test_drift_and_jump_detection(self):
        """
        Slews to a star and monitors for drift and 'jumps' in position.
        """
        # 1. Setup Alignment (Perfect identity for sim)
        self.driver.align_clear_all.membervalue = "On"
        await self.driver.handle_alignment_config(None)

        # 2. Target a star (Vega)
        # Enable anti-backlash to see if it causes 'jumps'
        self.driver.approach_disabled.membervalue = "Off"
        self.driver.approach_fixed.membervalue = "On"
        self.driver.approach_azm_offset.membervalue = 5000
        self.driver.approach_alt_offset.membervalue = 5000

        star = ephem.star("Vega")
        self.driver.update_observer()
        star.compute(self.driver.observer)

        target_ra = float(star.ra) * 12.0 / math.pi
        target_dec = float(star.dec) * 180.0 / math.pi

        print(f"Targeting Vega: RA={target_ra:.4f}h, Dec={target_dec:.4f}deg")
        self.driver.ra.membervalue = target_ra
        self.driver.dec.membervalue = target_dec
        self.driver.set_track.membervalue = "On"

        # 3. Monitor Slew for Jumps
        state_transitions = []
        telemetry = []
        slew_finished = False

        async def monitor_slew():
            nonlocal slew_finished
            last_state = None
            while not slew_finished:
                # Poll the INDI vector state
                cur_state = self.driver.equatorial_vector.state
                if cur_state != last_state:
                    state_transitions.append((time.time(), cur_state))
                    last_state = cur_state

                await self.driver.read_mount_position()
                az = int(self.driver.azm_steps.membervalue)
                alt = int(self.driver.alt_steps.membervalue)
                telemetry.append((time.time(), az, alt))
                await asyncio.sleep(0.1)

        # Trigger GoTo
        monitor_task = asyncio.create_task(monitor_slew())
        await self.driver.handle_equatorial_goto(None)

        # Wait for slew done
        for _ in range(120):
            await self.driver.read_mount_position()
            if self.driver.slewing_light.membervalue == "Idle":
                break
            await asyncio.sleep(1)

        slew_finished = True
        await monitor_task

        print(f"State transitions: {[s[1] for s in state_transitions]}")

        # Verify state sequence: Idle -> Busy -> Ok (Exactly once)
        # If there were jumps/double execution, we'd see Busy -> Ok -> Busy -> Ok
        busy_count = [s[1] for s in state_transitions].count("Busy")
        self.assertEqual(
            busy_count, 1, f"Expected exactly 1 'Busy' period, found {busy_count}"
        )

        # 4. Monitor Tracking for Drift
        print("Slew finished. Monitoring tracking for 60 seconds...")
        tracking_data = []
        for i in range(60):
            await self.driver.read_mount_position()
            ra = float(self.driver.ra.membervalue)
            dec = float(self.driver.dec.membervalue)
            tracking_data.append((ra, dec))
            if i % 10 == 0:
                print(f" T+{i}s: RA={ra:.6f}h, Dec={dec:.6f}deg")
            await asyncio.sleep(1)

        ra_vals = [d[0] for d in tracking_data]
        dec_vals = [d[1] for d in tracking_data]

        # Calculate drift (difference between last and first)
        ra_drift = (ra_vals[-1] - ra_vals[0]) * 3600.0 * 15.0  # arcsec
        dec_drift = (dec_vals[-1] - dec_vals[0]) * 3600.0  # arcsec

        # Initial pointing error
        ra_init_err = (ra_vals[0] - target_ra) * 3600.0 * 15.0
        dec_init_err = (dec_vals[0] - target_dec) * 3600.0

        print(
            f"Initial Error: RA={ra_init_err:.2f} arcsec, Dec={dec_init_err:.2f} arcsec"
        )
        print(f"Drift over 60s: RA={ra_drift:.2f} arcsec, Dec={dec_drift:.2f} arcsec")

        # Standard deviation (jitter)
        ra_std = np.std(ra_vals) * 3600.0 * 15.0
        dec_std = np.std(dec_vals) * 3600.0

        print(f"Precision (std): RA={ra_std:.2f} arcsec, Dec={dec_std:.2f} arcsec")

        # Assertions
        # Initial pointing should be very good (< 20 arcsec with iterative GoTo)
        self.assertLess(
            abs(ra_init_err), 20.0, f"High initial RA error: {ra_init_err:.2f} arcsec"
        )
        self.assertLess(
            abs(dec_init_err),
            20.0,
            f"High initial Dec error: {dec_init_err:.2f} arcsec",
        )

        # Sidereal drift should be small (< 10.0 arcsec over 60s)
        self.assertLess(
            abs(ra_drift), 10.0, f"Significant RA drift: {ra_drift:.2f} arcsec"
        )
        self.assertLess(
            abs(dec_drift), 10.0, f"Significant Dec drift: {dec_drift:.2f} arcsec"
        )

        # Jitter should be small
        self.assertLess(ra_std, 10.0, f"High RA jitter: {ra_std:.2f} arcsec")
        self.assertLess(dec_std, 10.0, f"High Dec jitter: {dec_std:.2f} arcsec")


if __name__ == "__main__":
    unittest.main()
