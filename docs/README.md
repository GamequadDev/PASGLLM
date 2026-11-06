graph TD
    Q["🔍 Zapytanie: Półprzewodniki i AI"]

    Q --> NVDA["🏢 NVIDIA - Bardzo dobra"]
    Q --> TSMC["🏢 TSMC - Stabilna"]
    Q --> ASML["🏢 ASML - Umiarkowana"]

    NVDA --- AMD["🏢 AMD - Konkurent"]

    NVDA -->|Klient produkcji| TSMC
    TSMC -->|Kupuje maszyny| ASML

    NVDA --- H100["📦 Produkt: B200 i H100"]
    ASML --- EUV["📦 Technologia: Maszyny EUV"]
### Makieta Interfejsu Użytkownika (UI Wireframe)
Widok podziału ekranu: po lewej stronie interaktywny graf relacji, po prawej generowany raport podsumowujący kondycję wybranej spółki.

```text
====================================================================================================
 PLATFORMA DO ANALIZY SPÓŁEK GIEŁDOWYCH Z LLM                                    [ Status: Połączono API ]
====================================================================================================
 [ Wpisz sektor lub spółki: 'Półprzewodniki, NVDA, TSMC'          ] [ 🔍 Generuj graf powiązań ]
 Filtry: [Sektor: Tech ▼] [Rynek: US ▼] [Analiza: Ostatni kwartał ▼] [LLM Model: Hermes Agent ▼]
====================================================================================================
 LEWY PANEL: GRAF POWIĄZAŃ (Neo4j / Vis.js)          | PRAWY PANEL: RAPORT ANALITYCZNY (LLM + DANE)
-----------------------------------------------------+----------------------------------------------
                                                     | 📊 SPÓŁKA: NVIDIA Corp (NASDAQ: NVDA)
              ( ASML )                               | ─────────────────────────────────────────────
                 ▲                                   | 📈 1. WYCENA I FINANSE (Yahoo Fin / SEC EDGAR)
                 │ [Dostawca maszyn]                 |   - Cena: 128.50 USD (+3.2% dzisiaj)
                 │                                   |   - P/E: 42.1  |  Średnia SMA(50): 121.30 USD
              ( TSMC ) ◄────────┐                    |   - Przychód Q/Q: +122% (Data Center driver)
                 ▲              │                    | ─────────────────────────────────────────────
                 │ [Producent]  │ [Konkurencja]      | 🤖 2. PODSUMOWANIE JAKOŚCIOWE (LLM Insight)
                 │              │                    |   "Dominująca pozycja w segmencie chipów AI.
             ┌───┴────┐         │                    |    Wąskie gardła produkcyjne w TSMC oraz
             │  NVDA  │ ◄───────┘                    |    regulacje eksportowe to główne ryzyka."
             └───┬────┘          ( AMD )             | ─────────────────────────────────────────────
                 │                                   | 📰 3. SENTYMENT WIADOMOŚCI (Finnhub / RSS)
                 ▼ [Główny produkt]                  |   🟢 Pozytywne: 75% | ⚪ Neutralne: 15% | 🔴 Negat: 10%
           [ B200 / H100 ]                           |   - "Tech Giants increase AI CapEx" (Waga: 0.9)
                                                     | ─────────────────────────────────────────────
   [Legenda]:                                        | 📦 4. STRUKTURA SPRZEDAŻY PRODUKTÓW
   🟢 Dobra kondycja  🟡 Ryzyko                      |   - Data Center (GPU): 85% udziału
   ── Powiązanie transakcyjne                        |   - Gaming: 11% | Inne: 4%
====================================================================================================
```

---

