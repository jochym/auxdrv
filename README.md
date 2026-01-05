# Celestron AUX INDI Driver (Python)

Nowoczesny sterownik INDI dla montaży Celestron wykorzystujący protokół AUX, z wbudowanym symulatorem do testów.

## Architektura projektu

*   `celestron_indi_driver.py`: Główny sterownik INDI integrujący się z biblioteką `indipydriver`.
*   `celestron_aux_driver.py`: Biblioteka obsługująca binarny protokół komunikacji Celestron AUX.
*   `simulator/`: Rozbudowany symulator teleskopu NexStar, umożliwiający testowanie drivera bez fizycznego sprzętu.

## Wymagania

*   Python 3.8+
*   `indipydriver >= 3.0.0`
*   `pyserial-asyncio`
*   `ephem`

Instalacja zależności:
```bash
pip install indipydriver pyserial-asyncio ephem
```

## Uruchomienie

1.  Uruchomienie symulatora (tryb headless):
    ```bash
    python simulator/nse_simulator.py -t
    ```
2.  Uruchomienie sterownika INDI:
    ```bash
    python celestron_indi_driver.py
    ```

Dla połączenia z symulatorem użyj portu: `socket://localhost:2000`.

## Rozwój

Projekt jest w trakcie aktywnego rozwoju. Planowane jest dodanie pełnych transformacji współrzędnych astronomicznych (Faza 3).
