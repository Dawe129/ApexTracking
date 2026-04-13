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


### uceni

## Lekce 1 - hledani hrace
### problem: uzivatel vyhleda hrace a zobrazi se mu predikace 

hlavni tri soubory: Web.py, player_source.py, prediction_runtime.py

web.py - webova vrstva, prijima formular (vstupy) a zobrazuje stranku, informace (vystupy)
player_source.py - vybira, rozhoduje odkud se vezmou vstupy: CSV, API, DB
prediction_runtime.py - bere hracovi data (vstupy) a vypocitava predikace

### prvni tok - pozadavek od uzivatele
kdyz uzivatel klikne ve vyhledavani na tlacitko hledat tak se posle HTTP (POST) pozadavek ze souboru web.py

#### HTTP pozadavky a index()
typy HTTP pozadavku a co delaji:
GET - chci si zobrazit stranku, chci ji prijmout, nacist
POST - posilam ti data z formulare, neco s nima udelej, zpracuj je, zjisti jeho predikaci

@app.route("/", methods=["GET", "POST"])
def index():

kdyz prijde jakykoliv pozadavek, tak se zavola index()
methods=["GET", "POST"] znamena ze tato cesta zvladne oba pozadavky:
pokud je pozadavek jen nejake klasicke otevreni stranky tak se posle pozadavek GET
pokud to je nejake odeslani formulare, posle se pozadavek POST

#### request.method
request method jen kontroluje co se stalo a podle toho pokracuje:
pokud prisel POST pozadavek, chci zpracovat nejaky formular a proves predikaci
pokud neprisel POST pozadavek tak to delat nebudu


#### zadani od uzivatele

player_name = (request.form.get("player_name") or "").strip()
platform = (request.form.get("platform") or "PC").strip().upper()

player_name - nazev promene
request.form - data z formulare, otevre to soubor s daty
.get("player_name") - vezmi hodnotu z pole jmenem player_name
or "" - pokud v poli player_name nic neni vezmi prazdny text
.strip() - ocisti data, odstrani mezi z obou stran, ze predu i ze zadu
.upper() - prevede text na velka pismena
.strip().upper() - odstrani mezi z obou stran a zaroven zvetsi text na velka pismena
.get("platform") or "PC" - vezme hodnout z pole jmenem platform, pokud prazdne vezme automaticky PC


### druhy tok - probehnuti predikace

predikace se zacina tvorit ve funkci run_prediciton v souboru prediction_runtime

#### row, source = resolve_player_row(...)

resolve_player_row - se podiva odkud muze brat uzivatelska data, nejprve se podivat do DB cache pak do API a pote do lokalniho CSV souboru
row - vrati data o hracovi 
source - vrati db, api, local

#### predictor = ApexPredictor("model/model.pkl")

spusti se trida ApexPredictor
ApexPredictor - nacte model ze souboru ktery uz je vytrenovan, znovu ho netrenuje

class ApexPredictor:
    def __init__(self, model_path: str = "model/model.pkl") -> None:
        path = Path(model_path)
        if not path.exists():
            raise PredictorError(f"Model file not found: {model_path}")

        bundle = joblib.load(path)
        if not isinstance(bundle, dict):
            raise PredictorError("Model bundle is invalid. Expected dict with model artifacts.")

def __init__(self, model_path: str = "model/model.pkl") -> None:

v konstruktoru __init__ se otevira soubor model.pkl neboli soubor modelu
model.pkl je uz hotovy vytrenovany model ktery se uz nemeni
pokud by se mel zmenit, musi se znovu natrenovat v notebook.ipynb a pak se vytvorit novy
Model obsahuje: rank_model, label_encoder

path = Path(model_path)
bundle = joblib.load(path) - nacte soubor do promene, soubor pote zkontroluje ze bundle je slovnik, pokud ne vyhodi vyjimku
pak uloží interně do self.rank_model, self.label_encoder a self.feature_columns


#### pred = predictor.predict(row)

def predict(self, player_row: Dict[str, Any]) -> Dict[str, Any]:
        X = self._build_features(player_row)

        rank_idx = int(self.rank_model.predict(X)[0])
        rank_name = self.label_encoder.inverse_transform(np.array([rank_idx]))[0]
        rank_metrics = self._rank_metrics(X, predicted_rank=rank_name, player_row=player_row)

        return {
            "predicted_rank": rank_name,
            "rank_confidence": rank_metrics["rank_confidence"],
            "promotion_chance": rank_metrics["promotion_chance"],
            "demotion_risk": rank_metrics["demotion_risk"],
            "rank_profile": rank_metrics.get("rank_profile", []),
            **self._recommendations(player_row),
        }

X = self._build_features(player_row) - spusti metodu _build_features ktera vezme hracuv slovni (row) a pro kazdy sloupec a radek prevede text na cislo
prevede row na takovy format ktery je potreba

self.rank_model.predict(X) - pouzije model a vrati model [5,4,6,3,...]
int(...[0]) - vezme prvni hodnotu
self.label_encoder.inverse_transform - vezme to cislo a prepise ho jako spravny nazev napr: gold, silver,...

rank_metrics = self._rank_metrics(X, predicted_rank=rank_name, player_row=player_row) - vola metodu compute_rank_metrics() z predictor_logic a ten spocita rank_confidence, promotion_chance, demotion_risk, rank_profile


return {...} - vraci predikace, ktere se maji vypsat
**self._recommendations(player_row) - zavola build_recommendations(player_row) a tato funkce vypocitava doporuceny setup hrace

rank_confidence = float(pred.get("rank_confidence", 0.0))

prevede vysledek modelu na cislo, stejne to funguje i pro promotion_chance a demotion_risk

result = {
        "player": row["player"],
        "rank": pred["predicted_rank"],
        "rank_confidence": format_percent(rank_confidence),
        "promotion_chance": format_percent(promotion_chance),
        "demotion_risk": format_percent(demotion_risk),
        "rank_profile": format_rank_profile(list(pred.get("rank_profile", []))),
        "source": source,
        "best_map": pred["best_map"],
        "best_legend": pred["best_legend"],
        "best_drop_zone": pred["best_drop_zone"],
        "ideal_team_role": pred["ideal_team_role"],
        "combat_style": pred["combat_style"],
    }

zde se vytvori slovnik ktery se pak posila na web

recent_matches = row.get("recent_matches") if isinstance(row.get("recent_matches"), list) else []
    if recent_matches:
        result["recent_games"] = recent_matches[:5]
        result["recent_games_kind"] = "api"
    else:
        result["recent_games"] = build_estimated_recent_games(
            row=row,
            rank_confidence=rank_confidence,
            promotion_chance=promotion_chance,
            demotion_risk=demotion_risk,
        )
        result["recent_games_kind"] = "estimate"

recent_matches - zjistuje jestli ma hrac historii zapasu:
pokud ani vypise se poslednich 5 zapasu
pokud ne spusti se funkce build_estimated_recent_games ktera mu odhadne poslednich 5 zapasu


## Lekce dva - notebook.ipynb