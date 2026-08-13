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
    """Guarda el reporte formateado en la carpeta /reportes del repositorio."""
    os.makedirs("reportes", exist_ok=True)
    filename = f"reportes/lineas_seguras_{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(content + "\n\n---\n\n")

def process_top_games():
    print("🚀 Buscando los 10 partidos TOP del día...")
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    fixtures = call_isports("/sport/football/schedule", params={"date": today_str})
    
    if not fixtures:
        print("No se obtuvieron partidos de iSportsAPI para la fecha actual.")
        return

    # Priorizar partidos de Ligas Élite
    top_matches = [m for m in fixtures if m.get("leagueId") in TOP_LEAGUES]
    
    # Si hay menos de 10 en ligas élite, tomar los primeros 10 disponibles
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

        # 1. Extracción dinámica de estadísticas en TheStatsAPI (/matches/{match_id}/stats)
        stats_data = get_thestats_data(f"/matches/{match_id}/stats")
        
        # Parseo de Lambdas (se leen métricas directas del JSON o fallback a 0)
        lambda_corners = float(
            stats_data.get("corners_avg", 
            stats_data.get("expected_corners", 
            stats_data.get("corners", {}).get("total_avg", 0)))
        )
        lambda_shots = float(
            stats_data.get("shots_on_target_avg", 
            stats_data.get("expected_shots", 
            stats_data.get("shots", {}).get("on_target_avg", 0)))
        )

        # Si no existen estadísticas suficientes para este evento, omitir
        if lambda_corners == 0 and lambda_shots == 0:
            print(f"⚠️ Sin datos cuantitativos suficientes para: {home_name} vs {away_name} (ID: {match_id})")
            continue

        # 2. Extracción dinámica de cuotas en iSportsAPI (/sport/football/odds)
        odds_data = call_isports("/sport/football/odds", params={"matchId": match_id})
        
        market_odds_corners = "N/A"
        market_odds_shots = "N/A"

        if isinstance(odds_data, list) and len(odds_data) > 0:
            # Obtiene cuota del primer operador disponible
            bookie = odds_data[0]
            market_odds_corners = bookie.get("corners", {}).get("over_price", "N/A")
            market_odds_shots = bookie.get("shots", {}).get("over_price", "N/A")

        # 3. Evaluación en el Motor Poisson (Filtro >= 80% Probabilidad)
        safe_corners, prob_c = get_safe_line(lambda_corners, threshold=0.80)
        safe_shots, prob_s = get_safe_line(lambda_shots, threshold=0.80)

        # Si alguna métrica supera el umbral del 80%, redacta el reporte
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
