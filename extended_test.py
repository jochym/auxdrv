
import asyncio
import os
import signal
from celestron_indi_driver import CelestronAUXDriver, AUXTargets, AUXCommand, AUXCommands

async def run_extended_test():
    print("=== ROZPOCZĘCIE ROZSZERZONEGO TESTU STEROWNIKA ===")
    
    # 1. Uruchomienie symulatora
    print("[1/7] Uruchamianie symulatora...")
    sim_proc = await asyncio.create_subprocess_exec(
        './venv/bin/python', 'simulator/nse_simulator.py', '-t', '-p', '2000',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await asyncio.sleep(2)

    try:
        # 2. Inicjalizacja sterownika
        print("[2/7] Inicjalizacja sterownika i połączenie...")
        driver = CelestronAUXDriver()
        driver.port_name.membervalue = "socket://localhost:2000"
        async def mock_send(xmldata): pass
        driver.send = mock_send
        
        driver.conn_connect.membervalue = "On"
        await driver.handle_connection(None)
        
        if not (driver.communicator and driver.communicator.connected):
            print("!!! BŁĄD: Brak połączenia.")
            return

        # 3. Ruch GoTo w obu osiach
        target_azm = 50000
        target_alt = 30000
        print(f"[3/7] GoTo: AZM={target_azm}, ALT={target_alt}...")
        await driver.slew_to(AUXTargets.AZM, target_azm)
        await driver.slew_to(AUXTargets.ALT, target_alt)
        
        # Czekamy na zakończenie ruchu (pooling pozycji)
        print("      Oczekiwanie na osiągnięcie celu...")
        for _ in range(10):
            await driver.read_mount_position()
            azm = int(driver.azm_steps.membervalue)
            alt = int(driver.alt_steps.membervalue)
            print(f"      Aktualna pozycja: AZM={azm}, ALT={alt}")
            if abs(azm - target_azm) < 100 and abs(alt - target_alt) < 100:
                print("      Cel osiągnięty.")
                break
            await asyncio.sleep(1)

        # 4. Ustawienie trackingu (Guide Rate)
        print("[4/7] Ustawianie trackingu (Guide Rate: AZM=100, ALT=50)...")
        # Emulujemy zdarzenie INDI dla Guide Rate
        class MockEvent:
            def __init__(self, root=None):
                self.vectorname = "TELESCOPE_GUIDE_RATE"
                self.root = root
        
        driver.guide_azm.membervalue = 100
        driver.guide_alt.membervalue = 50
        await driver.handle_guide_rate(MockEvent())
        
        # 5. Sprawdzenie czy pozycja się zmienia (tracking działa)
        print("[5/7] Weryfikacja trackingu (czekamy 3s)...")
        await driver.read_mount_position()
        p1_azm, p1_alt = int(driver.azm_steps.membervalue), int(driver.alt_steps.membervalue)
        await asyncio.sleep(3)
        await driver.read_mount_position()
        p2_azm, p2_alt = int(driver.azm_steps.membervalue), int(driver.alt_steps.membervalue)
        
        print(f"      Zmiana pozycji: ΔAZM={p2_azm - p1_azm}, ΔALT={p2_alt - p1_alt}")
        if p2_azm > p1_azm and p2_alt > p1_alt:
            print("      Tracking: OK (pozycja rośnie)")
        else:
            print("      Tracking: BŁĄD lub brak ruchu")

        # Zatrzymujemy tracking
        driver.guide_azm.membervalue = 0
        driver.guide_alt.membervalue = 0
        await driver.handle_guide_rate(MockEvent())

        # 6. Powrót do 0,0
        print("[6/7] Powrót do pozycji początkowej (0,0)...")
        await driver.slew_to(AUXTargets.AZM, 0)
        await driver.slew_to(AUXTargets.ALT, 0)
        
        for _ in range(10):
            await driver.read_mount_position()
            azm, alt = int(driver.azm_steps.membervalue), int(driver.alt_steps.membervalue)
            if azm < 100 and alt < 100:
                print("      Powrócono do bazy.")
                break
            await asyncio.sleep(1)

        # 7. Weryfikacja końcowa
        print("[7/7] Weryfikacja końcowa...")
        await driver.read_mount_position()
        final_azm = int(driver.azm_steps.membervalue)
        final_alt = int(driver.alt_steps.membervalue)
        print(f"      Pozycja końcowa: AZM={final_azm}, ALT={final_alt}")
        
        if final_azm < 100 and final_alt < 100:
            print("\n=== TEST ZAKOŃCZONY SUKCESEM ===")
        else:
            print("\n=== TEST ZAKOŃCZONY NIEPOWODZENIEM ===")

    finally:
        print("Zamykanie procesów...")
        sim_proc.terminate()
        await sim_proc.wait()

if __name__ == "__main__":
    asyncio.run(run_extended_test())
