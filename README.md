# Apex Legends Tracker

Projekt sbira statistiky hracu z mozambiquehe.re API a pomoci strojoveho uceni predikuje:

- Rank hrace (Bronze -> Predator) - klasifikace
- Damage per game - regrese

## Technologie

- Python
- mozambiquehe.re API
- scikit-learn
- Google Colab / Jupyter Notebook

## Struktura projektu

ApexTracking/
- src/
  - collector.py
  - predictor.py
  - app.py
- data/
  - players_input.txt
  - players.csv
- model/
  - model.pkl (vytvori se po treningu)
- vendor/
- notebook.ipynb
- .env
- .env.example
- .gitignore
- requirements.txt
- README.md

## 1) Instalace

```bash
pip install -r requirements.txt
```

## 2) API klic

Do souboru `.env` vloz jednu z moznosti:

```env
APEX_API_KEY=tvuj_api_klic
```

nebo pouze hodnotu klice na prvni radek.

## 3) Sber dat

Priprav seznam jmen hracu do `data/players_input.txt` (1 jmeno na radek), potom spust:

```bash
python -m src.collector --players-file data/players_input.txt --out data/players.csv --platform PC
```

Pro 1500+ hracu pouzij vetsi vstupni seznam a pripadne zvys prodlevu parametrem `--sleep`.

## 4) Trenink modelu v notebooku

Otevri `notebook.ipynb` v Colabu/Jupyter a spust vsechny bunky:

- nacteni a cisteni dat
- trening klasifikace ranku
- trening regrese damage
- evaluace (accuracy, MAE, grafy)
- export `model/model.pkl`

## 5) Spusteni aplikace

```bash
python app.py
```

Aplikace si vyzada jmeno hrace, stahne aktualni data z API a vrati predikovany rank a damage/game.

## Puvod dat

Data pochazi z verejneho Apex Legends API: https://apexlegendsapi.com/ (mozambiquehe.re)
