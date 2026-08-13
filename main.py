import os
import time
from datetime import datetime, timezone
from config import (
    call_thestats_api,
    call_isports_odds,
    get_safe_line,
    TOP_COMPETITIONS
)

def save_report(content):
    """Guarda el reporte en la carpeta /reportes del repositorio."""
    os.makedirs("reportes", exist_ok=True)
    filename = f"reportes/lineas_seguras_{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(content + "\n\n---\n\n")

def get_team_stats_avg(team_id, last_n=5):
    """
    Obtiene los partidos finalizados del equipo y calcula sus promedios
    reales de córners y remates a partir de /football/matches/{match_id}/stats
    """
    if not team_id:
        return 0.0, 0.0

    # 1. Partidos finalizados del equipo
    matches_res = call_thestats_api("/football/matches", params={
        "team_id": team_id,
        "status": "finished",
        "per_page": last_n
    })

    if not matches_res or "data" not in matches_res:
        return 0.0, 0.0

    finished_matches = matches_res.get("data", [])
    if not finished_matches:
        return 0.0, 0.0

    corners_list = []
    shots_list = []

    # 2. Iterar cada partido para extraer /stats
    for m in finished_matches:
        match_id = m.get("id")
        if not match_id:
            continue

        stats_res = call_thestats_api(f"/football/matches/{match_id}/stats")
        if not stats_res or "data" not in stats_res:
            continue

        stats_data = stats_res.get("data", {})
        
        # Determinar si el equipo jugó de Local o Visitante en ese partido
        is_home = (m.get("home_team", {}).get("id") == team_id)
        prefix = "home" if is_home else "away"

        # Extraer métricas del payload
        c = stats_data.get(f"{prefix}_corners") or stats_data.get("corners", {}).get(prefix) or 0
        s = stats_data.get(f"{prefix}_shots_on_target") or stats_data.get("shots_on_target", {}).get(prefix) or 0

        corners_list.append(float(c))
        shots_list.append(float(s))

    avg_c = (sum(corners_list) / len(corners_list)) if corners_list else 0.0
    avg_s = (sum(shots_list) / len(shots_list)) if shots_list else 0.0

    return avg_c, avg_s

def process_pipeline():
    print("🚀 Consultando partidos programados desde TheStatsAPI...")
    
    # 1. Obtener partidos programados
    scheduled_res = call_thestats_api("/football/matches", params={
        "status": "scheduled",
        "per_page": 100
    })

    if not scheduled_res or "data" not in scheduled_res:
        print("❌ No se pudieron recuperar partidos programados. Revisa la THESTATS_API_KEY.")
        return

    raw_matches = scheduled_res.get("data", [])
    print(f"📊 Total de eventos recuperados: {len(raw_matches)}. Filtrando jornada...")

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    todays_matches = []

    for match in raw_matches:
        utc_date_str = str(match.get("utc_date", ""))
        if today_str in utc_date_str or not utc_date_str:
            todays_matches.append(match)

    print(f"📌 Partidos seleccionados para hoy ({today_str}): {len(todays_matches)}")

    # Si no hay partidos exactamente para hoy, se toma una muestra de los primeros 15
    candidates = todays_matches if len(todays_matches) > 0 else raw_matches[:15]

    # Ordenar por competiciones de mayor importancia
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
        match_id = match.get("id")
        comp_name = match.get("competition", {}).get("name", "Competición")
        
        home_team_obj = match.get("home_team", {})
        away_team_obj = match.get("away_team", {})

        home_id = home_team_obj.get("id")
        away_id = away_team_obj.get("id")

        home_name = home_team_obj.get("name", "Local")
        away_name = away_team_obj.get("name", "Visita")

        # 2. Extracción de Promedios Históricos Reales
        home_c_avg, home_s_avg = get_team_stats_avg(home_id, last_n=5)
        away_c_avg, away_s_avg = get_team_stats_avg(away_id, last_n=5)

        lambda_corners = home_c_avg + away_c_avg
        lambda_shots = home_s_avg + away_s_avg

        # Si no hay suficiente historial registrado para los equipos, omitir
        if lambda_corners == 0 and lambda_shots == 0:
            print(f"⚠️ Omitido [Sin historial suficiente en /stats]: {home_name} vs {away_name}")
            continue

        processed_count += 1

        # 3. Consulta de cuotas en iSportsAPI
        c_odds, s_odds = call_isports_odds(match_id)

        # 4. Cálculo del Modelo Poisson (Probabilidad >= 80%)
        safe_corners, prob_c = get_safe_line(lambda_corners, threshold=0.80) if lambda_corners > 0 else (None, 0)
        safe_shots, prob_s = get_safe_line(lambda_shots, threshold=0.80) if lambda_shots > 0 else (None, 0)

        if safe_corners or safe_shots:
            picks_count += 1
            report_text = (
                f"### 🏆 [PICK REAL THESTATSAPI] {home_name} vs {away_name}\n"
                f"* **Competición:** `{comp_name}` | **ID:** `{match_id}`\n"
                f"* **Hora de Análisis:** `{datetime.now().strftime('%H:%M:%S')} UTC`\n\n"
            )
            
            if safe_corners:
                report_text += (
                    f"* 🚩 **Córners:** Apuesta a **{safe_corners}**\n"
                    f"  * Proyección Real ($\lambda$): `{lambda_corners:.2f}` (Local: {home_c_avg:.1f} + Visita: {away_c_avg:.1f})\n"
                    f"  * Probabilidad Calculada: **{prob_c*100:.1f}%**\n"
                    f"  * Cuota Referencia: `{c_odds}`\n"
                )
            if safe_shots:
                report_text += (
                    f"* 🎯 **Remates al Arco:** Apuesta a **{safe_shots}**\n"
                    f"  * Proyección Real ($\lambda$): `{lambda_shots:.2f}` (Local: {home_s_avg:.1f} + Visita: {away_s_avg:.1f})\n"
                    f"  * Probabilidad Calculada: **{prob_s*100:.1f}%**\n"
                    f"  * Cuota Referencia: `{s_odds}`\n"
                )

            print(report_text)
            save_report(report_text)

        time.sleep(0.2)

    print(f"\n✅ Pipeline finalizado: {processed_count} eventos evaluados con promedios reales. {picks_count} picks generados con proba ≥ 80%.")

if __name__ == "__main__":
    process_pipeline()
