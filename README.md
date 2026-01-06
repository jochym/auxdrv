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
*   `pyyaml`
*   `textual`
*   `rich`

Instalacja zależności:
```bash
pip install indipydriver pyserial-asyncio ephem pyyaml textual rich
```

## Uruchomienie

1.  **Uruchomienie symulatora:**
    *   Tryb graficzny (Textual TUI): `python simulator/nse_simulator.py`
    *   Tryb headless (tło): `python simulator/nse_simulator.py -t`
2.  **Uruchomienie sterownika INDI:**
    ```bash
    python celestron_indi_driver.py
    ```

Dla połączenia z symulatorem użyj portu: `socket://localhost:2000`.

## Integracja ze Stellarium

Symulator udostępnia serwer zgodny z protokołem Stellarium na porcie `10001`. Aby zweryfikować działanie:

1.  Uruchom symulator: `python simulator/nse_simulator.py`
2.  W Stellarium przejdź do: **Konfiguracja (F2) -> Wtyczki -> Sterowanie teleskopem -> Skonfiguruj**.
3.  Dodaj nowy teleskop:
    *   Sterowany przez: **Zewnętrzne oprogramowanie lub inny komputer**.
    *   Nazwa: **NSE Simulator**.
    *   Host: **localhost**, Port: **10001**.
4.  Połącz się z teleskopem. Zobaczysz celownik teleskopu na mapie nieba.

## System Wyrównania (Alignment)

Sterownik obsługuje 3-punktowe wyrównanie na gwiazdach. Aby wykonać kalibrację:
1.  Ustaw tryb `Coord Set Mode` na **SYNC**.
2.  Wybierz gwiazdę w planetarium i wykonaj polecenie **Sync**.
3.  Powtórz dla 2-3 gwiazd w różnych częściach nieba. Sterownik automatycznie wyliczy macierz transformacji poprawiającą celność GoTo.

## Konfiguracja

Lokalizacja obserwatora oraz porty są definiowane w pliku `config.yaml`. Domyślnie ustawiono współrzędne dla miejscowości **Bębło, Polska**.
