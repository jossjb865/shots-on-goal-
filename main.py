import os
import time
from datetime import datetime
from config import (
    call_thestats_api,
    call_isports_odds,
    get_safe_line,
    TOP_LEAGUES_STATS
)

def save_report(content):
    """Guarda el reporte cuantitativo en formato Markdown."""
    os.makedirs("reportes", exist_ok=True)
    filename = f"reportes/lineas_seguras_{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(content + "\n\n---\n\n")

def parse_thestats_metrics(match_detail):
    """
    Extrae de forma precisa los promedios/expectativas reales 
    desde el objeto de TheStatsAPI.
    """
    if not match_detail or not isinstance(match_detail, dict):
        return None, None

    # Mapeo de campos estadísticos avanzados de TheStatsAPI
    stats = match_detail.get("stats", match_detail)
    expectations = match_detail.get("expectations", {})
    
    # Busca la media o expectativa calculada por TheStatsAPI
    lambda_corners = (
        expectations.get("expected_corners") or 
        stats.get("corners_avg") or 
        stats.get("corners_total_mean")
    )
    
    lambda_shots = (
        expectations.get("expected_shots_on_target") or 
        stats.get("shots_on_target_avg") or 
        stats.get("shots_on_target_mean")
    )

    # Si vienen desglosadas por equipo Local y Visitante en TheStatsAPI, las suma:
    if lambda_corners is None:
        home_c = stats.get("home_corners_avg", 0)
        away_c = stats.get("away_corners_avg", 0)
        if home_c > 0 or away_c > 0:
            lambda_corners = float(home_c) + float(away_c)

    if lambda_shots is None:
        home_s = stats.get("home_shots_on_target_avg", 0)
        away_s = stats.get("away_shots_on_target_avg", 0)
        if home_s > 0 or away_s > 0:
            lambda_shots = float(home_s) + float(away_s)

    # Conversión estricta a float
    try:
        c_val = float(lambda_corners) if lambda_corners else None
        s_val = float(lambda_shots) if lambda_shots else None
        return c_val, s_val
    except (ValueError, TypeError):
        return None, None

def process_thestats_pipeline():
    print("🚀 Iniciando Motor Cuantitativo centrado exclusivamente en TheStatsAPI...")
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # 1. Obtener accesorios/partidos del día desde TheStatsAPI
    fixtures = call_thestats_api("/matches", params={"date": today_str})
    
    if not fixtures or not isinstance(fixtures, list):
        print("ℹ️ Probando consulta de proximos eventos en TheStatsAPI...")
        fixtures = call_thestats_api("/fixtures/upcoming")
        
    if not fixtures or not isinstance(fixtures, list):
        print("❌ No se pudieron recuperar eventos desde TheStatsAPI. Revisa la validez de THESTATS_API_KEY.")
        return

    print(f"📊 {len(fixtures)} eventos recuperados desde TheStatsAPI. Filtrando datos...")

    analyzed_count = 0
    picks_count = 0

    for match in fixtures:
        match_id = match.get("id") or match.get("match_id")
        home_team = match.get("home_team", {}).get("name") or match.get("home_name", "Local")
        away_team = match.get("away_team", {}).get("name") or match.get("away_name", "Visita")
        league_slug = match.get("league", {}).get("slug", "desconocida")

        # 2. Consultar el endpoint de estadísticas detalladas para el evento en TheStatsAPI
        match_detail = call_thestats_api(f"/matches/{match_id}")
        if not match_detail:
            match_detail = call_thestats_api(f"/stats/{match_id}")

        lambda_corners, lambda_shots = parse_thestats_metrics(match_detail or match)

        # REGLA DE ORO DE UN APOSTADOR FRÍO: Si no hay datos duros reales de TheStatsAPI, SE DESCARTA.
        if lambda_corners is None and lambda_shots is None:
            print(f"⚠️ Omitido [Sin datos cuantitativos en TheStatsAPI]: {home_team} vs {away_team}")
            continue

        analyzed_count += 1

        # 3. Obtener cuotas de mercado (Referencia)
        c_odds, s_odds = call_isports_odds(match_id)

        # 4. Cálculo de Distribución Poisson (Umbral ≥ 80%)
        safe_corners, prob_c = get_safe_line(lambda_corners, threshold=0.80) if lambda_corners else (None, 0)
        safe_shots, prob_s = get_safe_line(lambda_shots, threshold=0.80) if lambda_shots else (None, 0)

        # Si se valida alguna Línea Segura, se emite el Pick
        if safe_corners or safe_shots:
            picks_count += 1
            report_text = (
                f"### 🏆 [PICK THESTATSAPI] {home_team} vs {away_team}\n"
                f"* **Liga:** `{league_slug}` | **ID TheStatsAPI:** `{match_id}`\n"
                f"* **Fecha/Hora:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC`\n\n"
            )
            
            if safe_corners:
                report_text += (
                    f"* 🚩 **Córners:** Apuesta a **{safe_corners}**\n"
                    f"  * Proyección Real TheStatsAPI ($\lambda$): `{lambda_corners:.2f}`\n"
                    f"  * Probabilidad Matemáticamente Calculada: **{prob_c*100:.1f}%**\n"
                    f"  * Cuota Referencia: `{c_odds}`\n"
                )
            if safe_shots:
                report_text += (
                    f"* 🎯 **Remates al Arco:** Apuesta a **{safe_shots}**\n"
                    f"  * Proyección Real TheStatsAPI ($\lambda$): `{lambda_shots:.2f}`\n"
                    f"  * Probabilidad Matemáticamente Calculada: **{prob_s*100:.1f}%**\n"
                    f"  * Cuota Referencia: `{s_odds}`\n"
                )

            print(report_text)
            save_report(report_text)

        time.sleep(0.2)

    print(f"\n✅ Análisis completado: {analyzed_count} partidos procesados con datos reales de TheStatsAPI. {picks_count} picks detectados con proba ≥ 80%.")

if __name__ == "__main__":
    process_thestats_pipeline()
