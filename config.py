import os
import requests
import numpy as np
from scipy.stats import poisson

# Claves de API desde GitHub Secrets
THESTATS_KEY = os.environ.get("THESTATS_API_KEY")
ISPORTS_KEY = os.environ.get("ISPORTS_API_KEY")

# Endpoints base
THESTATS_BASE = "https://api.thestatsapi.com/api/v1/football"
ISPORTS_BASE = "https://api.isportsapi.com"

# Ligas Prioritarias en TheStatsAPI (Série A Brasil, Liga MX, Premier, LaLiga, etc.)
TOP_LEAGUES_STATS = [
    "premier-league",
    "la-liga",
    "serie-a",
    "bundesliga",
    "ligue-1",
    "brasileiro-serie-a",
    "liga-mx",
    "champions-league"
]

def call_thestats_api(endpoint, params=None):
    """Conector primario exclusivo para TheStatsAPI vía Bearer Token."""
    if params is None:
        params = {}
    
    url = f"{THESTATS_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {THESTATS_KEY}",
        "Accept": "application/json"
    }
    
    try:
        res = requests.get(url, headers=headers, params=params, timeout=12)
        if res.status_code == 200:
            data = res.json()
            # Retorna data directa o el wrapper segun el schema de TheStatsAPI
            return data.get("data", data)
        else:
            print(f"⚠️ TheStatsAPI HTTP {res.status_code} en {endpoint}")
            return None
    except Exception as e:
        print(f"❌ Error conectando con TheStatsAPI ({endpoint}): {e}")
        return None

def call_isports_odds(match_id):
    """Consulta secundaria de cuotas a iSportsAPI."""
    if not ISPORTS_KEY:
        return "1.83", "1.85"
    
    url = f"{ISPORTS_BASE}/sport/football/odds"
    params = {"api_key": ISPORTS_KEY, "matchId": match_id}
    try:
        res = requests.get(url, params=params, timeout=8)
        data = res.json()
        if data.get("code") == 0 and data.get("data"):
            bookie = data["data"][0]
            c_odds = bookie.get("corners", {}).get("over_price", "1.83")
            s_odds = bookie.get("shots", {}).get("over_price", "1.85")
            return str(c_odds), str(s_odds)
    except Exception:
        pass
    return "1.83", "1.85"

def get_safe_line(lambda_total, threshold=0.80):
    """
    Motor Cuantitativo Poisson
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
