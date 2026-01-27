# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "flask",
#     "pandas",
# ]
# ///

# ============================================================================
# CONFIGURATION RÉSEAU
# ============================================================================
# Interface réseau sur laquelle écouter :
#   - "0.0.0.0" : Écoute sur toutes les interfaces (accès depuis d'autres machines)
#   - "127.0.0.1" : Écoute uniquement en local (accès depuis cette machine uniquement)
HOST = "0.0.0.0"

# Port d'écoute (changez si le port est bloqué par un EDR/firewall)
# Ports alternatifs courants : 8000, 8080, 8888, 3000, 5001, 5555
PORT = 5000
# ============================================================================

import os
import json
import pandas as pd
import numpy as np
from flask import Flask, render_template, jsonify, request
from dateutil import parser

app = Flask(__name__)

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# Cache global pour éviter de recharger le gros JSON à chaque requête
# Amélioration possible: classe de gestion de cache plus sophistiquée
CACHE = {}

def get_dataframe(filename):
    """Charge et met en cache le DataFrame pandas."""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return None
    
    if filename in CACHE:
        return CACHE[filename]
    
    print(f"Loading {filename}...")
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    # Transformation en liste de dictionnaires plats pour les colonnes principales
    # On garde les attributs complexes (smart_pi) dans une colonne 'raw_attributes' ou on garde le lien via index
    
    extracted_data = []
    for entry in data:
        attrs = entry.get('attributes', {})
        specific_states = attrs.get('specific_states', {})
        
        # Gestion de la position de ext_current_temperature (parfois dans attributes, parfois dans specific_states)
        ext_temp = specific_states.get('ext_current_temperature')
        if ext_temp is None:
            ext_temp = attrs.get('ext_current_temperature')
            
        # Extraction de is_heating via hvac_action
        hvac_action = attrs.get('hvac_action', 'idle')
        is_heating = 1 if hvac_action == 'heating' else 0
        
        extracted_data.append({
            'timestamp': parser.parse(entry['last_updated']), # ou last_changed
            'current_temperature': attrs.get('current_temperature'),
            'temperature': attrs.get('temperature'),
            'ext_current_temperature': ext_temp,
            'hvac_action': hvac_action,
            'is_heating': is_heating,
            'full_entry': entry # Stocker l'entrée complète pour les détails (attention mémoire)
        })
        
    df = pd.DataFrame(extracted_data)
    df = df.sort_values('timestamp')
    df.set_index('timestamp', inplace=True)
    
    # Remove timezone info or convert to common if needed, or keep as is.
    # ECharts gère bien les ISO strings.
    
    CACHE[filename] = df
    print(f"Loaded {len(df)} records.")
    return df

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files')
def list_files():
    """Liste les fichiers JSON disponibles."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.json')]
    return jsonify(files)

@app.route('/api/chart-data/<filename>')
def get_chart_data(filename):
    """Renvoie uniquement les données nécessaires au graphique principal (léger)."""
    df = get_dataframe(filename)
    if df is None:
        return jsonify({'error': 'File not found'}), 404
        
    # On downsample si trop de données? Pour l'instant on envoie tout car step chart
    # Pour un step chart propre, il faut garder les transitions.
    
    # Optimisation: export list of lists or dict of lists
    # ECharts dataset format: source: [['time', 'temp', ...], ...]
    
    # Préparation des colonnes
    # timestamps = df.index.map(lambda x: x.isoformat()).tolist()
    timestamps = df.index.map(lambda x: x.isoformat()).tolist()
    
    # helper to clean nans
    def clean_series(series):
        return [x if pd.notnull(x) else None for x in series]

    curr_temp = clean_series(df['current_temperature'])
    target_temp = clean_series(df['temperature'])
    ext_temp = clean_series(df['ext_current_temperature'])
    is_heating = clean_series(df['is_heating'])
    
    return jsonify({
        'timestamps': timestamps,
        'current_temperature': curr_temp,
        'temperature': target_temp,
        'ext_current_temperature': ext_temp,
        'is_heating': is_heating
    })

@app.route('/api/details/<filename>')
def get_details(filename):
    """Renvoie les détails complets pour un timestamp donné."""
    ts_str = request.args.get('timestamp')
    if not ts_str:
        return jsonify({'error': 'Missing timestamp'}), 400
        
    df = get_dataframe(filename)
    if df is None:
        return jsonify({'error': 'File not found'}), 404
    
    try:
        ts = parser.parse(ts_str)
        # Recherche de l'index le plus proche (method='nearest')
        idx = df.index.get_indexer([ts], method='nearest')[0]
        record = df.iloc[idx]
        
        full_entry = record['full_entry']
        # On peut enrichir ou nettoyer si besoin
        
        return jsonify(full_entry)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print(f"Starting Flask server on {HOST}:{PORT}")
    print(f"Access the application at: http://{HOST if HOST != '0.0.0.0' else 'localhost'}:{PORT}")
    if HOST == "0.0.0.0":
        print(f"Also accessible from other machines using your IP address")
    app.run(debug=True, host=HOST, port=PORT)
