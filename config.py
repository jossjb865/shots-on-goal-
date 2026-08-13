import os
import requests
import numpy as np
from scipy.stats import poisson

ISPORTS_KEY = os.environ.get("ISPORTS_API_KEY")
THESTATS_KEY = os.environ.get("THESTATS_API_KEY")

ISPORTS_PRIMARY = "https://api.isportsapi.com"
ISPORTS_SECONDARY = "https://api2.isportsapi.com"
THESTATS_BASE = "https://api.thestatsapi.com/api/football"

# IDs de Ligas Top (Premier, LaLiga, Serie A, Bundesliga, Ligue 1, Champions)
TOP_LEAGUES = [36, 31, 34, 8, 11, 684]

def call_isports(path, params=None):
    if params is None:
        params = {}
    params['api_key'] = ISPORTS_KEY
    
    try:
        res = requests.get(f"{ISPORTS_PRIMARY}{path}", params=params, timeout=10)
        data = res.json()
        if data.get("code") == 0:
            return data.get("data", [])
    except Exception:
        pass

    try:
        res = requests.get(f"{ISPORTS_SECONDARY}{path}", params=params, timeout=10)
        data = res.json()
        if data.get("code") == 0:
            return data.get("data", [])
    except Exception as e:
        print(f"Error iSportsAPI ({path}): {e}")
        
    return []

def get_thestats_data(path):
    url = f"{THESTATS_BASE}{path}"
    headers = {"Authorization": f"Bearer {THESTATS_KEY}"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        return res.json() if res.status_code == 200 else {}
    except Exception as e:
        print(f"Error TheStatsAPI ({path}): {e}")
        return {}

def get_safe_line(lambda_total, threshold=0.80):
    lines = [3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5]
    safe_line = None
    prob_success = 0.0

    for line in lines:
        k = int(np.floor(line))
        prob_over = 1 - poisson.cdf(k, lambda_total)
        
        if prob_over >= threshold:
            safe_line = f"Over {line}"
            prob_success = prob_over
        else:
            break
            
    return safe_line, prob_success
