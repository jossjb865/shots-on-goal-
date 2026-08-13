import os
import requests
import numpy as np
from scipy.stats import poisson

THESTATS_KEY = os.environ.get("THESTATS_API_KEY")
ISPORTS_KEY = os.environ.get("ISPORTS_API_KEY")

THESTATS_BASE = "https://api.thestatsapi.com/api"
ISPORTS_BASE = "https://api.isportsapi.com"

# Ligas Élite para filtrar (IDs o Keywords)
TOP_COMPETITIONS = [
    "premier league", "la liga", "laliga", "serie a", "bundesliga",
    "ligue 1", "champions league", "brasileirao", "liga mx", "copa libertadores"
]

def get_thestats_headers():
    """Autenticación exacta según la documentación oficial de TheStatsAPI."""
    return {
        "x-api-key": THESTATS_KEY,
        "Accept": "application/json"
    }

def call_thestats_api(path, params=None):
    """Conector base para TheStatsAPI."""
    url = f"{THESTATS_BASE}{path}"
    try:
        res = requests.get(url, headers=get_thestats_headers(), params=params, timeout=10)
        if res.status_code == 200:
            return res.json()
        else:
            print(f"⚠️ HTTP {res.status_code} en endpoint {path}")
            return None
    except Exception as e:
        print(f"❌ Error conectando a TheStatsAPI ({path}): {e}")
        return None

def call_isports_odds(match_id):
    """Consulta secundaria de cuotas en iSportsAPI."""
    if not ISPORTS_KEY:
        return "N/A", "N/A"
    
    url = f"{ISPORTS_BASE}/sport/football/odds"
    params = {"api_key": ISPORTS_KEY, "matchId": match_id}
    try:
        res = requests.get(url, params=params, timeout=8)
        data = res.json()
        if data.get("code") == 0 and data.get("data"):
            bookie = data["data"][0]
            c_odds = bookie.get("corners", {}).get("over_price", "N/A")
            s_odds = bookie.get("shots", {}).get("over_price", "N/A")
            return str(c_odds), str(s_odds)
    except Exception:
        pass
    return "N/A", "N/A"

def get_safe_line(lambda_total, threshold=0.80):
    """
    Motor Poisson Quantitative Engine
    Calcula la línea de Over más alta con P(X > k) >= 80%
    """
    if not lambda_total or lambda_total <= 0:
        return None, 0.0

    lines = [3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5]
    safe_line = None
    prob_success = 0.0

    for line in lines:
        k = int(np.floor(line))
        prob_over = 1.0 - poisson.cdf(k, lambda_total)
        
        if prob_over >= threshold:
            safe_line = f"Over {line}"
            prob_success = prob_over
        else:
            break
            
    return safe_line, prob_success
