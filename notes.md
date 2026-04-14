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

### prvni bunka - importy a nastaveni prostredi

import warnings - nacita modul pro praci s hrozbami (warningy)
warnings.filterwarnings('ignore') - skryva warningy aby nebyli videt
from pathlib import Path - bezpecna prace se soubory a cesty
import joblib - ukladani, nacitani moduloveho bundelu
import numpy as np - prace s numerikou
import pandas as pd - DataFrame tabulky
from sklearn.ensemble import RandomForestClassifier - klasifikator random forest modelu
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix - metriky pro vyhodnoceni
from sklearn.model_selection import train_test_split - rozdeli data na trenovaci a testovaci
from sklearn.preprocessing import LabelEncoder - prevod textovich trid ranku na cisla


df = df.dropna(subset=['rank']).copy()
.dropna - odstrani radky ci sloupce kde chybjeji hodnoty
subset-['rank] - znamena ze kontroluje jen sloupec rank, subset jen urcuje na jaky sloupec se ma zamerit
.copy() - vytvori novy nezavisly DataFrame

df['rank'].nunique() - vraci pocet unikatnich hodnot ve sloupci rank

fit_transform(y) - prevodnik mapovani trid (Bronze->0, Silver->1, Gold->2)

pd.Series(y_encoded).value_counts() - zabali pole y_encoded do pandas series, values_counts() - spocita cetnost kazde tridy

### druha bunka - nacteni CSV

dataset_path = Path('data/players_ready.csv') - definuje cestu k souboru
if not dataset_path.exists():
    raise FileNotFoundError(f'Dataset not found: {dataset_path}') - jestli nenajde cestu k souboru vyhodi vyjimku

df = pd.read_csv(dataset_path) - nacte CSV do DataFrame pouzije knihovnu pandas
print('Dataset file:', dataset_path) - vypise cestu odkud se to nacetlo
print('Rows:', len(df)) - spocita a vypise pocet radku
print('Columns:', len(df.columns)) - vypise pocet sloupcu
display(df.head(5)) - vypise prvnich pet radku souboru

### treti bunka - kontrola a cisteni dat

required_cols = [
    'player', 'uid', 'level', 'rank', 'rank_score', 'kills', 'damage',
    'headshots', 'games_played', 'wins', 'kdr', 'damage_per_game'
]

seznam slopupcu ktere jsou potreba pro funkcnost, bez nich nemuze pipeline bezet

missing = [col for col in required_cols if col not in df.columns] - zjistuje jestli nejake sloupce chybi
print('Missing columns:', missing) - vypise chybjejici sloupce, pokud nejake jsou

if missing:
    raise ValueError(f'Chybí sloupce: {missing}') - vyhodi vyjimku (zastavi program) kdyz nejaky sloupec chybi 

print('Null values by column:') - pokud jsou vsechny sloupce v poradku tak vypise ze nic nechybi 
print(df[required_cols].isna().sum()):

df[required_cols] - projde jen sloupce ktere jsou v required_cols 
.isna() vraci hodnoty TRUE - hodnota chybi, FALSE - hodnota existuje
.sum() spocita vsechny TRUE (1) a vrati soucet vsech TRUE neboli neplatnych radku


df = df.dropna(subset=['rank']).copy() - odstrani radky kde chybi rank, nemuze chybet cilova promenna

numeric_cols = ['level', 'rank_score', 'kills', 'damage', 'headshots', 'games_played', 'wins', 'kdr', 'damage_per_game'] - slopce ktere musi byt numericke, musi tam byt cislo

for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
 - pokousi se prevest hodnoty na cisla, pokud jsou tam neplatne hodnoty, prepise je na 0.0

print('Null values after conversion:')
print(df[required_cols].isna().sum()) - vypise pocet chybnych sloupcu po predchozi uprave

print('Unique rank values:', df['rank'].nunique()) - vypise pocet rank trid, takze 9 
print(df['rank'].value_counts().head(15)) - vypise prvnich 15 ranku, takze vsechny a kolik jich kazdych je takze (silver - 542)

### ctvrta bunka - priprava vstupu a cilove promenne

feature_columns = ['level', 'rank_score', 'kills', 'damage', 'headshots', 'games_played', 'wins', 'kdr', 'damage_per_game']
- seznam vstupnich promenych pro model (predikaci)

X = df[feature_columns] - vstupní vlastnosti modelu
y = df['rank'].astype(str) - cílová proměnná

label_encoder = LabelEncoder() - inicializace encoderu
y_encoded = label_encoder.fit_transform(y) textovym rankum da ciselne stitky

print('Feature columns:', feature_columns) - kontrola vstupu
print('Target classes:', list(label_encoder.classes_)) - vypis ranku, jako model rozlisuje ranky
print('Class counts:')
print(pd.Series(y_encoded).value_counts().sort_index())
- vypise jednotlive ranky jako cisla a u kazdeho napise kolikrat tam je a pote je seradi podle indexu

### pata bunka - rozdeleni dat na trenovaci a testovaci
split_kwargs = {'test_size': 0.2, 'random_state': 42} - nastavi ze 20% dat bude testovacich
class_counts = pd.Series(y_encoded).value_counts() - zpocita kolikrat tam je jeden rank ale pro vsechny ranky 
can_stratify = len(class_counts) > 1 and class_counts.min() >= 2 - kontroluje jestli jsou alespon 2 vzorky v nejmensi tride

if can_stratify:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_encoded, stratify=y_encoded, **split_kwargs
    ) - pokud to projde zachova pomer mezi trenovacimi a testovacimi daty
