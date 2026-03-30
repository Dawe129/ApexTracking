# ApexTracking

ApexTracking je webova aplikace, ktera z live Apex statistik dela ML predikce a doporuceni.

Co aplikace vraci:
- predikovany rank,
- predikovany damage per game,
- predikovany win rate,
- doporuceny setup (mapa, legenda, drop, role, styl),
- poslednich 5 her (API historie nebo odhad).

## Produkcni provoz

Projekt je urcen pro spousteni na Renderu.

Aplikace se ma pouzivat pres URL Render web service (napr. `https://apextracking.onrender.com`).

## Architektura

- Backend: Flask (`src/web.py`)
- Data ingest: `src/player_source.py` + `src/collector.py`
- ML inference: `src/predictor.py`
- Databaze: PostgreSQL (`src/auth_store.py`)
- Frontend: `templates/index.html`, `static/style.css`
- Trening modelu: `src/train.py`
- Model bundle: `model/model.pkl`

## Datovy tok (runtime)

1. Uzivatel zada hrace.
2. Aplikace zkusi cache v PostgreSQL (`player_cache`).
3. Kdyz cache neni, stahne data z API.
4. Data se premapuji na feature row.
5. Model predikuje rank, damage/game, win rate.
6. Recommendation engine navrhne mapu/legendu/drop/role/style.
7. U prihlaseneho uzivatele se predikce ulozi do historie (`predictions`).

## Databaze (PostgreSQL only)

Aplikace bezi pouze s PostgreSQL.

Povinna env promenna:
- `DATABASE_URL`

Pouzite tabulky:
- `users`
- `predictions`
- `player_cache`

## Render nasazeni

### 1) Vytvor PostgreSQL service
- Service name: napriklad `apextracking-db`
- Region: stejny jako web service

### 2) Vytvor Web Service
- Runtime: Python
- Branch: `main`
- Root Directory: prazdne
- Build Command: `pip install -r requirements.txt`
- Start Command: `python -m src.web`

### 3) Nastav env promenne ve Web Service
- `DATABASE_URL` = Internal Database URL z Render PostgreSQL
- `APEX_API_KEY` = tvuj API key
- `FLASK_SECRET_KEY` = dlouhy nahodny string

### 4) Deploy
- Manual Deploy -> Deploy latest commit

### 5) Overeni funkcnosti
- otevrit Render URL,
- registrace + predikce,
- restart web service,
- overit, ze ucet a historie zustaly (persistence PostgreSQL).

## Trening modelu

Model se trenuje z vlastnich sesbiranych dat skriptem `src/train.py`.

Notebook s postupem treninku a evaluace je v `notebook.ipynb`.

Trenuji se 3 modely:
- rank model,
- damage model,
- win rate model.

Model je ukladan komprimovane do `model/model.pkl` kvuli nizsi pametove narocnosti v produkci.

## Testy

Projekt obsahuje unit testy:
- `tests/test_collector.py`
- `tests/test_predictor_logic.py`
- `tests/test_train_targets.py`

## Poznamka k puvodu dat

Treningova data jsou sbirana pres Apex API (vlastni sber). Nejde o prevzaty hotovy dataset.

V projektu jsou skripty pro sber a zpracovani dat:
- `src/collector.py`
- `src/uid_harvester.py`
- `src/build_training_dataset.py`

## Vnitrni studijni material

Interni poznamky k obhajobe a logice programu jsou v `notes.md`.
