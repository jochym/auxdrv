# Rozwój sterownika INDI dla montażu Celestron AUX (Python)

## Aktualny stan projektu (v0.5.0)

Projekt zrealizował fundamenty techniczne i matematyczne potrzebne do sterowania teleskopem, w tym system wyrównania i nowoczesny interfejs testowy.

### Zaimplementowane kamienie milowe:
*   ✅ **Rdzeń AUX:** Kompletna obsługa binarnego protokołu Celestron (sumy kontrolne, echo skipping).
*   ✅ **Łączność:** Wsparcie dla Serial oraz TCP (symulator).
*   ✅ **INDI API:** Pełna zgodność z `indipydriver 3.0.4`.
*   ✅ **Astronomia:** Transformacje RA/Dec <-> Enkodery, predykcja 2. rzędu, anti-backlash GoTo.
*   ✅ **Alignment:** 3-punktowy model transformacji macierzowej (korekcja błędów ustawienia).
*   ✅ **Symulator:** Nowoczesny interfejs **Textual TUI**, wsparcie dla protokołu Stellarium.
*   ✅ **Testy:** Zestaw testów funkcjonalnych i matematycznych.
*   ✅ **Dokumentacja:** Pełne wsparcie Docstrings (Google Style).

---

## Roadmapa Rozwoju

### Faza 6: Bezpieczeństwo i Akcesoria (W TRAKCIE)
*   **Slew Limits:** Implementacja programowych limitów wysokości i azymutu.
*   **Cord Wrap Prevention:** Ochrona kabli przed skręceniem.
*   **Focuser Support:** Obsługa modułów wyciągu okularowego przez magistralę AUX.
*   **GPS Support:** Integracja z wbudowanym modułem GPS.

### Faza 7: Obsługa Obiektów Ruchomych (Planowane)
*   Rozszerzenie pętli śledzenia o obsługę obiektów nie-syderycznych (Satelity, Komety).
*   Integracja z danymi TLE.


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
