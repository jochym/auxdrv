# Celestron AUX INDI Driver (Python)

Nowoczesny sterownik INDI dla montaży Celestron wykorzystujący protokół AUX, z wbudowanym symulatorem do testów.

## Architektura projektu

*   `celestron_indi_driver.py`: Główny sterownik INDI integrujący się z biblioteką `indipydriver`.
*   `celestron_aux_driver.py`: Biblioteka obsługująca binarny protokół komunikacji Celestron AUX.
*   `simulator/`: Rozbudowany symulator teleskopu NexStar, umożliwiający testowanie drivera bez fizycznego sprzętu.

## Wymagania

*   Python 3.8+
*   `indipydriver`
*   `pyserial-asyncio`

Instalacja zależności:
```bash
pip install indipydriver pyserial-asyncio
```

## Uruchomienie

1.  Uruchomienie symulatora (opcjonalnie):
    ```bash
    python simulator/nse_simulator.py
    ```
2.  Uruchomienie sterownika INDI:
    ```bash
    python celestron_indi_driver.py
    ```

## Rozwój

Projekt jest w trakcie aktywnego rozwoju. Planowane jest dodanie obsługi TCP dla symulatora, trybu headless oraz pełnych transformacji współrzędnych astronomicznych.
