# Apex Legends Tracker

Projekt sbira statistiky hracu z mozambiquehe.re API a pomoci strojoveho uceni predikuje:

- Rank hrace (Bronze -> Predator) - klasifikace
- Damage per game - regrese
- Doporucenou mapu, legendu, drop lokaci, roli a herni styl
- Global Top 50 leaderboard (API + fallback dataset)

Dataset v data/players_ready.csv je sjednoceny do jednoho souboru a jmena byla normalizovana (bez sufixu _sim).

## Aktualni stav projektu

Hotovo:

- API collector podle jmena hrace
- API collector podle UID (harvester pro velky pocet unikatu, checkpoint/resume, paralelni workers)
- trenink modelu do model/model.pkl
- web aplikace (Flask) pro predikci
- konzolova aplikace (volitelna)

Pouzivana cesta je:

- data/players.csv -> treninkova data (staticky podklad pro ucitele/GitHub)
- PostgreSQL -> persistentni DB pro uzivatele, historii i live cache hracu
- model/model.pkl -> model pro predikce

Manualni vstup podle jmen je volitelny (soubor data/players_input.txt si pripadne vytvor sam).

## Quick Start (Doporuceno)

1) Instalace:

```powershell
Set-Location "C:\Users\dpivo\Downloads\projekty\ApexTracking"
$py = ".\\.venv\\Scripts\\python.exe"
& $py -m pip install -r requirements.txt
```

2) Rychly sber 1500+ unikatu:

```powershell
& $py -m src.uid_harvester --target 1500 --max-attempts 500000 --platform PC --out data/players.csv --sleep 0 --request-timeout 3 --checkpoint-every 50 --workers 16
```

3) Kontrola poctu dat:

```powershell
& $py -c "import pandas as pd; df=pd.read_csv('data/players.csv'); print('rows:', len(df)); print('unique_uid:', df['uid'].nunique())"
```

4) Trenink modelu:

```powershell
& $py -m src.train --csv data/players.csv --out model/model.pkl
```

5) Spusteni webu:

```powershell
& $py -m src.web
```

Otevri: http://127.0.0.1:5000/

## Struktura projektu

ApexTracking/
- src/
  - collector.py      (sber dat podle jmena, + API fetch podle uid)
  - uid_harvester.py  (sber velkeho poctu unikatu, resume, checkpoint, workers)
  - train.py          (trenink modelu a export model.pkl)
  - predictor.py      (nacteni modelu a predikce)
  - web.py            (Flask web)
- data/
  - players.csv
  - players_ready.csv
- model/
  - model.pkl
- templates/
  - index.html
- static/
  - style.css
- notebook.ipynb
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

Nejdriv vytvor data/players_input.txt (1 jmeno na radek), potom spust:

```powershell
& $py -m src.collector --players-file data/players_input.txt --out data/players.csv --platform PC
```

### Varianta B - doporucena (1500+ unikatu)

Pouziva src.uid_harvester a uklada prubezne checkpointy.

```powershell
& $py -m src.uid_harvester --target 1500 --max-attempts 500000 --platform PC --out data/players.csv --sleep 0 --request-timeout 3 --checkpoint-every 50 --workers 16
```

Poznamky:

- skript lze bezpecne prerusit Ctrl+C
- progress se ulozi do data/players.csv
- dalsi spusteni navaze na ulozena data

Zakladni tuning parametru:

- --workers: paralelni requests (rychlejsi sber), zacni 16; pri nestabilite sniz na 8
- --request-timeout: jak dlouho cekat na request, doporuceno 2.5-4 s
- --sleep: 0 pro max rychlost
- --checkpoint-every: mene zapisu na disk, doporuceno 50

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
& $py -m src.web
```

Pak otevri:

- http://127.0.0.1:5000/

## Leaderboard (Top 50)

Pro vytvoreni zebricky top hracu (aspon 50 zaznamu):

```powershell
& $py -m src.build_leaderboard --seed data/top_players_seed.txt --out data/leaderboard_top.csv --target 50 --platform PC
```

Co to dela:

- zkusi stahnout hrace ze seed listu pres API
- kdyz API vrati mene hracu, doplni zbytek z data/players_ready.csv
- vystup ulozi do data/leaderboard_top.csv

Dulezite: pouzij http, ne https.

Poznamka k vyhledani hrace (AUTO rezim):

- aplikace nejdriv zkusi nacist hrace z PostgreSQL cache (tabulka player_cache)
- pokud hrac v cache neni, stahne aktualni data z API a ulozi je do PostgreSQL
- kdyz API neni dostupne, pouzije fallback lokalni soubory data/players_ready.csv a data/players.csv

Tento flow znamena:

- prvni dotaz na hrace je live (API)
- dalsi dotazy na stejne jmeno/platformu jsou rychlejsi z DB cache
- predikce stale bezi pres model/model.pkl

## Hosting na Render + PostgreSQL

Proc PostgreSQL:

- Render free web service ma ephemerial filesystem.
- PostgreSQL na Renderu je persistentni, data zustavaji.

Co nastavit na Renderu:

1. Vytvor PostgreSQL service.
2. Ve Web Service nastav env promennou DATABASE_URL na Internal Database URL z Render PostgreSQL.
3. Nastav take APEX_API_KEY a FLASK_SECRET_KEY.
4. Build command: pip install -r requirements.txt
5. Start command: python -m src.web

Chovani aplikace:

- DATABASE_URL je povinny, aplikace bezi jen na PostgreSQL

### Konzole (volitelne)

```powershell
& $py -m src.app
```

## Notebook

Soubor notebook.ipynb je pripraveny pro Colab/Jupyter jako alternativni cesta treninku a evaluace.

## Puvod dat

Data pochazi z verejneho Apex Legends API:

- https://apexlegendsapi.com/

## Troubleshooting

1) Python z .venv nejde spustit:

- Ujisti se, ze jsi v root slozce projektu: C:\Users\dpivo\Downloads\projekty\ApexTracking
- Neklikej cd ApexTracking podruhe.
- Over cestu: Test-Path .\\.venv\\Scripts\\python.exe

2) Harvester hlasi timeouty:

- Jde o sit/API nestabilitu, ne nutne o neplatny klic.
- Pro max propustnost pouzij workers + nizsi timeout.
- Pri velke nestabilite zkus workers 8 a request-timeout 4.

3) Web nejde otevrit v prohlizeci:

- Otevirat pouze http://127.0.0.1:5000/
- Nepouzivat https://127.0.0.1:5000/