else:
    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, **split_kwargs) - velikost splitu

print('Train shape:', X_train.shape)
print('Test shape:', X_test.shape)
print('Train class distribution:')
print(pd.Series(y_train).value_counts().sort_index())

### sesta bunka - trenink modelu
rank_model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
n_estimators=100 - nastaveni RandomForest modelu - 100 stromu, 
random_state=42 - aby se les pokazde stavel stejne
n_jobs=-1 - jak moc paralarne se les stavi

rank_model.fit(X_train, y_train) - vytrenuje model

train_preds = rank_model.predict(X_train) - predikace na trenovacich datech
test_preds = rank_model.predict(X_test) - predikace na testovacich datech

print('Train accuracy:', accuracy_score(y_train, train_preds)) - vypocita presnost treninku
print('Test accuracy:', accuracy_score(y_test, test_preds)) - vypocita presnopst testu

### sedma bunka - vyhodnoceni modelu
print('Classification report (test set):') - Precision/recall/F1 per třída + macro/weighted avg.

Precision - v procentech kolikrat to bylo spravne urcene ale jen u jednotlive tridy (97% znamena ze v 97% to byla pravda)
Recall - kolik procent z jednotlive tridy model zachytil napr (98% bronzu model zachytil)
F1-score - urcuje jak je dobry model v oblasti precision a recall
Support - kolik vzorku bylo v jednotlive tride
Accuracy - celkova uspesnost modelu, bere to z F1-score
Macro-avg - prumery vsechn metrik
weighted-avg - prumer podle poctu vzorku, trida ktera ma vice vzorku ma vetsi hodnotu nez trida ktera jich ma min


print(classification_report(y_test, test_preds, target_names=label_encoder.classes_))

cm = confusion_matrix(y_test, test_preds)
cm_df = pd.DataFrame(cm, index=label_encoder.classes_, columns=label_encoder.classes_)
display(cm_df)

### osma bunka - analyza pravdepodobnosti
if hasattr(rank_model, 'predict_proba'): - overi ze model umi pravdepodobnosti
    proba = rank_model.predict_proba(X_test)
    max_proba = proba.max(axis=1)
    print('Průměrná nejvyšší pravděpodobnost (confidence):', np.mean(max_proba))
    print('Minimální nejvyšší pravděpodobnost:', np.min(max_proba))
    print('Maximální nejvyšší pravděpodobnost:', np.max(max_proba))
else:
    print('Model nepodporuje predict_proba.')


### devata bunka - export modelu
bundle = {
    'rank_model': rank_model,
    'label_encoder': label_encoder,
    'feature_columns': feature_columns,
}

- sbali vse potrebne pro runtime

