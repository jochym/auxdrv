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

### Faza 4: Logika Podejścia (Anti-backlash GoTo)
*   **Cel:** Eliminacja luzów mechanicznych.
*   **Tryb FIXED_OFFSET:** Zawsze kończ ruch w zadanym kierunku (np. dodatnie kroki w obu osiach).
*   **Tryb TRACKING_DIRECTION:** Ostatnia faza ruchu (wolna) w kierunku wektora śledzenia obiektu.
*   **Właściwości INDI:** `GOTO_APPROACH_MODE`, `GOTO_APPROACH_OFFSET`.

### Faza 5: Zaawansowane Śledzenie Predykcyjne (2nd Order)
*   **Algorytm:** Wyznaczanie prędkości kątowych ($\omega$) za pomocą symetrycznego wyrażenia różniczkowego drugiego rzędu:
    $\omega(t) \approx \frac{\theta(t + \Delta t) - \theta(t - \Delta t)}{2\Delta t}$
*   **Pętla śledzenia:** Częstotliwość 1 Hz, aktualizacja prędkości w czasie rzeczywistym.
*   **Rozszerzalność:** Architektura przygotowana pod śledzenie obiektów nie-syderycznych (satelity, komety, asteroidy).

### Faza 6: Obsługa akcesoriów i stabilność
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
