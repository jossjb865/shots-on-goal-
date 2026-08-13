import os
import time
from datetime import datetime
from config import (
    call_isports,
    get_thestats_data,
    get_safe_line,
    TOP_LEAGUES
)

def save_report(content):
    """Guarda las alertas en la carpeta /reportes del repositorio."""
    os.makedirs("reportes", exist_ok=True)
    filename = f"reportes/lineas_seguras_{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(content + "\n\n---\n\n")

def extract_averages(analysis_data):
    """
    Extrae dinámicamente el promedio de córners y remates.
    Soporta múltiples estructuras JSON de iSportsAPI.
    """
    if not analysis_data or not isinstance(analysis_data, dict):
        return 9.5, 8.5 # Media histórica global por defecto si la API omite el desglose

    home_recent = analysis_data.get("homeRecent", [])
    away_recent = analysis_data.get("awayRecent", [])

    c_vals = []
    s_vals = []

    # Extraer de partidos recientes del Local
    for m in home_recent[:5]:
        c = m.get("homeCorner") or m.get("corners") or m.get("home_corner")
        s = m.get("homeShotOnGoal") or m.get("shotsOnGoal") or m.get("home_shots")
        if c is not None: c_vals.append(float(c))
        if s is not None: s_vals.append(float(s))

    # Extraer de partidos recientes de la Visita
    for m in away_recent[:5]:
        c = m.get("awayCorner") or m.get("corners") or m.get("away_corner")
        s = m.get("awayShotOnGoal") or m.get("shotsOnGoal") or m.get("away_shots")
        if c is not None: c_vals.append(float(c))
        if s is not None: s_vals.append(float(s))

    # Si se encontraron datos en el JSON se calcula la media, si no, se usa baseline cuantitativo
    avg_corners = (sum(c_vals) / len(c_vals)) if c_vals else 9.6
    avg_shots = (sum(s_vals) / len(s_vals)) if s_vals else 8.4

    return avg_corners, avg_shots

def process_top_games():
    print("🚀 Buscando los 10 partidos TOP y procesando cuotas/métricas...")
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    fixtures = call_isports("/sport/football/schedule", params={"date": today_str})
    
    if not fixtures:
        # Fallback si se consulta en una hora donde el schedule de hoy está vacío
        fixtures = call_isports("/sport/football/schedule")
        
    if not fixtures:
        print("❌ No se obtuvieron partidos de iSportsAPI.")
        return

    # Priorizar por Ligas Top o tomar los primeros 10 disponibles
    top_matches = [m for m in fixtures if m.get("leagueId") in TOP_LEAGUES]
    if len(top_matches) < 10:
        top_matches = fixtures[:10]
    else:
        top_matches = top_matches[:10]

    print(f"📌 Procesando {len(top_matches)} partidos con el Motor Poisson...")

    for match in top_matches:
        match_id = match.get("matchId")
        home_name = match.get("homeName", "Local")
        away_name = match.get("awayName", "Visita")
        league_id = match.get("leagueId", "N/A")

        # 1. Obtención y extracción de promedios cuantitativos
        analysis_data = call_isports("/sport/football/analysis", params={"matchId": match_id})
        lambda_corners, lambda_shots = extract_averages(analysis_data)

        # 2. Extracción de cuotas reales (/sport/football/odds)
        odds_data = call_isports("/sport/football/odds", params={"matchId": match_id})
        market_odds_corners = "1.83"
        market_odds_shots = "1.85"

        if isinstance(odds_data, list) and len(odds_data) > 0:
            bookie = odds_data[0]
            # Mapeo de cuotas según la respuesta de la API
            c_odds = bookie.get("corners", {}).get("over_price") or bookie.get("handicap", {}).get("over")
            s_odds = bookie.get("shots", {}).get("over_price") or bookie.get("handicap", {}).get("over")
            if c_odds: market_odds_corners = str(c_odds)
            if s_odds: market_odds_shots = str(s_odds)

        # 3. Motor Poisson (Filtro Estricto >= 80% Probabilidad de Acierto)
        safe_corners, prob_c = get_safe_line(lambda_corners, threshold=0.80)
        safe_shots, prob_s = get_safe_line(lambda_shots, threshold=0.80)

        if safe_corners or safe_shots:
            report_text = (
                f"### 🏆 [PICK DETECTADO] {home_name} vs {away_name}\n"
                f"* **Liga ID:** `{league_id}` | **Match ID:** `{match_id}`\n"
                f"* **Hora de Análisis:** `{datetime.now().strftime('%H:%M:%S')} UTC`\n\n"
            )
            
            if safe_corners:
                report_text += (
                    f"* 🚩 **Córners:** Apuesta a **{safe_corners}**\n"
                    f"  * Proyección ($\lambda$): `{lambda_corners:.2f}` | Probabilidad: **{prob_c*100:.1f}%**\n"
                    f"  * Cuota Referencia iSportsAPI: `{market_odds_corners}`\n"
                )
            if safe_shots:
                report_text += (
                    f"* 🎯 **Remates al Arco:** Apuesta a **{safe_shots}**\n"
                    f"  * Proyección ($\lambda$): `{lambda_shots:.2f}` | Probabilidad: **{prob_s*100:.1f}%**\n"
                    f"  * Cuota Referencia iSportsAPI: `{market_odds_shots}`\n"
                )

            print(report_text)
            save_report(report_text)

        time.sleep(0.3)

if __name__ == "__main__":
    process_top_games()
