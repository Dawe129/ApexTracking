# ApexTracking - poznamky k obhajobe

Tento dokument je interni podklad na uceni cele aplikace. Je napsany tak, aby slo rychle vysvetlit:
- co aplikace dela,
- odkud berou data,
- jak funguje model,
- co se uklada do databaze,
- jak je to hostovane,
- kde je co v kodu.

## 1) Co je to za aplikaci
ApexTracking je web aplikace ve Flasku, ktera po zadani hrace:
- nacte jeho statistiky,
- predikuje rank, damage/game a win rate,
- navrhne herni setup (mapa, legenda, drop, role, styl),
- ukaze poslednich 5 her (z API, nebo odhad pokud API historii neposle).

Aplikace ma 3 rezimy uzivatele:
- auth obrazovka (login/register),
- guest (vyhledavani + leaderboard),
- user (vlastni ucet + historie predikci + vlastni Apex profil).

## 2) Kde je co v kodu
Hlavni soubory:
- src/web.py: hlavni Flask aplikace, request flow, form actions, render sablony.
- src/player_source.py: rozhoduje odkud se vezmou data hrace (DB cache, API, fallback CSV).
- src/collector.py: API fetch + parsovani payloadu na numerickou feature row.
- src/predictor.py: nacteni modelu a inference (rank, damage, win rate + recommendation engine).
- src/auth_store.py: PostgreSQL vrstva (users, predictions, player_cache).
- notebook.ipynb: trenink modelu a export model bundle.
- src/leaderboard.py: nacteni a formatovani top leaderboardu.
- templates/index.html: frontend sablona.
- static/style.css: styly UI.

Data a model:
- data/players.csv nebo data/players_ready.csv: treninkovy dataset.
- data/leaderboard_top.csv: tabulka top hracu pro zobrazeni.
- model/model.pkl: natrenovany model bundle.

Testy:
- tests/test_collector.py
- tests/test_predictor_logic.py

## 3) Jak tece request v praxi
Vstupni endpoint je / v src/web.py.

Zakladni tok:
1. Uzivatel odesle formular (predict, login, register, predict_my...).
2. Web vrstva zavola _run_prediction(player, platform).
3. _run_prediction zavola resolve_player_row v player_source.py.
4. player_source vrati feature row + zdroj dat (db/api/local).
5. ApexPredictor v predictor.py udela inference.
6. web.py pripravi result slovnik pro sablonu.
7. templates/index.html vykresli vystup.

U prihlaseneho uzivatele se po predikci uklada zaznam do predictions tabulky.

## 4) Odkud se berou statistiky hrace
Rozhoduje src/player_source.py v AUTO rezimu:
1. Nejdric DB cache (player_cache v PostgreSQL).
2. Pokud cache nema zaznam, vola se API (mozambiquehe.re bridge).
3. Pokud API selze, fallback lokalni CSV.

Co dela collector.py:
- fetch_player_stats udela HTTP request na API.
- player_to_row rozparsuje payload do feature sloupcu:
  level, rank_score, kills, damage, headshots, games_played, wins, kdr, damage_per_game.
- kdyz API neposle kompletni data, pouzivaji se fallback odhady.
- nove taky vytahuje recent_matches (pokud API vrati historii zapasu).

## 5) Co se predikuje
Model vraci:
- predicted_rank
- predicted_damage_per_game
- predicted_win_rate

V predictor.py navic bezi logika:
- kalibrace damage predikce podle realnych vstupu hrace,
- kalibrace win rate,
- score-based recommendation engine pro mapu/legendu/drop/role/style,
- variabilni, ale deterministicke doporuceni (neni porad stejny vysledek pro vsechny).

## 6) Poslednich 5 her
Aplikace ukazuje sekci Poslednich 5 her:
- pokud API posle historii, zobrazi se realne hodnoty (placement, kills, damage, outcome),
- pokud API historii neposle, v web.py se dopocte realisticky odhad 5 her podle statistik.

