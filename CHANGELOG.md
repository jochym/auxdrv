# Changelog

Wszystkie istotne zmiany w tym projekcie będą dokumentowane w tym pliku.

## [0.5.2] - 2026-01-06

### Added
- Tryb debugowania (`-d` / `--debug`) w symulatorze, raportujący parametry pracy na `stderr`.
- Implementacja okna przesuwnego (sliding window) dla obliczeń prędkości nieba (vRA, vDec) w celu eliminacji szumów numerycznych.

### Fixed
- Naprawiono oscylacje wyświetlanych prędkości vRA/vDec w interfejsie TUI.
- Poprawiono stabilność obliczeń prędkości w trybie headless.

## [0.5.1] - 2026-01-06

### Added
- Rozszerzenie interfejsu TUI symulatora o wyświetlanie prędkości obrotu silników (vAlt, vAzm) w °/s.
- Wyświetlanie prędkości poruszania się po sferze niebieskiej (vRA, vDec) w "/s (arcsec/s).
- Poprawa stylizacji interfejsu Textual.

## [0.5.0] - 2026-01-05

### Added
- Nowoczesny interfejs TUI symulatora oparty na bibliotece **Textual** (zastąpienie curses).
- Zaawansowany **system wyrównania (Alignment)** oparty na transformacjach macierzowych 3x3.
- Obsługa właściwości `TELESCOPE_ON_COORD_SET` (tryby SLEW, TRACK, SYNC).
- Możliwość dodawania punktów wyrównania (max 3 gwiazdy) w celu korekcji błędów ustawienia montażu.
- Nowy zestaw testów: `test_10_alignment_3star` oraz testy matematyki wyrównania (`tests/test_alignment_math.py`).
- Obsługa zmiennej środowiskowej `EXTERNAL_SIM` w testach funkcjonalnych.

### Changed
- Pełne udokumentowanie kodu (Docstrings w standardzie Google Style) dla wszystkich modułów.
- Usunięcie ostrzeżeń o przestarzałych funkcjach (`utcnow`, `get_event_loop`).
- Poprawa logiki `Park` – obsługa "zawijania" licznika kroków (wrap-around).
- Zmiana formatu konfiguracji na YAML (`config.yaml`).

## [0.4.0] - 2026-01-05

### Added
- Implementacja logiki podejścia **Anti-backlash GoTo** (Faza 4).
- Nowe właściwości INDI: `GOTO_APPROACH_MODE` (DISABLED, FIXED_OFFSET, TRACKING_DIRECTION) oraz `GOTO_APPROACH_OFFSET`.
- Zaawansowana pętla śledzenia oparta na **predykcji 2. rzędu** (Faza 5).
- Algorytm wyznaczania prędkości kątowych ($\omega$) za pomocą symetrycznego wyrażenia różniczkowego.
- Nowe właściwości INDI: `TELESCOPE_TRACK_MODE` (Sidereal, Solar, Lunar).
- Mechanizm blokowania komunikacji (`asyncio.Lock`) w `AUXCommunicator` dla zapewnienia bezpieczeństwa współbieżnego dostępu do magistrali AUX.
- Nowe testy funkcjonalne: `test_7_approach_logic`, `test_8_approach_tracking_direction`, `test_9_predictive_tracking`.

### Changed
- Refaktoryzacja metody GoTo w celu obsługi wieloetapowego ruchu (Stage 1: Fast Approach, Stage 2: Slow Final).
- Metoda `equatorial_to_steps` obsługuje teraz parametr `time_offset`.

## [0.3.0] - 2026-01-05

### Added
- Integracja z biblioteką `ephem` dla transformacji współrzędnych astronomicznych.
- Obsługa właściwości INDI `GEOGRAPHIC_COORD` (szerokość, długość, wysokość).
- Obsługa właściwości INDI `EQUATORIAL_EOD_COORD` (RA/Dec).
- Implementacja logiki GoTo na współrzędne równikowe (RA/Dec -> Alt/Az -> Encoders).
- Automatyczne wyliczanie i raportowanie bieżącego RA/Dec na podstawie pozycji enkodera.
- Nowy test funkcjonalny `test_6_equatorial_goto` weryfikujący poprawność transformacji.
- Obsługa pliku konfiguracyjnego `config.json` z domyślną lokalizacją w Bęble.
- Instrukcja integracji ze Stellarium do weryfikacji wizualnej.

### Changed
- Poprawiono odporność metody `handle_equatorial_goto` na brak danych zdarzenia.

## [0.2.1] - 2026-01-05

### Added
- Kompletny zestaw testów funkcjonalnych w katalogu `tests/` oparty na `unittest`.
- Testy pokrywają: Firmware Info, GoTo Precision, Tracking Logic, Park/Unpark, Connection Robustness.
- Automatyczne przechwytywanie logów symulatora podczas testów (`test_sim.log`).

### Changed
- Poprawiono odporność metod `handle_sync`, `handle_park`, `handle_unpark`, `handle_guide_rate` na brak danych zdarzenia (ułatwia testowanie).
- Zsynchronizowano stan projektu i roadmapę.

## [0.2.0] - 2026-01-05

### Added
- Wsparcie dla połączeń TCP w `AUXCommunicator` (URL `socket://host:port`).
- Mechanizm "Echo Skipping" w protokole AUX, umożliwiający pracę na magistralach jednoprzewodowych.
- Tryb headless (`-t` / `--text`) w symulatorze teleskopu.
- Obsługa biblioteki `ephem` w symulatorze.
- Implementacja właściwości `TELESCOPE_GUIDE_RATE` w sterowniku INDI.
- Zweryfikowano działanie pętli sterowania (Slew/Read/Tracking) za pomocą rozszerzonego testu automatycznego.


### Changed
- Pełna refaktoryzacja `celestron_indi_driver.py` w celu dostosowania do API `indipydriver 3.0.4`.
- Naprawiono błędy konstruktorów `NumberMember` (kolejność argumentów).
- Poprawa stabilności odczytu ramek AUX (użycie `readexactly`).
- Usunięcie błędnych bajtów zerowych z plików źródłowych.


## [0.1.0] - 2026-01-05

### Added
- Początkowa implementacja sterownika Celestron AUX w Pythonie.
- Podstawowe właściwości INDI: `CONNECTION`, `PORT`, `FIRMWARE_INFO`, `MOUNT_POSITION`.
- Sterowanie ruchem: `SLEW_RATE`, `TELESCOPE_MOTION_NS/WE`, `TELESCOPE_ABSOLUTE_COORD`.
- Synchronizacja montażu i parkowanie.
- Symulator teleskopu z interfejsem TUI (curses).
- Implementacja binarnego protokołu AUX (pakowanie/rozpakowywanie ramek, sumy kontrolne).
