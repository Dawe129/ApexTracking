# ApexTracking - studijni poznamky

Toto je interni studijni dokument pro obhajobu a orientaci v projektu.

## 1) Co projekt dela

ApexTracking je Flask aplikace, ktera po zadani hrace:
- nacte statistiky hrace,
- predikuje rank,
- spocita confidence + promotion chance + demotion risk,
- doporuci mapu, legendu, drop lokaci, roli a play style,
- zobrazi poslednich 5 zapasu (API nebo estimate).

## 2) Jedna veta k architekture

Pouziva se jeden klasifikacni model ranku; vsechny metriky (confidence/promote/demote) jsou odvozene z pravdepodobnosti tohoto modelu.

## 3) Kde se model trenuje

Trenink je v notebook.ipynb.

Kroky treninku:
1. Nacteni datasetu (`data/players.csv` nebo `data/players_ready.csv`).
2. Cisteni a validace dat.
3. Feature engineering.
4. Label encoding ranku.
5. Train/test split.
6. Trenink `RandomForestClassifier`.
7. Evaluace (`accuracy`, `classification_report`).
8. Analyza `predict_proba`.
9. Export model bundle do `model/model.pkl`.

## 4) Jaky model bundle se uklada

V model/model.pkl je:
- rank_model
- label_encoder
- feature_columns

Damage a win_rate modely uz se v aktualni verzi nepouzivaji.

## 5) Jak probiha predikce v runtime

Tok requestu:
1. Web route v src/web.py prijme formular.
2. src/prediction_runtime.py zavola `run_prediction`.
3. src/player_source.py najde data (`db` -> `api` -> `local`).
4. src/predictor.py zavola `ApexPredictor.predict`.
5. src/predictor_logic.py vrati rank + metriky + doporuceni.
6. Vysledek se vykresli do templates/index.html.

## 6) Jak se pocitaji metriky

Predicted rank:
- klasicka klasifikace (`predict`).

Rank confidence:
- `max(predict_proba)`.

Promotion chance:
- soucet pravdepodobnosti trid nad aktualnim rankem hrace.

Demotion risk:
- soucet pravdepodobnosti trid pod aktualnim rankem hrace.

Rank Probability Profile:
- kompletni rozpis pravdepodobnosti po rank tridach v UI.
- zobrazuje se fixne od Rookie po Predator.

## 7) Jak se sbiraji data

Sber dat je oddeleny do notebook_data_collection.ipynb.

Workflow A - collect_players_to_csv:
- vstup je seznam jmen,
- pro kazde jmeno se vola API,
- payload se mapuje na jednotny row,
- row projde validaci,
- vysledek se uklada do CSV.

Workflow B - harvest_uids_to_csv:
- z existujicich seed UID se generuji kandidati,
- paralelne se overuji pres API,
- validni row se deduplikuji,
- ukladaji se checkpointy i finalni CSV.

## 8) Jak se data cisti

V notebooku:
1. Kontrola povinnych sloupcu.
2. Prevod numerickych sloupcu na float.
3. Filtrovani nevalidnich zaznamu (games_played, wins rozsah).
4. Orez outlieru (kdr, damage_per_game).

V runtime mapperu (`src/apex_payload_mapper.py`):
- payload -> row schema,
- helper validace `is_row_usable`.

## 9) Datove zdroje v runtime

AUTO rezim v src/player_source.py:
1. player_cache (PostgreSQL)
2. API volani (src/apex_api.py)
3. fallback CSV (`data/players_ready.csv` nebo `data/players.csv`)

## 10) Databaze a tabulky

Povinne env:
- DATABASE_URL

Tabulky:
1. users
- login, heslo hash, ulozeny apex profil.

2. predictions
- historie predikci.
- sloupec predicted_damage_per_game se drzi kvuli kompatibilite a uklada confidence (%).

3. player_cache
- cache row_json podle player_key a platform.

## 11) Rozpis trid a souboru (co kde hledat)

### `class ApexPredictor` (src/predictor.py)
- nacte model bundle,
- pripravi feature DataFrame,
- vraci predikci ranku, metriky a doporuceni.

### `class PredictorError` (src/predictor.py)
- vyjimka pri chybe modelu/inference.

### `class CollectorError` (src/apex_api.py)
- vyjimka pri API/sberu dat.

### src/predictor_logic.py
- `compute_rank_metrics`: confidence/promote/demote + rank profile,
- `build_recommendations`: herni doporuceni,
- `rank_tier_score`: prevod rank jmena na tier score.

### src/prediction_runtime.py
- `run_prediction`: orchestruje celu predikci pro web,
- formatuje vystupni procenta,
- doplni estimate recent matches, kdyz API historii nema.

