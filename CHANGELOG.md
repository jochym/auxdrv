# Changelog

Wszystkie istotne zmiany w tym projekcie będą dokumentowane w tym pliku.

## [0.1.0] - 2026-01-05

### Added
- Początkowa implementacja sterownika Celestron AUX w Pythonie.
- Podstawowe właściwości INDI: `CONNECTION`, `PORT`, `FIRMWARE_INFO`, `MOUNT_POSITION`.
- Sterowanie ruchem: `SLEW_RATE`, `TELESCOPE_MOTION_NS/WE`, `TELESCOPE_ABSOLUTE_COORD`.
- Synchronizacja montażu i parkowanie.
- Symulator teleskopu z interfejsem TUI (curses).
- Implementacja binarnego protokołu AUX (pakowanie/rozpakowywanie ramek, sumy kontrolne).
