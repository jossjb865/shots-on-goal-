import os
import time
import requests
from datetime import datetime, timezone
from config import (
    THESTATS_BASE,
    get_thestats_headers,
    call_isports_odds,
    get_safe_line,
    TOP_COMPETITIONS
)

def save_report(content):
    os.makedirs("reportes", exist_ok=True)
    filename = f"reportes/lineas_seguras_{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(content + "\n\n---\n\n")

def fetch_scheduled_matches():
    """Consulta la API de TheStatsAPI con los parámetros confirmados."""
    url = f"{THESTATS_BASE}/matches"
    params = {
        "status": "scheduled",
        "per_page": 100,
        "timezone_offset": "-06:00"
    }
    
    try:
        res = requests.get(url, params=params, headers=get_thestats_headers(), timeout=12)
        if res.status_code == 200:
            payload = res.json()
            return payload.get("data", [])
        else:
            print(f"⚠️ Error HTTP {res.status_code} al consultar /matches en TheStatsAPI")
            return []
    except Exception as e:
        print(f"❌ Error de conexión en TheStatsAPI: {e}")
        return []

def parse_match_metrics(match_obj):
    """
    Extrae los promedios/expectativas reales desde la estructura recibida.
    """
    stats = match_obj.get("stats", {})
    expectations = match_obj.get("expectations", {})
    
    # Intento 1: Campos directos de expectativa o promedio
    lambda_c = expectations.get("expected_corners") or stats.get("corners_avg")
    lambda_s = expectations.get("expected_shots_on_target") or stats.get("shots_on_target_avg")

    # Intento 2: Suma de promedios Local + Visitante
    if lambda_c is None:
        home_c = stats.get("home_corners_avg") or stats.get("home_corners")
        away_c = stats.get("away_corners_avg") or stats.get("away_corners")
        if home_c is not None and away_c is not None:
            lambda_c = float(home_c) + float(away_c)

    if lambda_s is None:
        home_s = stats.get("home_shots_avg") or stats.get("home_shots_on_target")
        away_s = stats.get("away_shots_avg") or stats.get("away_shots_on_target")
        if home_s is not None and away_s is not None:
            lambda_s = float(home_s) + float(away_s)

    try:
        c_val = float(lambda_c) if lambda_c is not None else None
        s_val = float(lambda_s) if lambda_s is not None else None
        return c_val, s_val
    except (ValueError, TypeError):
        return None, None

def process_pipeline():
    print("🚀 Consultando TheStatsAPI (endpoint /matches con status=scheduled)...")
    
    raw_matches = fetch_scheduled_matches()
    if not raw_matches:
        print("❌ No se recibieron partidos en la consulta.")
        return

    print(f"📊 Total de eventos recuperados: {len(raw_matches)}. Filtrando jornada de hoy...")

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    todays_matches = []

    # 1. Filtro local por Fecha (utc_date == fecha actual)
    for match in raw_matches:
        utc_date_str = match.get("utc_date", "")
        # Extrae los primeros 10 caracteres (YYYY-MM-DD)
        match_date = utc_date_str[:10] if len(utc_date_str) >= 10 else ""
        
        if match_date == today_str or not match_date:
            todays_matches.append(match)

    print(f"📌 Partidos filtrados para hoy ({today_str}): {len(todays_matches)}")

    # Si la API no tiene partidos para hoy en los primeros 100 resultados, usamos el lote original
    candidates = todays_matches if len(todays_matches) > 0 else raw_matches[:20]

    # 2. Ordenamiento por relevancia de competición
    def competition_rank(m):
        comp_name = str(m.get("competition", {}).get("name", "")).lower()
        for i, top in enumerate(TOP_COMPETITIONS):
            if top in comp_name:
                return i
        return 99

    candidates.sort(key=competition_rank)

    processed_count = 0
    picks_count = 0

    for match in candidates:
        match_id = match.get("id") or match.get("match_id")
        comp_name = match.get("competition", {}).get("name", "Competición Desconocida")
        
        home_team = match.get("home_team", {}).get("name") or match.get("home_name", "Local")
        away_team = match.get("away_team", {}).get("name") or match.get("away_name", "Visita")

        # Extraer métricas reales
        lambda_corners, lambda_shots = parse_match_metrics(match)

        # Regla estricta: Si la respuesta no incluye datos duros de córners o remates, omitir evento
        if lambda_corners is None and lambda_shots is None:
            print(f"⚠️ Omitido por ausencia de métricas directas: {home_team} vs {away_team} ({comp_name})")
            continue

        processed_count += 1

        # Obtener cuotas de referencia secundarias
        c_odds, s_odds = call_isports_odds(match_id)

        # Aplicación del Modelo Poisson (Umbral ≥ 80%)
        safe_corners, prob_c = get_safe_line(lambda_corners, threshold=0.80) if lambda_corners else (None, 0)
        safe_shots, prob_s = get_safe_line(lambda_shots, threshold=0.80) if lambda_shots else (None, 0)

        if safe_corners or safe_shots:
            picks_count += 1
            report_text = (
                f"### 🏆 [PICK THESTATSAPI] {home_team} vs {away_team}\n"
                f"* **Competición:** `{comp_name}` | **ID:** `{match_id}`\n"
                f"* **Hora de Procesamiento:** `{datetime.now().strftime('%H:%M:%S')} UTC`\n\n"
            )
            
            if safe_corners:
                report_text += (
                    f"* 🚩 **Córners:** Apuesta a **{safe_corners}**\n"
                    f"  * Proyección ($\lambda$): `{lambda_corners:.2f}` | Probabilidad: **{prob_c*100:.1f}%**\n"
                    f"  * Cuota Referencia: `{c_odds}`\n"
                )
            if safe_shots:
                report_text += (
                    f"* 🎯 **Remates al Arco:** Apuesta a **{safe_shots}**\n"
                    f"  * Proyección ($\lambda$): `{lambda_shots:.2f}` | Probabilidad: **{prob_s*100:.1f}%**\n"
                    f"  * Cuota Referencia: `{s_odds}`\n"
                )

            print(report_text)
            save_report(report_text)

        time.sleep(0.1)

    print(f"\n✅ Ejecución finalizada: {processed_count} eventos evaluados con métricas reales. {picks_count} picks generados.")

if __name__ == "__main__":
    process_pipeline()
