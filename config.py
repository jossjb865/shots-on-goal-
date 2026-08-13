import os
import requests
import numpy as np
from scipy.stats import poisson

# Claves de API desde GitHub Secrets
ISPORTS_KEY = os.environ.get("ISPORTS_API_KEY")
THESTATS_KEY = os.environ.get("THESTATS_API_KEY")

# Endpoints base
ISPORTS_PRIMARY = "https://api.isportsapi.com"
ISPORTS_SECONDARY = "https://api2.isportsapi.com"
THESTATS_BASE = "https://api.thestatsapi.com/api/football"

# IDs Oficiales iSportsAPI para Ligas Élite
TOP_LEAGUES = [
    31,    # LaLiga (España)
    36,    # Premier League (Inglaterra)
    34,    # Serie A (Italia)
    8,     # Bundesliga (Alemania)
    11,    # Ligue 1 (Francia)
    684,   # UEFA Champions League
    118,   # Liga MX
    1987   # Brasileirão Serie A
]

def call_isports(path, params=None):
    """Conector a iSportsAPI con conmutación automática en caso de error."""
    if params is None:
        params = {}
    params['api_key'] = ISPORTS_KEY
    
    # Intento 1: Servidor Principal
    try:
        res = requests.get(f"{ISPORTS_PRIMARY}{path}", params=params, timeout=10)
        data = res.json()
        if data.get("code") == 0:
            return data.get("data", [])
    except Exception:
        pass

    # Intento 2: Servidor Secundario (api2)
    try:
        res = requests.get(f"{ISPORTS_SECONDARY}{path}", params=params, timeout=10)
        data = res.json()
        if data.get("code") == 0:
            return data.get("data", [])
    except Exception as e:
        print(f"Error en iSportsAPI ({path}): {e}")
        
    return []

def get_thestats_data(path):
    """Conector a TheStatsAPI con autenticación por Bearer Token."""
    url = f"{THESTATS_BASE}{path}"
    headers = {"Authorization": f"Bearer {THESTATS_KEY}"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        return res.json() if res.status_code == 200 else {}
    except Exception as e:
        print(f"Error en TheStatsAPI ({path}): {e}")
        return {}

def get_safe_line(lambda_total, threshold=0.80):
    """
    Motor Cuantitativo: Calcula la línea de Over más alta 
    con probabilidad acumulada Poisson >= 80%
    """
    if lambda_total <= 0:
        return None, 0.0

    lines = [3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5]
    safe_line = None
    prob_success = 0.0

    for line in lines:
        k = int(np.floor(line))
        # Probabilidad P(X > line) = 1 - CDF(k)
        prob_over = 1 - poisson.cdf(k, lambda_total)
        
        if prob_over >= threshold:
            safe_line = f"Over {line}"
            prob_success = prob_over
        else:
            break
            
    return safe_line, prob_success