### src/player_source.py
- `resolve_player_row`: rozhoduje odkud se berou data hrace.

### src/apex_payload_mapper.py
- mapovani sloziteho API payloadu na jednotny row schema.

### src/db_core.py
- DB init, connect, schema create.

### src/db_users.py
- create/auth/get/update user.

### src/db_predictions.py
- ukladani a cteni historie predikci.

### src/db_cache.py
- cteni/zapis player cache.

### src/auth_store.py
- facade re-export (aby zbytek appky importoval jedno misto).

## 12) Testy

tests/test_collector.py:
- kontrola mapovani recent matches a payload -> row.

tests/test_predictor_logic.py:
- poradi rank tier score,
- ze recommendations vraci vsechna ocekavana pole.

Poznamka:
- testy jsou unit-level (logika), ne plne end-to-end test cele Flask app.

## 13) Kratky text k obhajobe (30-45 s)

"Projekt pouziva jeden rank klasifikacni model. Rank confidence, promotion chance a demotion risk se nepocitaji pravidly natvrdo, ale primo z distribuce pravdepodobnosti modelu. Runtime data beru pres resolver z DB cache, API nebo fallback CSV. Trenink je oddeleny v notebook.ipynb, sber dat v notebook_data_collection.ipynb a perzistence bezi na PostgreSQL." 

## 14) Nejcastejsi troubleshooting

1. Prazdny/failed API vysledek:
- zkontrolovat APEX_API_KEY,
- zkontrolovat timeout,
- overit fallback dataset.

2. Login nebo historie nefunguje:
- zkontrolovat DATABASE_URL,
- overit tabulky users/predictions/player_cache.

3. Divny rank vystup:
- zkontrolovat vstupni row,
- zkontrolovat model/model.pkl,
- porovnat classification report z treninku.

4. UI nesedi po upravach:
- hard refresh (Ctrl+F5),
- zkontrolovat static/style.css a templates/index.html.

## 6) Struktura model bundle

Soubor `model/model.pkl` obsahuje:
- `rank_model`,
- `label_encoder`,
- `feature_columns`.

Regresni modely pro damage/win rate uz nejsou soucasti aktualni produkcni verze.

## 7) Databaze (PostgreSQL)

Povinne env:
- `DATABASE_URL`

Tabulky:
1. `users`:
- auth + ulozeny Apex profil.

2. `predictions`:
- historie predikci usera,
- sloupec `predicted_damage_per_game` se pouziva jako uloziste confidence (%) kvuli zpetne kompatibilite.

3. `player_cache`:
- cache row_json podle `player_key + platform`.

DB vrstva je po refaktoru rozdelena:
- `src/db_core.py`,
- `src/db_users.py`,
- `src/db_predictions.py`,
- `src/db_cache.py`,
- facade exporty pres `src/auth_store.py`.

## 8) Hlavni moduly aplikace

- `src/web.py`: Flask controller a flow requestu.
- `src/prediction_runtime.py`: runtime orchestrace predikce.
- `src/player_source.py`: resolver zdroje dat (`db/api/local`).
- `src/predictor.py`: model wrapper.
- `src/predictor_logic.py`: confidence/progression metriky + recommendation logika.
- `src/apex_api.py`: API client facade.
- `src/apex_payload_mapper.py`: mapovani payloadu + validace row.
- `src/leaderboard.py`: priprava leaderboardu pro UI.

## 9) Deploy (Render)

- Build: `pip install -r requirements.txt`
- Start: `python -m src.web`
- Env: `DATABASE_URL`, `APEX_API_KEY`, `FLASK_SECRET_KEY`

## 10) Kratke vysvetleni k obhajobe

"V aktualni verzi pouzivame jeden klasifikacni rank model. Krome ranku z nej pres `predict_proba` pocitame confidence, promotion chance a demotion risk. Data se pro runtime berou z DB cache/API/fallback, trenink je v `notebook.ipynb` a sber dat je oddeleny v `notebook_data_collection.ipynb`." 

## 11) Co zkontrolovat, kdyz neco nefunguje

1. API chyba / prazdny vysledek:
- zkontrolovat `APEX_API_KEY`, timeout a fallback.

2. Login/historie nefunguje:
- zkontrolovat `DATABASE_URL` a tabulky v PostgreSQL.

3. Divny rank vystup:
- zkontrolovat vstupni row z `player_source.py`,
- zkontrolovat aktualni `model/model.pkl`.

4. Aplikace pada na hostingu:
- overit env promenne, DB dostupnost a velikost modelu.
