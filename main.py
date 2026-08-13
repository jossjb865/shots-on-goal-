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
    """Guarda el reporte en formato Markdown dentro del repositorio."""
    os.makedirs("reportes", exist_ok=True)
    filename = f"reportes/lineas_seguras_{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(content + "\n\n---\n\n")

def extract_averages_from_analysis(analysis_data):
    """
    Parsea la respuesta de /sport/football/analysis para extraer
    los promedios reales de córners y remates (Home/Away).
    """
    if not analysis_data or not isinstance(analysis_data, dict):
        return 0.0, 0.0

    home_recent = analysis_data.get("homeRecent", [])
    away_recent = analysis_data.get("awayRecent", [])

    if not home_recent or not away_recent:
        return 0.0, 0.0

    # Promedio de Córners (Local en casa + Visita fuera)
    home_corners = [float(m.get("homeCorner", 0)) for m in home_recent[:5] if "homeCorner" in m]
    away_corners = [float(m.get("awayCorner", 0)) for m in away_recent[:5] if "awayCorner" in m]
    
    avg_corners = 0.0
    if home_corners and away_corners:
        avg_corners = (sum(home_corners) / len(home_corners)) + (sum(away_corners) / len(away_corners))

    # Promedio de Remates al Arco (Local en casa + Visita fuera)
    home_shots = [float(m.get("homeShotOnGoal", 0)) for m in home_recent[:5] if "homeShotOnGoal" in m]
    away_shots = [float(m.get("awayShotOnGoal", 0)) for m in away_recent[:5] if "awayShotOnGoal" in m]
    
    avg_shots = 0.0
    if home_shots and away_shots:
        avg_shots = (sum(home_shots) / len(home_shots)) + (sum(away_shots) / len(away_shots))

    return avg_corners, avg_shots

def process_top_games():
    print("🚀 Buscando los partidos TOP del día en iSportsAPI...")
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    fixtures = call_isports("/sport/football/schedule", params={"date": today_str})
    
    if not fixtures:
        print("No se obtuvieron partidos programados para la fecha actual.")
        return

    # Priorizar partidos de Ligas Élite
    top_matches = [m for m in fixtures if m.get("leagueId") in TOP_LEAGUES]
    if len(top_matches) < 10:
        top_matches = fixtures[:10]
    else:
        top_matches = top_matches[:10]

    print(f"📌 Procesando {len(top_matches)} partidos seleccionados.")

    for match in top_matches:
        match_id = match.get("matchId")
        home_name = match.get("homeName", "Local")
        away_name = match.get("awayName", "Visita")
        league_id = match.get("leagueId", "N/A")

        # 1. Obtención de estadísticas reales vía /sport/football/analysis
        analysis_data = call_isports("/sport/football/analysis", params={"matchId": match_id})
        
        lambda_corners, lambda_shots = extract_averages_from_analysis(analysis_data)

        # Si el historial no contiene métricas suficientes, buscar respaldo en TheStatsAPI
        if lambda_corners == 0 and lambda_shots == 0:
            stats_fallback = get_thestats_data(f"/matches/{match_id}/stats")
            lambda_corners = float(stats_fallback.get("corners_avg", 0))
            lambda_shots = float(stats_fallback.get("shots_on_target_avg", 0))

        # Si aún no hay datos cuantitativos, omitir evento
        if lambda_corners == 0 and lambda_shots == 0:
            print(f"⚠️ Sin historial/datos suficientes para: {home_name} vs {away_name} (ID: {match_id})")
            continue

        # 2. Obtención de Cuotas reales en iSportsAPI (/sport/football/odds)
        odds_data = call_isports("/sport/football/odds", params={"matchId": match_id})
        market_odds_corners = "N/A"
        market_odds_shots = "N/A"

        if isinstance(odds_data, list) and len(odds_data) > 0:
            bookie = odds_data[0]
            market_odds_corners = bookie.get("corners", {}).get("over_price", "1.80")
            market_odds_shots = bookie.get("shots", {}).get("over_price", "1.85")

        # 3. Motor Poisson (Filtro >= 80% Probabilidad de Acierto)
        safe_corners, prob_c = get_safe_line(lambda_corners, threshold=0.80)
        safe_shots, prob_s = get_safe_line(lambda_shots, threshold=0.80)

        if safe_corners or safe_shots:
            report_text = (
                f"### 🏆 [TOP MATCH] {home_name} vs {away_name}\n"
                f"* **Liga ID:** `{league_id}` | **Match ID:** `{match_id}`\n"
                f"* **Hora de Análisis:** `{datetime.now().strftime('%H:%M:%S')} UTC`\n\n"
            )
            
            if safe_corners:
                report_text += (
                    f"* 🚩 **Córners:** Apuestas a **{safe_corners}**\n"
                    f"  * Proyección Stats: `{lambda_corners:.2f}` | Probabilidad: **{prob_c*100:.1f}%**\n"
                    f"  * Cuota iSportsAPI: `{market_odds_corners}`\n"
                )
            if safe_shots:
                report_text += (
                    f"* 🎯 **Remates al Arco:** Apuestas a **{safe_shots}**\n"
                    f"  * Proyección Stats: `{lambda_shots:.2f}` | Probabilidad: **{prob_s*100:.1f}%**\n"
                    f"  * Cuota iSportsAPI: `{market_odds_shots}`\n"
                )

            print(report_text)
            save_report(report_text)

        time.sleep(0.5)

if __name__ == "__main__":
    process_top_games()