out_path = Path('model/model.pkl') - cilovy soubor modelu
out_path.parent.mkdir(parents=True, exist_ok=True) - pokud slozka neexistuje tak ji vytvori
joblib.dump(bundle, out_path, compress=('xz', 3)) - ulozi komprimovany bundle
print(f'Saved model bundle to {out_path}') = vypise kam model ulozil
print('Bundle size (MB):', out_path.stat().st_size / (1024 * 1024)) - vypise velikost modelu

## lekce tri - sbirani dat v notebook_data_collection

### prvni bunka - importy a zavislosti 
from concurrent.futures import ThreadPoolExecutor, as_completed - paralelne vola UID ve sberu
from pathlib import Path - bezpecna prace s cestami
import csv - cteni a zapis CSV
import random = nahodne generovani kandidatnich UID
import time - pauza mezi requesty

from src.apex_api import (
    CollectorError,
    fetch_player_stats,
    fetch_player_stats_by_uid,
    is_row_usable,
    load_api_key,
    player_to_row,
)
- fetch funkce validace radku a mapovani payloadu do radku

### druha bunka - sber dat podle seznamu jmen
def collect_players_to_csv(
    players,
    out_csv='data/players.csv',
    platform='PC',
    sleep_seconds=0.25,
    min_level=25.0,
    min_kills=80.0,
    min_damage=20000.0,
    min_rank_score=1000.0,
    min_nonzero_metrics=3,
    allow_no_gameplay_signal=False,
): 
- vstupni parametry

    api_key = load_api_key() - nacte api klic
    rows = [] - drzi vysledne zaznamy
    seen = set() - kontroluje duplicity

    for name in [str(p).strip() for p in players if str(p).strip()]: - smycka pro vycistena jmena 
        try:
            payload = fetch_player_stats(player=name, api_key=api_key, platform=platform)
- stahne profil hrace podle jmena
            row = player_to_row(payload, requested_name=name) 
- prevede api payload na jednotny radek pro CSV
            if not is_row_usable(
                row,
                min_level=min_level,
                min_kills=min_kills,
                min_damage=min_damage,
                min_rank_score=min_rank_score,
                min_nonzero_metrics=min_nonzero_metrics,
                require_gameplay_signal=not allow_no_gameplay_signal,
            ): - overi minimalni kvalitu dat podle limitu, 
                continue

            key = str(row.get('uid', '')).strip() or str(row.get('player', '')).strip().lower()
- bere uid a kdyz nenajde uid tak bere jmeno hrace
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
            print(f'OK: {name}')
        except CollectorError as exc:
- zachycuje chyby api
            print(f'SKIP {name}: {exc}')

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
- pauza mezi requesty, ochranuje pred rate limity

    if not rows:
        raise RuntimeError('No rows collected.')

    out = Path(out_csv) = vysledna cesta
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f'Saved {len(rows)} rows to {out}') - vypise hlavicku
    return rows - vrati radky aby se s nimi dalo pracovat

