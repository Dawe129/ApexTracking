# ApexTracking - poznamky k obhajobe

Tento dokument je interni tahak na obhajobu aktualni verze projektu.

## 1) Co aplikace dela

ApexTracking je Flask web, ktery po zadani hrace:
- nacte statistiky z DB cache/API/fallback CSV,
- predikuje rank,
- z pravdepodobnosti rank modelu vypocita rank confidence, promotion chance a demotion risk,
- navrhne setup (mapa, legenda, drop, role, styl),
- zobrazi poslednich 5 her (real API historie nebo estimate).

Rezime uzivatele:
- auth (login/register),
- guest (search + leaderboard),
- user (vlastni profil + historie predikci).

## 2) Hlavni soubory v aktualnim stavu

- `src/web.py`: Flask flow, formulare, render vystupu.
- `src/player_source.py`: resolver zdroje dat hrace (db/api/local).
- `src/apex_api.py`: API vrstva (fetch, mapovani payloadu na row, validacni helpery).
- `src/predictor.py`: inference ranku + metriky confidence/progression + recommendation engine.
- `src/auth_store.py`: PostgreSQL vrstva (`users`, `predictions`, `player_cache`).
- `src/leaderboard.py`: priprava leaderboardu pro UI.
- `src/build_leaderboard.py`: script na sestaveni leaderboard CSV.
- `notebook.ipynb`: trening modelu + notebook-only sber dat.
- `templates/index.html`, `static/style.css`: frontend.

Smazane stare skripty:
- `src/collector.py` (nahrazeno `src/apex_api.py` + notebook sekci),
- `src/uid_harvester.py` (nahrazeno notebook sekci).

## 3) Datovy tok requestu

1. Formular v UI zavola `POST /`.
2. `web.py` spusti `_run_prediction`.
3. `player_source.resolve_player_row` vrati row + source (`db`/`api`/`local`).
4. `ApexPredictor.predict` vrati:
- `predicted_rank`,
- `rank_confidence`,
- `promotion_chance`,
- `demotion_risk`,
- doporuceny setup.
5. `web.py` slozi result pro sablonu.
6. U prihlaseneho usera ulozi zaznam do `predictions`.

## 4) Odkud se berou data

AUTO rezim v `player_source.py`:
1. Nejdriv DB cache (`player_cache`).
2. Kdyz cache neni, API pres `apex_api.fetch_player_stats`.
3. Kdyz API selze, fallback z lokalniho CSV (`players_ready.csv`/`players.csv`).

`apex_api.player_to_row` mapuje payload na jednotne feature schema:
- level, rank_score, kills, damage, headshots, games_played, wins, kdr, damage_per_game,
- recent_matches (pokud API data obsahuje historii).

## 5) Co presne se predikuje

Hlavni ML vystup:
- `predicted_rank` (klasifikace).

Odvozene metriky z `predict_proba`:
- `rank_confidence` = jistota modelu,
- `promotion_chance` = pravdepodobnost, ze vykon patri do vyssiho tieru,
- `demotion_risk` = pravdepodobnost, ze vykon je blizsi nizsimu tieru.

Proc je to obhajitelne:
- nejde o trivialni deleni typu damage/games nebo wins/games,
- metriky vychazeji primo z distribuce pravdepodobnosti klasifikacniho modelu.

## 6) Last 5 matches

- Kdyz API vrati historii, zobrazi se realna data.
- Kdyz API historii nevrati, `web.py` generuje realisticky estimate (transparentne oznaceno).

## 7) Databaze (PostgreSQL)

Povinne env:
- `DATABASE_URL`

Tabulky:
1. `users`
- auth + ulozeny Apex profil.

2. `predictions`
- historie predikci usera.
- sloupec `predicted_damage_per_game` je aktualne pouzity jako uloziste confidence (%),
  kvuli kompatibilite bez DB migrace.

3. `player_cache`
- cachovany row_json pro rychlejsi opakovane dotazy.

## 8) Trening a sber dat

Vse je centralizovane do `notebook.ipynb`.

Notebook obsahuje:
- pripravu datasetu,
- trening rank modelu,
- evaluaci,
- export `model/model.pkl`,
- pomocne funkce pro sber dat:
  - kolekce podle seznamu jmen,
  - UID harvesting.

## 9) Leaderboard

`build_leaderboard.py` sklada `data/leaderboard_top.csv`:
- API + fallback data,
- quality filtry,
- top 50 pro zobrazeni ve webu.

## 10) Hosting (Render)

- Build: `pip install -r requirements.txt`
- Start: `python -m src.web`
- Env: `DATABASE_URL`, `APEX_API_KEY`, `FLASK_SECRET_KEY`
- DB: Render PostgreSQL (persistuje data mezi deployi/restarty).

## 11) 30s obhajoba (zkracena)

"Aplikace je Flask web s autentizaci, perzistentni PostgreSQL vrstvou a rank klasifikacnim modelem. Data beru z DB cache, API a fallback datasetu. Nepredikuju trivialni podily, ale rank a metriky confidence/progression odvozene z pravdepodobnosti modelu. Nad tim bezi recommendation vrstva pro prakticke herni rozhodnuti. Cele to je nasazene na Renderu." 

## 12) Co zkontrolovat, kdyz neco nefunguje

1. API chyba / prazdny vysledek:
- zkontrolovat `APEX_API_KEY`, timeout a source fallback.

2. Login/historie nefunguje:
- zkontrolovat `DATABASE_URL` a tabulky v Postgresu.

3. Divny rank vystup:
- zkontrolovat vstupni row ze `player_source`,
- zkontrolovat aktualni `model/model.pkl`.

4. Aplikace pada na hostingu:
- overit RAM limit a velikost modelu.
