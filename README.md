# ApexTracking

ApexTracking is a Flask web application that predicts Apex player rank from profile stats and provides practical in-game recommendations.

## Features

- Rank prediction (single classifier model)
- Rank confidence
- Promotion chance
- Demotion risk
- Recommendation block:
	- best map
	- best legend
	- best drop location
	- recommended role
	- play style
- Rank Probability Profile (class probabilities shown per rank)
- Last 5 matches (API history when available, otherwise transparent estimate)
- Auth, guest mode, prediction history, and leaderboard

## Runtime Architecture

- Web entry point: src/web.py
- Prediction orchestration: src/prediction_runtime.py
- Data source resolver: src/player_source.py
- Model wrapper: src/predictor.py
- Prediction logic and metrics: src/predictor_logic.py
- API client facade: src/apex_api.py
- Payload mapping and validation: src/apex_payload_mapper.py
- DB facade: src/auth_store.py
- DB modules: src/db_core.py, src/db_users.py, src/db_predictions.py, src/db_cache.py
- Frontend: templates/index.html, static/style.css

## Model

The current production pipeline uses one model:
- rank_model (classifier)

Stored bundle:
- model/model.pkl

Bundle keys:
- rank_model
- label_encoder
- feature_columns

## Notebooks

- notebook.ipynb: model training and export
- notebook_data_collection.ipynb: data collection workflows

## Environment Variables

Required:
- DATABASE_URL
- APEX_API_KEY
- FLASK_SECRET_KEY

## Database

PostgreSQL tables:
- users
- predictions
- player_cache

## Local Run

1. Install dependencies
- pip install -r requirements.txt

2. Set environment variables
- DATABASE_URL
- APEX_API_KEY
- FLASK_SECRET_KEY

3. Start app
- python -m src.web

## Deploy (Render)

Recommended configuration:
- Build command: pip install -r requirements.txt
- Start command: python -m src.web
- Runtime: Python

## Tests

Unit tests:
- tests/test_collector.py
- tests/test_predictor_logic.py

Run:
- python -m unittest tests.test_collector tests.test_predictor_logic

## Data Origin

Training data is collected via Apex API workflows (project-owned collection), then cleaned and prepared for training.
