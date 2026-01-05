# Changelog

Wszystkie istotne zmiany w tym projekcie będą dokumentowane w tym pliku.

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
