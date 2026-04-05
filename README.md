# ApexTracking

ApexTracking je webova Flask aplikace, ktera z Apex statistik dela ML odhad ranku a prakticka doporuceni pro hru.

## Co aplikace vraci

- Predicted rank
- Rank confidence
- Promotion chance
- Demotion risk
- Doporuceny setup (mapa, legenda, drop location, role, play style)
- Last 5 matches (realna API historie nebo transparentne oznaceny estimate)

## Architektura

- Backend: `src/web.py`
- Data source resolver: `src/player_source.py`
- API vrstva (runtime): `src/apex_api.py`
- ML inference + recommendations: `src/predictor.py`
- Databaze: PostgreSQL (`src/auth_store.py`)
- Leaderboard loader: `src/leaderboard.py`
- Frontend: `templates/index.html`, `static/style.css`
- Trening + data collection workflow: `notebook.ipynb`
- Model bundle: `model/model.pkl`

## Datovy tok (runtime)

1. Uzivatel zada hrace a platformu.
2. `player_source` zkusi nacist data z `player_cache` (PostgreSQL).
3. Pokud cache neni, sahne na API a row ulozi do cache.
4. `predictor` spocita rank + confidence/progression metriky a doporuceny setup.
5. Web vykresli vystup.
6. U prihlaseneho uzivatele se predikce ulozi do `predictions` historie.

## Databaze (PostgreSQL only)

Aplikace bezi pouze s PostgreSQL.

Povinne env promenne:
- `DATABASE_URL`
- `APEX_API_KEY`
- `FLASK_SECRET_KEY`

Pouzite tabulky:
- `users`
- `predictions`
- `player_cache`

Poznamka: sloupec `predicted_damage_per_game` v tabulce `predictions` se nyni pouziva pro ulozeni rank confidence (%) kvuli zpetne kompatibilite bez migrace.

## Render nasazeni

### 1) Vytvor PostgreSQL service
- Service name: napr. `apextracking-db`
- Region: stejny jako web service

### 2) Vytvor Web Service
- Runtime: Python
- Branch: `main`
- Root Directory: prazdne
- Build Command: `pip install -r requirements.txt`
- Start Command: `python -m src.web`

### 3) Nastav env promenne
- `DATABASE_URL` = Internal Database URL z Render PostgreSQL
- `APEX_API_KEY` = tvuj API key
- `FLASK_SECRET_KEY` = dlouhy nahodny string

### 4) Deploy
- Manual Deploy -> Deploy latest commit

### 5) Overeni
- Otevrit Render URL
- Prihlasit/registrovat se
- Spustit predikci
- Overit, ze historie predikci zustava po restartu

## Trening modelu a sber dat

Model i sber dat je centralizovany do `notebook.ipynb`.

Notebook obsahuje:
- cisteni dat,
- feature engineering,
- trenink rank modelu,
- evaluaci,
- export do `model/model.pkl`,
- notebook-only funkce pro sber dat:
	- kolekce podle seznamu jmen,
	- UID harvesting.

## Testy

Projekt obsahuje unit testy:
- `tests/test_collector.py`
- `tests/test_predictor_logic.py`

## Poznamka k puvodu dat

Treningova data jsou sbirana pres Apex API (vlastni sber), nejde o prevzaty hotovy dataset.
