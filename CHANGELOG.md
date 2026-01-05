# Changelog

Wszystkie istotne zmiany w tym projekcie będą dokumentowane w tym pliku.

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
