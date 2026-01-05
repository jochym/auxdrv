# Rozwój sterownika INDI dla montażu Celestron AUX (Python)

## Aktualny stan projektu (v0.3.0)

Projekt zrealizował fundamenty techniczne i matematyczne potrzebne do sterowania teleskopem.

### Zaimplementowane kamienie milowe:
*   ✅ **Rdzeń AUX:** Kompletna obsługa binarnego protokołu Celestron (sumy kontrolne, echo skipping).
*   ✅ **Łączność:** Wsparcie dla Serial oraz TCP (symulator).
*   ✅ **INDI API:** Pełna zgodność z `indipydriver 3.0.4`.
*   ✅ **Astronomia:** Transformacje współrzędnych RA/Dec <-> Enkodery przy użyciu biblioteki `ephem`.
*   ✅ **Symulator:** Headless mode, wsparcie dla protokołu Stellarium.
*   ✅ **Testy:** Zestaw testów funkcjonalnych w `tests/test_functional.py`.
*   ✅ **Konfiguracja:** Plik `config.yaml` (domyślnie Bębło).

---

## Roadmapa Rozwoju

### Faza 3.5: Dokumentacja kodu (W TRAKCIE)
*   Uzupełnienie wszystkich funkcji i klas o docstringi zgodne ze standardem Google Style.
*   Opisanie logiki komunikacji i transformacji współrzędnych dla ułatwienia przyszłego rozwoju.

### Faza 4: Logika Podejścia (Anti-backlash GoTo) (ZAKOŃCZONO)
*   **Cel:** Eliminacja luzów mechanicznych.
*   **Zrealizowane zadania:**
    *   ✅ Właściwości INDI: `GOTO_APPROACH_MODE`, `GOTO_APPROACH_OFFSET`.
    *   ✅ Implementacja trybu **FIXED_OFFSET** (zawsze podejście z tej samej strony).
    *   ✅ Implementacja trybu **TRACKING_DIRECTION** (dynamiczne wyznaczanie kierunku zgodnego ze śledzeniem).
    *   ✅ Dwuetapowy ruch: Szybki dojazd do punktu pośredniego + wolny dojazd precyzyjny.

### Faza 5: Zaawansowane Śledzenie Predykcyjne (2nd Order) (ZAKOŃCZONO)
*   **Cel:** Płynne prowadzenie za obiektem z użyciem predykcji numerycznej.
*   **Zrealizowane zadania:**
    *   ✅ Algorytm: Wyznaczanie prędkości kątowych ($\omega$) za pomocą symetrycznego wyrażenia różniczkowego drugiego rzędu.
    *   ✅ Pętla śledzenia: Tło asynchroniczne (1 Hz), aktualizacja prędkości silników (`MC_SET_POS_GUIDERATE`).
    *   ✅ Rozszerzalność: Architektura gotowa pod śledzenie obiektów nie-syderycznych (satelity, komety).
    *   ✅ Właściwość INDI: `TELESCOPE_TRACK_MODE`.

### Faza 6: Obsługa akcesoriów i stabilność (NASTĘPNY KROK)
*   Implementacja wsparcia dla modułów Focuser (wyciąg okularowy) i GPS.
*   Długofalowe testy dryfu śledzenia i odporności na błędy komunikacji.

---

## Instrukcje dla programistów

### Środowisko testowe:
```bash
python3 -m venv venv
source venv/bin/activate
pip install indipydriver pyserial-asyncio ephem pyyaml
```

### Uruchamianie testów:
```bash
./venv/bin/python tests/test_functional.py
```
