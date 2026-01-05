# Rozwój sterownika INDI dla montażu Celestron AUX (Python)

## Aktualny stan sterownika (`celestron_indi_driver.py`)

Sterownik INDI dla montażu Celestron AUX został zaimplementowany w Pythonie, wykorzystując bibliotekę `indipydriver` oraz protokół AUX zreferowany na podstawie sterownika C++ `indi-celestronaux` i jego symulatora.

### Zaimplementowane funkcjonalności:
*   **Połączenie/Rozłączenie:** Właściwość `CONNECTION`.
*   **Konfiguracja portu szeregowego:** Właściwość `PORT` (nazwa portu, prędkość transmisji).
*   **Informacje o oprogramowaniu układowym:** Właściwość `FIRMWARE_INFO` (model, wersje HC, AZM, ALT) pobierane za pomocą komend AUX `MC_GET_MODEL` i `GET_VER`.
*   **Odczyt pozycji montażu:** Właściwość `MOUNT_POSITION` (AZM i ALT w krokach enkodera), aktualizowana okresowo za pomocą komendy AUX `MC_GET_POSITION`.
*   **Status montażu:** Właściwość `MOUNT_STATUS` (SLEWING, TRACKING, PARKED).
*   **Sterowanie ruchem z zadaną prędkością:**
    *   Właściwość `SLEW_RATE` (prędkość od 1 do 9).
    *   Właściwość `TELESCOPE_MOTION_NS` (ruch Północ/Południe) za pomocą komend AUX `MC_MOVE_POS`/`MC_MOVE_NEG` dla osi ALT.
    *   Właściwość `TELESCOPE_MOTION_WE` (ruch Zachód/Wschód) za pomocą komend AUX `MC_MOVE_POS`/`MC_MOVE_NEG` dla osi AZM.
*   **Ruch do pozycji absolutnej (w krokach):** Właściwość `TELESCOPE_ABSOLUTE_COORD` (AZM i ALT w krokach enkodera) za pomocą komend AUX `MC_GOTO_FAST`/`MC_GOTO_SLOW`.
*   **Synchronizacja montażu:** Właściwość `TELESCOPE_SYNC` (ustawia bieżącą pozycję jako referencyjną) za pomocą komendy AUX `MC_SET_POSITION`.
*   **Parkowanie montażu:** Właściwość `TELESCOPE_PARK` (parkuje do pozycji 0,0 kroków) za pomocą komend AUX `MC_GOTO_FAST`/`MC_GOTO_SLOW`.
*   **Odparkowanie montażu:** Właściwość `TELESCOPE_UNPARK`.

## Dalszy rozwój sterownika

Poniżej przedstawiono listę zadań i kierunków dalszego rozwoju sterownika:

### 1. Transformacje współrzędnych RA/Dec
*   **Cel:** Umożliwienie sterowania montażem za pomocą współrzędnych astronomicznych (RA/Dec) zamiast surowych kroków enkodera.
*   **Zadania:**
    *   Implementacja konwersji RA/Dec na kroki AZM/ALT i odwrotnie. Będzie to wymagało uwzględnienia lokalizacji obserwatora (szerokość/długość geograficzna, czas lokalny) oraz typu montażu (Alt-Az, EQ).
    *   Dodanie właściwości INDI dla współrzędnych RA/Dec.
    *   Wykorzystanie logiki transformacji z `celestronaux.cpp` (funkcje takie jak `AltAzFromRaDec`, `EncodersToAltAz`, `EncodersToRADE`, `RADEToEncoders`).

### 2. Zaawansowane śledzenie i prowadzenie (Guiding)
*   **Cel:** Pełna implementacja trybów śledzenia (syderyczny, słoneczny, księżycowy) oraz obsługa prowadzenia (guiding).
*   **Zadania:**
    *   Dodanie właściwości INDI dla trybów śledzenia (`TRACK_MODE`).
    *   Implementacja komend AUX związanych ze śledzeniem (np. `MC_SET_POS_GUIDERATE`, `MC_SET_NEG_GUIDERATE`, `MC_AUX_GUIDE`).
    *   Rozwinięcie metody `hardware()` o logikę aktywnego śledzenia i korekcji pozycji.

### 3. Obsługa focuser'a
*   **Cel:** Umożliwienie sterowania focuserem podłączonym do montażu.
*   **Zadania:**
    *   Dodanie właściwości INDI dla focuser'a (np. `FOCUS_POSITION`, `FOCUS_MOVE_RELATIVE`).
    *   Implementacja komend AUX związanych z focuser'em (np. `FOC_GET_HS_POSITIONS`).

### 4. Obsługa GPS
*   **Cel:** Integracja z modułem GPS montażu.
*   **Zadania:**
    *   Dodanie właściwości INDI dla GPS.
    *   Implementacja komend AUX związanych z GPS (np. `GPS_GET_LAT`, `GPS_GET_LONG`, `GPS_GET_TIME`).

### 5. Ulepszona obsługa błędów i statusów
*   **Cel:** Zwiększenie niezawodności i informatywności sterownika.
*   **Zadania:**
    *   Bardziej szczegółowe raportowanie błędów komunikacji.
    *   Implementacja odczytu statusu montażu (np. czy montaż jest w ruchu, czy osiągnął cel) za pomocą komend AUX `MC_SLEW_DONE`, `MC_SEEK_DONE`.
    *   Wykorzystanie właściwości `ILight` do wizualizacji statusów.

### 6. Integracja z symulatorem (W TRAKCIE)
*   **Cel:** Umożliwienie automatycznego testowania sterownika bez fizycznego montażu.
*   **Zadania w realizacji:**
    *   ✅ Inicjalizacja repozytorium Git, dokumentacja (README, CHANGELOG).
    *   🔄 Refaktoryzacja symulatora do trybu headless (bez curses).
    *   🔄 Wdrożenie wsparcia dla komunikacji TCP/IP między driverem a symulatorem.
    *   📋 Automatyzacja testów i weryfikacji funkcjonalności.

## Instrukcje uruchamiania sterownika

### Wymagane zależności:
*   `indipydriver`
*   `pyserial-asyncio`

Zainstaluj je za pomocą:
```bash
pip install indipydriver pyserial-asyncio
```

### Uruchomienie:
1.  Zapisz kod sterownika (plik `celestron_indi_driver.py`) w wybranym katalogu.
2.  Uruchom sterownik z terminala:
    ```bash
    python /sciezka/do/celestron_indi_driver.py
    ```
3.  Połącz się z klientem INDI (np. KStars/Ekos), dodając nowego sterownika "Celestron AUX". Upewnij się, że ustawienia portu szeregowego w kliencie INDI odpowiadają tym skonfigurowanym w sterowniku (domyślnie `/dev/ttyUSB0` i 19200 baud).
