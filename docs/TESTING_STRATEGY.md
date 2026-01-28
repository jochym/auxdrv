# Strategia Testów i Bezpieczeństwa Sprzętowego

Dokument ten opisuje zestaw testów dla sterownika INDI Celestron AUX oraz procedury bezpiecznego przenoszenia walidacji z symulatora na rzeczywisty montaż.

## 🗂️ Kategorie Testów

### 🟢 Tier 1: Wirtualne (Tylko Symulator)
Testy w tej grupie sprawdzają logikę matematyczną i protokół. Nie mają sensu na sprzęcie lub wymagają specyficznych warunków (np. zatrzymanego czasu).
*   `tests/test_alignment_*.py`: Walidacja transformacji SVD i modeli geometrycznych.
*   `tests/integration/test_full_stack.py`: Sprawdzenie warstwy TCP i sesji INDI.

### 🟡 Tier 2: Sprzętowe Bezpieczne (Hardware-Ready)
Te testy mogą być uruchamiane na prawdziwym montażu. Wykonują one standardowe operacje astronomiczne.
*   `tests/test_functional.py`: Podstawowe komendy GoTo, Parkowanie (uwaga: trwa długo!), Home.
*   `tests/test_tracking_accuracy.py`: Analiza dryfu podczas długotrwałego śledzenia.
*   `tests/test_moving_objects.py`: Śledzenie Księżyca i satelitów (wymaga aktualnego czasu).
*   `tests/test_visual_stars.py`: Celowanie w najjaśniejsze gwiazdy (Capella, Betelgeuse).

### 🔴 Tier 3: Sprzętowe Krytyczne (Używać z Ostrożnością)
Testy sprawdzające limity fizyczne i sytuacje awaryjne. **Wymagają obecności przy teleskopie.**
*   `tests/test_safety.py`: Testy limitów Alt/Az i Cord Wrap. Teleskop może zbliżyć się do statywu/pieru.
*   `scripts/hit_validation.py`: Interaktywny test impulsów osi i zatrzymania awaryjnego.

---

## ⚠️ Procedura Bezpieczeństwa (Hardware Protocol)

Podczas pracy z prawdziwym sprzętem należy przestrzegać poniższych zasad:

1.  **Brak restartów**: Prawdziwy montaż pamięta swoją pozycję i stan (np. Park). Testy sprzętowe nie mogą zakładać, że zaczynają od "zera".
2.  **Dwustopniowe GoTo**: Driver automatycznie wykonuje ruch w dwóch fazach (FAST + SLOW z anti-backlash). Nie należy tego wyłączać, gdyż zapewnia to bezpieczeństwo mechaniczne i precyzję.
3.  **Emergency Stop**: Zawsze miej pod ręką klawisz **SPACE** (w skryptach HIT) lub przycisk Abort w kliencie INDI.
4.  **Zasilanie**: Testy ruchów szybkich (`Rate 9`) wymagają stabilnego zasilania.

---

## 🛠️ Korzystanie ze skryptów walidacyjnych

Skrypty w katalogu `scripts/` służą do interaktywnej pracy:

1.  **HIT (Hardware Interaction Test)**: 
    `python scripts/hit_validation.py`
    Wykonaj to jako pierwsze po podpięciu nowego montażu. Sprawdza czy "Północ to Północ".
2.  **PEC Measure**:
    `python scripts/pec_measure.py`
    Uruchom podczas śledzenia gwiazdy blisko południka, aby zmierzyć błąd okresowy montażu.
3.  **Real World Validation**:
    `python scripts/real_world_validation.py`
    Zaawansowana analiza precyzji GoTo (wymaga symulatora lub bardzo precyzyjnego zewnętrznego pomiaru).