To je dulezite rict u obhajoby:
- historie je best effort data,
- ne vsechny profily maji plny telemetry payload,
- proto je fallback transparentne oznaceny jako estimate.

## 7) Databaze (PostgreSQL)
Pouziva se DATABASE_URL, bez ni app nenastartuje.

Tabulky v auth_store.py:
1. users
- id, email, password_hash, apex_player, apex_platform, created_at

2. predictions
- user_id, queried_player, resolved_player, predicted_rank,
  predicted_damage_per_game, source, created_at

3. player_cache
- player_key, platform, row_json, updated_at

K cemu slouzi:
- users: auth a propojeni vlastniho Apex uctu.
- predictions: historie predikci pro user dashboard.
- player_cache: rychlejsi opakovane dotazy na stejneho hrace.

## 8) Jak jsem sbiral data
Datovy zdroj je Apex API bridge (mozambiquehe.re).

Pouzite cesty:
- manualni sber podle jmen,
- uid harvester pro vetsi pocet unikatnich profilu,
- fallback/synteticke cisteni datasetu pro konzistentni trenink.

Po sberu se data cisti a mapuji na stejne feature schema, aby slo trenovat stabilne.

## 9) Jak jsem trenoval model
Trenink je pouze v notebook.ipynb.

Pipeline:
1. Nacist CSV.
2. Osetrit numericke sloupce.
3. Pripravit targety:
- rank (klasifikace),
- damage/game (regrese),
- win rate (regrese).
4. Train/test split.
5. Natrenovat random forest modely.
6. Ulozit bundle do model/model.pkl (komprimovane).

Dulezita optimalizace:
- model byl zmenseny (mensi complexity + komprese),
- kvuli RAM limitu Render Free instance.

## 10) Leaderboard
Leaderboard je v src/leaderboard.py.

Princip:
- cte data z data/leaderboard_top.csv (fallback players_ready.csv),
- prevede numeriku,
- odfiltruje nerealisticke profily,
- seradi podle rank tier + rank score + damage/kdr/wins,
- vraci top 50 pro UI.

## 11) Hosting (Render)
Deploy je na Render Web Service.

Nastaveni:
- Build command: pip install -r requirements.txt
- Start command: python -m src.web
- Root directory: prazdne

Env promenne:
- DATABASE_URL
- APEX_API_KEY
- FLASK_SECRET_KEY

Databaze:
- Render PostgreSQL sluzba (persistentni).

Proc PostgreSQL:
- SQLite soubor by na ephemeral hostingu nebyl spolehlivy,
- PostgreSQL drzi data i po restartu/novem deployi.

## 12) Co rict u obhajoby (strucna verze)
1. Aplikace je Flask web s auth, API ingestem, ML predikci a recommendation vrstvou.
2. Data flow je DB cache -> API -> fallback dataset.
3. Predikce bezi z model bundle (rank, damage, win rate).
4. Doporuceni je score-based logika, ne natvrdo if-else pro vsechny stejne.
5. Persistence je v PostgreSQL (users, predictions, player_cache).
6. App bezi na Renderu, model byl optimalizovan pro RAM limity.

## 13) Co zkontrolovat kdyz neco nefunguje
1. 404 na root:
- overit Start Command a ze bezi spravna service.

2. Padani instance:
- velikost modelu a RAM limit planu.

3. Nefunguje login/historie:
- overit DATABASE_URL a tabulky v PostgreSQL.

4. Divne predikce:
- zkontrolovat vstupni row z collectoru,
- zkontrolovat kalibraci v predictor.py.

5. API nic nevraci:
- overit APEX_API_KEY,
- overit rate-limit/timeout,
- fallback behavior.

## 14) Rychla priprava pred obhajobou
1. Otevrit app a ukazat login + predikci.
2. Ukazat ze se uklada historie predikci.
3. Ukazat leaderboard.
4. Ukazat Poslednich 5 her.
5. Strucne vysvetlit data flow a PostgreSQL tabulky.