### treti bunka - uid harvesting
def harvest_uids_to_csv(
    target=1500,
    max_attempts=250000,
    out_csv='data/players.csv',
    seed_csv='data/players.csv',
    platform='PC',
    workers=4,
    request_timeout=20.0,
    checkpoint_every=25,
    min_level=25.0,
    min_kills=80.0,
    min_damage=20000.0,
    min_rank_score=1000.0,
    min_nonzero_metrics=3,
    allow_no_gameplay_signal=False,
):
- vstupni parametry

    api_key = load_api_key() - nacte api
    out = Path(out_csv) - vysledna cesta

    seeds = [] - nacte seed UID, bere jen ciselne UID
    if Path(seed_csv).exists():
        with Path(seed_csv).open('r', newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                uid = str(r.get('uid', '')).strip()
                if uid.isdigit():
                    seeds.append(int(uid))

    if not seeds:
        seeds = [2796574388, 1008248071359, 1008995227775, 1003944652988]
- pokud nejsou zadne pouzitelne seeds 

    rows = []
    collected = set()
    seen_probe = set()
    attempts = 0

    def candidate_uid():
        pivot = random.choice(seeds)
        return str(max(1, pivot + random.randint(-25000, 25000)))
- vezme nahodny seed a prohledava v rozmezi -25 000 az +25 000

    def fetch_one(uid):
        try:
            payload = fetch_player_stats_by_uid(uid=uid, api_key=api_key, platform=platform, timeout=request_timeout)
- mapuje payload, zkusi dotaz pres UID
            row = player_to_row(payload)
            if not is_row_usable(
                row,
                min_level=min_level,
                min_kills=min_kills,
                min_damage=min_damage,
                min_rank_score=min_rank_score,
                min_nonzero_metrics=min_nonzero_metrics,
                require_gameplay_signal=not allow_no_gameplay_signal,
            ):
- validace radku
                return None
            return row
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as ex:
- bezi dokud neni target (vysledny pocet radku), nebo maximalni pocet pokusu
        while len(rows) < int(target) and attempts < int(max_attempts):
            batch = []
- sbira nova UID ke zkouseni, nebere duplicity, 
            while len(batch) < max(1, workers * 2) and attempts < int(max_attempts):
                uid = candidate_uid()
                attempts += 1
                if uid in seen_probe:
                    continue
                seen_probe.add(uid)
                batch.append(uid)

            futures = [ex.submit(fetch_one, uid) for uid in batch]
- posle batch paralerne na API
            for fu in as_completed(futures):
- as_completed - zpracovava pozadavky jak prichazeji
                row = fu.result()
                if row is None:
                    continue
                uid = str(row.get('uid', '')).strip()
                if not uid or uid in collected:
                    continue
- filtrace radku
                collected.add(uid)
                rows.append(row)
                seeds.append(int(uid))
- ulozeni validniho radku

                if len(rows) % checkpoint_every == 0:
- checkpoint na zapis radku do CSV
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with out.open('w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                        writer.writeheader()
                        writer.writerows(rows)
                    print(f'Checkpoint: {len(rows)} rows after {attempts} attempts')

            if len(rows) >= int(target):
                break
- kdyz radky dosahnou vysledku tak se loop ukonci

    if not rows:
        raise RuntimeError('No UID rows harvested.')

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
- po skonceni znovu zapise cely CSV

    print(f'Harvest done: {len(rows)} rows after {attempts} attempts -> {out}')
    return rows

## Jednovětý business cíl:
Co přesně appka přinási
- apka je urcena pro rychlou orientacni predikaci hrace, muze mu potvrdit jestli odpovida jeho rank opravdu jeho schopnostem, ci by mel byt vis nebo niz a dava mu i doporuceny setup na postavy, mapy, atd..


Architektura v 5 bodech:
Frontend 
- web fomular prijme hracovo jmeno a platforu pres kterou hraje a vyhodnoti mu predikaci
runtime
- sjednoti vstupni data, vyvola model, dopocit metriky, provede predikaci a pote vystup
data source
- data se berou z DB, pote pres harvester z API a nakonec lokalne z CSV
model artifact
- nasazeny model ulozeny jako bundle ktery obsahuje klasifikator, encoder trid a seznam feature
persistence
- PostgreSQL uklada uzivatele, historii predikaci 


Kvalita modelu v jedné větě:
- kvalita model je silna, velmi silna u nizsich ranku (vice vzorku), mene silna u vetsich ranku (mene vzorku), ale celkove by mela dosahovat 92%


Limity modelu:
- Vzacne/vetsi tirdy ranku maji mene vzroku takze maji horsi recall a precision


Proč RandomForest:
Rychlý baseline, robustní na mixed numerická data, snadná interpretace feature importance.


Verzionování modelu:
Kdy a jak se model obnovuje, co je trigger retréninku.


Monitoring v produkci:
Co sleduješ po nasazení (error rate, response time, fallback rate, distribuce tříd).


Rizika a mitigace:
Rate limits, stale cache, missing columns, schema drift.


Security:
Práce s API key a DB URL jen přes env.


Opravit 2 nepřesnosti:
V notes.md máš „accuracy bere to z F1-score“ (to není přesně pravda) a pár terminologických formulací, které by u zkoušení mohly působit nejistě.
Doporučené „zkouškové“ otázky, na které být ready:

Proč tento model a ne jiný?
Jak poznáš, že model degradoval?
Co se stane, když API/DB vypadne?
Jak bys zlepšil slabé třídy (Master/Predator)?
Jak zajistíš reprodukovatelnost tréninku?