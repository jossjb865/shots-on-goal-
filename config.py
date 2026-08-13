import os
import requests
import numpy as np
from scipy.stats import poisson

# Configuración de API Keys desde GitHub Secrets
ISPORTS_KEY = os.environ.get("ISPORTS_API_KEY")
THESTATS_KEY = os.environ.get("THESTATS_API_KEY")

# Endpoints base confirmados
ISPORTS_PRIMARY = "https://api.isportsapi.com"
ISPORTS_SECONDARY = "https://api2.isportsapi.com"
THESTATS_BASE = "https://api.thestatsapi.com/api/football"

# --- MOTOR CUANTITATIVO: POISSON (SAFE LINE >= 80%) ---
def get_safe_line(lambda_total, threshold=0.80):
    """
    Calcula la línea de Over más alta cuya probabilidad acumulada Poisson sea >= 80%
    """
    lines = [3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5]
    safe_line = None
    prob_success = 0.0

    for line in lines:
        k = int(np.floor(line))
        # P(X > line) = 1 - CDF(k)
        prob_over = 1 - poisson.cdf(k, lambda_total)
        
        if prob_over >= threshold:
            safe_line = f"Over {line}"
            prob_success = prob_over
        else:
            break
            
    return safe_line, prob_success

# --- CONEXIÓN A ISPORTSAPI ---
def call_isports(path, params=None):
    if params is None:
        params = {}
    params['api_key'] = ISPORTS_KEY
    
    # Intento en servidor primario
    try:
        res = requests.get(f"{ISPORTS_PRIMARY}{path}", params=params, timeout=10)
        data = res.json()
        if data.get("code") == 0:
            return data.get("data", [])
    except Exception:
        pass

    # Fallback automático al servidor secundario (api2)
    try:
        res = requests.get(f"{ISPORTS_SECONDARY}{path}", params=params, timeout=10)
        data = res.json()
        if data.get("code") == 0:
            return data.get("data", [])
    except Exception as e:
        print(f"Error crítico en iSportsAPI ({path}): {e}")
        
    return []

# --- CONEXIÓN A THESTATSAPI ---
def get_thestats_odds(match_id, live=False):
    suffix = "/odds/live" if live else "/odds"
    url = f"{THESTATS_BASE}/matches/{match_id}{suffix}"
    headers = {"Authorization": f"Bearer {THESTATS_KEY}"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        return res.json() if res.status_code == 200 else {}
    except Exception as e:
        print(f"Error TheStatsAPI Odds ({match_id}): {e}")
        return {}

def get_thestats_player_odds(match_id):
    url = f"{THESTATS_BASE}/matches/{match_id}/odds/players"
    headers = {"Authorization": f"Bearer {THESTATS_KEY}"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        return res.json() if res.status_code == 200 else {}
    except Exception as e:
        print(f"Error TheStatsAPI Player Odds ({match_id}): {e}")
        return {}
