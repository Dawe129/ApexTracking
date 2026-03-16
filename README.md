# Apex Legends Tracker

Projekt sbira statistiky hracu z mozambiquehe.re API a pomoci strojoveho uceni predikuje:

- Rank hrace (Bronze -> Predator) - klasifikace
- Damage per game - regrese

## Aktualni stav projektu

Hotovo:

- API collector podle jmena hrace
- API collector podle UID (harvester pro velky pocet unikatu)
- trenink modelu do model/model.pkl
- web aplikace (Flask) pro predikci
- konzolova aplikace (volitelna)

Pouzivana cesta je:

- data/players.csv -> treninkova data
- model/model.pkl -> model pro predikce

Soubor data/players_input.txt je jen volitelny manualni vstup pro collector podle jmen.

## Struktura projektu

ApexTracking/
- src/
  - collector.py      (sber dat podle jmena, + API fetch podle uid)
  - uid_harvester.py  (sber velkeho poctu unikatu)
  - train.py          (trenink modelu a export model.pkl)
  - predictor.py      (nacteni modelu a predikce)
  - web.py            (Flask web)
  - app.py            (CLI verze)
- data/
  - players.csv
  - players_input.txt
  - players_unique_test.csv (testovaci soubor, neni nutny)
- model/
  - model.pkl
- templates/
  - index.html
- static/
  - style.css
- notebook.ipynb
- app.py              (hlavni vstup pro web)
- .env
- .env.example
- requirements.txt

## Instalace

Windows PowerShell:

```powershell
Set-Location "C:\Users\dpivo\Downloads\projekty\ApexTracking"
$py = ".\\.venv\\Scripts\\python.exe"
& $py -m pip install -r requirements.txt
```

## API klic

Do souboru .env vloz:

```env
APEX_API_KEY=tvuj_api_klic
```

Alternativne muzes mit v .env jen samotny klic na prvnim radku.

## Sber dat

### Varianta A - manualni seznam jmen

Pouziva data/players_input.txt (1 jmeno na radek):

```powershell
& $py -m src.collector --players-file data/players_input.txt --out data/players.csv --platform PC
```

### Varianta B - doporucena (1500+ unikatu)

Pouziva src.uid_harvester a uklada prubezne checkpointy.

```powershell
& $py -m src.uid_harvester --target 1500 --max-attempts 120000 --platform PC --out data/players.csv --sleep 0.02 --checkpoint-every 25
```

Poznamky:

- skript lze bezpecne prerusit Ctrl+C
- progress se ulozi do data/players.csv
- dalsi spusteni navaze na ulozena data

Kontrola poctu zaznamu:

```powershell
& $py -c "import pandas as pd; df=pd.read_csv('data/players.csv'); print('rows:',len(df)); print('unique_uid:',df['uid'].nunique())"
```

## Trenink modelu

```powershell
& $py -m src.train --csv data/players.csv --out model/model.pkl
```

## Spusteni aplikace

### Web (doporuceno)

```powershell
& $py app.py
```

Pak otevri:

- http://127.0.0.1:5000/

Dulezite: pouzij http, ne https.

### Konzole (volitelne)

```powershell
& $py -m src.app
```

## Notebook

Soubor notebook.ipynb je pripraveny pro Colab/Jupyter jako alternativni cesta treninku a evaluace.

## Puvod dat

Data pochazi z verejneho Apex Legends API:

- https://apexlegendsapi.com/
