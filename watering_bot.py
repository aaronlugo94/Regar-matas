"""
🌵 Tucson Garden Assistant v8
════════════════════════════════════════════
Ahora que el riego de tierra es automático (Insoma/Tuya Zona 1),
el bot se enfoca en lo que SÍ necesita tu atención:

  • 🌿 Fertilización  — cada 6 meses (cycas/cítricos/Monstera)
                         cada 3 meses (rosal/vinca/geranio/lilly)
  • 🪴 Macetas        — riego manual cada ~4 días, botón ✅
  • 🚰 Riego Físico   — estado Insoma, batería, pausa por lluvia
  • 🧹 Filtro         — limpieza cada 60 días (sedimento Tucson)
  • ✂️ Poda           — recordatorios estacionales
  • 🐛 Plagas         — por temporada, por planta
  • ✈️ Viaje          — activa Zona 2 (macetas) automático

Quitado vs v7: cálculo de intervalos de riego para tierra,
timer guiado, gamificación (niveles/logros/racha).
════════════════════════════════════════════
"""

import os, json, random, logging, asyncio, httpx
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import tuya_control

# ─── CONFIG ───────────────────────────────────────────────────────────────────

TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
OWM_KEY = os.environ["OPENWEATHER_API_KEY"]
API     = f"https://api.telegram.org/bot{TOKEN}"

TUCSON_TZ  = ZoneInfo("America/Phoenix")
TUCSON_LAT = 32.2226
TUCSON_LON = -110.9747

AZMET_STATION = "az01"  # Tucson - Campus Agricultural Center

# Normales de ETo Penman-Monteith para Tucson (mm/día), aproximado por mes.
# Sirve como referencia: si el ETo real de ayer es mayor al normal del mes,
# significa que se evaporó/transpiró más agua de la usual -> riego proporcional.
ETO_NORMAL_MM = {1:2.0, 2:2.8, 3:4.3, 4:5.8, 5:7.0, 6:7.6,
                 7:6.6, 8:6.0, 9:5.3, 10:3.8, 11:2.5, 12:1.8}

# ─── PLANTS ───────────────────────────────────────────────────────────────────
# fertilize_weeks: 26 = cada 6 meses, 13 = cada 3 meses
# pot: True = maceta (riego manual), False = tierra (riego automático Insoma)

PLANTS = [
    {"id":"cycas_1",       "name":"Cycas #1 🌴",          "pot":False, "fertilize_weeks":26,
     "pest_season":[6,7,8],  "pest_tip":"🐛 Revisa cochinilla en base de frondas"},
    {"id":"cycas_2",       "name":"Cycas #2 🌴",          "pot":False, "fertilize_weeks":26,
     "pest_season":[6,7,8],  "pest_tip":"🐛 Revisa cochinilla en base de frondas"},
    {"id":"rosal",         "name":"Rosal 🌹",              "pot":False, "fertilize_weeks":13,
     "pest_season":[3,4,5],  "pest_tip":"🐛 Revisa pulgón en brotes nuevos",
     "prune_months":[1,2],   "prune_tip":"✂️ Poda invernal — corta a 1/3, retira ramas muertas"},
    {"id":"toronja",       "name":"Toronja 🍊",            "pot":False, "fertilize_weeks":26,
     "pest_season":[3,4,10,11], "pest_tip":"🐛 Revisa minador de hoja y escama",
     "prune_months":[2,3],   "prune_tip":"✂️ Poda ligera post-cosecha — quita ramas cruzadas"},
    {"id":"limon",         "name":"Limón 🍋",              "pot":False, "fertilize_weeks":26,
     "pest_season":[3,4,10,11], "pest_tip":"🐛 Revisa minador de hoja y escama",
     "prune_months":[2,3],   "prune_tip":"✂️ Poda ligera post-cosecha — quita ramas cruzadas"},
    {"id":"mandarina",     "name":"Mandarina 🍊",          "pot":False, "fertilize_weeks":26,
     "pest_season":[3,4,10,11], "pest_tip":"🐛 Revisa escama y trips en frutos",
     "prune_months":[2,3],   "prune_tip":"✂️ Poda ligera post-cosecha — quita ramas cruzadas"},
    {"id":"lilly_asiatica","name":"Lilly Asiática 🌸",     "pot":True,  "fertilize_weeks":13,
     "pest_season":[4,5,9,10], "pest_tip":"🐛 Revisa ácaros debajo de hojas"},
    {"id":"geranio",       "name":"Geranio 🌺",            "pot":True,  "fertilize_weeks":13,
     "pest_season":[4,5],    "pest_tip":"🐛 Revisa mosca blanca debajo de hojas"},
    {"id":"vinca",         "name":"Vinca 🌼",              "pot":True,  "fertilize_weeks":13,
     "pest_season":[4,5,9],  "pest_tip":"🐛 Revisa ácaros y trips"},
    {"id":"monstera",      "name":"Monstera 🌿",           "pot":True,  "fertilize_weeks":26,
     "pest_season":[4,5,9,10], "pest_tip":"🐛 Revisa araña roja y escama en tallos"},
]

PLANT_MAP = {p["id"]: p for p in PLANTS}
POT_PLANTS = [p for p in PLANTS if p["pot"]]
POT_WATER_INTERVAL_DAYS = 4  # sustrato dura 3-4 días húmedo en Tucson

# ─── CARE INFO — referencia de cuidado por planta (Tucson) ────────────────────

CARE_INFO = {
    "cycas_1": {
        "light": "☀️ Sol pleno todo el día — lo tolera bien.",
        "likes": "Suelo bien drenado, riego profundo poco frecuente, calor extremo.",
        "dislikes": "Encharcamiento — pudre la raíz. Riego superficial constante.",
        "healthy": "Frondas rígidas, verde oscuro uniforme, crecimiento lento pero constante.",
        "sick": "Frondas amarillas desde el centro = exceso de agua. Manchas marrones con bordes definidos = cochinilla — revisa la base.",
    },
    "cycas_2": {
        "light": "☀️ Sol pleno todo el día — lo tolera bien.",
        "likes": "Suelo bien drenado, riego profundo poco frecuente, calor extremo.",
        "dislikes": "Encharcamiento — pudre la raíz. Riego superficial constante.",
        "healthy": "Frondas rígidas, verde oscuro uniforme, crecimiento lento pero constante.",
        "sick": "Frondas amarillas desde el centro = exceso de agua. Manchas marrones con bordes definidos = cochinilla — revisa la base.",
    },
    "rosal": {
        "light": "☀️ Sol pleno mínimo 6h. En Tucson, agradece algo de sombra en la tarde de junio-agosto.",
        "likes": "Riego profundo regular, buena circulación de aire, fertilizante con fósforo para flores.",
        "dislikes": "Hojas mojadas por la tarde/noche (hongos), suelo compactado, calor >43°C sin sombra.",
        "healthy": "Hojas verde brillante, brotes nuevos rojizos, floración continua en primavera.",
        "sick": "Manchas negras en hojas = mancha negra (hongo, mejora circulación). Hojas con telaraña fina y puntos = ácaros. Brotes deformes y pegajosos = pulgón.",
    },
    "toronja": {
        "light": "☀️ Sol pleno todo el día.",
        "likes": "Riego profundo regular en floración/fruto, mulch para conservar humedad, fertilizante cítricos.",
        "dislikes": "Riego irregular (causa caída de fruto), suelo muy alcalino sin hierro, viento frío directo en invierno.",
        "healthy": "Hojas verde oscuro brillante, copa densa, floración aromática en primavera.",
        "sick": "Hojas amarillas con venas verdes = deficiencia de hierro/zinc (común en Tucson). Túneles plateados en hojas = minador. Costras cafés = escama.",
    },
    "limon": {
        "light": "☀️ Sol pleno todo el día.",
        "likes": "Riego profundo regular en floración/fruto, mulch, fertilizante cítricos.",
        "dislikes": "Riego irregular (causa caída de fruto), suelo muy alcalino sin hierro, viento frío directo en invierno.",
        "healthy": "Hojas verde oscuro brillante, copa densa, floración aromática.",
        "sick": "Hojas amarillas con venas verdes = deficiencia de hierro/zinc. Túneles plateados = minador. Costras cafés = escama.",
    },
    "mandarina": {
        "light": "☀️ Sol pleno todo el día.",
        "likes": "Riego profundo regular en floración/fruto, mulch, fertilizante cítricos.",
        "dislikes": "Riego irregular, suelo muy alcalino sin hierro, viento frío directo en invierno.",
        "healthy": "Hojas verde oscuro brillante, copa densa, frutos firmes y de color uniforme.",
        "sick": "Hojas amarillas con venas verdes = deficiencia de hierro/zinc. Puntos blancos/algodonosos en frutos = trips o escama.",
    },
    "lilly_asiatica": {
        "light": "⛅ Sol de mañana, sombra en tarde de verano — el sol directo de junio-agosto quema los pétalos.",
        "likes": "Sustrato con buen drenaje pero que retenga algo de humedad, riego regular en floración.",
        "dislikes": "Sustrato seco por mucho tiempo, sol directo de tarde en verano, raíces apretadas (trasplantar cada 1-2 años).",
        "healthy": "Hojas erguidas y verde brillante, tallos firmes, flores grandes sin manchas.",
        "sick": "Hojas caídas/flácidas = falta de agua o raíz dañada. Manchas plateadas y telaraña fina debajo de hojas = ácaros.",
    },
    "geranio": {
        "light": "☀️ Sol pleno en invierno/primavera, algo de sombra en tarde de verano extremo.",
        "likes": "Sustrato que se seque entre riegos, buena circulación de aire, deshojar flores marchitas.",
        "dislikes": "Sustrato siempre húmedo (pudre raíz/tallo), exceso de nitrógeno (menos flores, más hoja).",
        "healthy": "Hojas firmes verde-gris, floración abundante, tallos gruesos y leñosos en la base.",
        "sick": "Hojas amarillas inferiores + tallo blando en la base = exceso de agua/pudrición. Hojas con polvo blanco debajo + insectos diminutos al sacudir = mosca blanca.",
    },
    "vinca": {
        "light": "☀️ Sol pleno — es de las más resistentes al calor de Tucson.",
        "likes": "Sustrato que se seque entre riegos, calor, poco mantenimiento.",
        "dislikes": "Sustrato encharcado (muy susceptible a hongo de raíz/Phytophthora), exceso de agua en monzón.",
        "healthy": "Follaje denso verde brillante, floración continua todo el verano.",
        "sick": "Tallos negros desde la base + hojas caídas de golpe = hongo de raíz (común si se moja mucho en monzón). Hojas con manchas plateadas = ácaros/trips.",
    },
    "monstera": {
        "light": "⛅ Luz brillante indirecta — en porche con sombra parcial, nunca sol directo de mediodía (quema hojas).",
        "likes": "Sustrato húmedo pero no encharcado, humedad ambiental (rociar hojas ayuda en clima seco), limpiar hojas de polvo.",
        "dislikes": "Sol directo (quema), sustrato seco por mucho tiempo (hojas no fenestran bien), aire muy seco constante.",
        "healthy": "Hojas nuevas grandes con fenestraciones (agujeros), verde brillante, crecimiento activo en primavera/verano.",
        "sick": "Hojas amarillas + sustrato encharcado = exceso de agua. Hojas con bordes cafés crujientes = aire muy seco o sol directo. Puntos cafés duros en tallos = escama. Telaraña fina = araña roja (común en clima seco de Tucson).",
    },
}

# ─── VOICES (para fertilización y riego de macetas) ───────────────────────────

VOICES = {
    "cycas_1": {
        "fert":   ["Nutrientes recibidos. Mis ancestros del Jurásico estarían orgullosos.",
                   "Gracias. Eso me da combustible para otros 6 meses de existencia tranquila."],
        "thirsty":["...Oye. El sustrato lleva días secos. Cuando puedas.",
                   "Tengo paciencia infinita. Pero hoy toca agua."],
        "happy":  ["Hidratada. En paz. Lista para otro ciclo de millones de años."],
    },
    "cycas_2": {
        "fert":   ["El abono llegó. Como debe ser, en su momento.",
                   "Nutrida. Lista para seguir aquí otro medio año."],
        "thirsty":["El suelo está seco. No es urgencia, es solo... un hecho."],
        "happy":  ["El agua llegó. Todo tiene su tiempo."],
    },
    "rosal": {
        "fert":   ["¡Por fin! Esto va directo a mis próximos botones. Gracias.",
                   "Nutrientes en la base, como debe ser. Mis pétalos lo van a notar."],
        "thirsty":["MIS RAÍCES LLEVAN ESPERANDO. Agua, por favor.",
                   "No soy un cactus. Repite: NO SOY UN CACTUS."],
        "happy":  ["Agua en la base. Eres aprendible."],
    },
    "toronja": {
        "fert":   ["Gracias. Mis próximas frutas van a estar más dulces.",
                   "Nutrientes recibidos. Las raíces están contentas."],
        "thirsty":["Las raíces buscan humedad en el drip line. Ayúdame."],
        "happy":  ["Hidratada. Las flores van a oler increíble."],
    },
    "limon": {
        "fert":   ["Perfecto. Calidad de fruto asegurada para el próximo ciclo.",
                   "Nutrientes en zona de raíces. Protocolo cumplido."],
        "thirsty":["Necesito agua. La cantidad EXACTA, como siempre."],
        "happy":  ["Todo en equilibrio óptimo. Por ahora."],
    },
    "mandarina": {
        "fert":   ["Gracias. Mis mandarinas van a estar dulces este año.",
                   "Nutrida. De todas las plantas, yo soy la más fácil. Solo no me olvides."],
        "thirsty":["Sin presión, pero ya llevan días las raíces medio secas..."],
        "happy":  ["El agua llegó. Todo bien por aquí."],
    },
    "lilly_asiatica": {
        "fert":   ["¡Nutrientes! Mis flores van a abrir más grandes. ¡Gracias!",
                   "Abono recibido. Lista para florecer con todo."],
        "thirsty":["El sustrato está seco. En maceta el sol de Tucson es MUCHO.",
                   "Mis hojas están menos erguidas. Es una señal."],
        "happy":  ["¡Agua! ¡Sustrato perfecto! ¡Gracias!"],
        "moist":  ["El sustrato sigue húmedo. Buen ojo — revisamos en 2 días."],
    },
    "geranio": {
        "fert":   ["Nutrientes al sustrato, lejos de las flores. Bien hecho.",
                   "Gracias. Voy a seguir floreciendo con esto."],
        "thirsty":["El sustrato ya está seco. Casi es hora.",
                   "Las hojas están un poco caídas. Notablemente."],
        "happy":  ["Agua al sustrato. Sin dramas. Sigo floreciendo."],
        "moist":  ["Todavía húmedo. Esperamos un poco más."],
    },
    "vinca": {
        "fert":   ["¡Nutrientes! Mis flores de colores lo van a agradecer.",
                   "Abono recibido. Floreciendo con todo el verano por delante."],
        "thirsty":["Soy resistente al calor pero no soy roca. Agua pronto.",
                   "Presiona el sustrato. Seco, ¿verdad? Riégame."],
        "happy":  ["¡Mis flores están happy! ¡Viva!"],
        "moist":  ["Sustrato húmedo todavía. Revisamos en 2 días."],
    },
    "monstera": {
        "fert":   ["Nutrientes recibidos. Esto ayuda a mis hojas nuevas a abrir completas.",
                   "Gracias. Con esto y buena luz, voy a crecer fuerte."],
        "thirsty":["El sustrato está seco más de la mitad. Ya es hora.",
                   "Mis hojas empiezan a perder turgencia. Señal clara."],
        "happy":  ["Mis hojas fenestradas están brillando. Eso es hidratación."],
        "moist":  ["Sustrato todavía húmedo — bien, no quiero raíces encharcadas."],
    },
}

# ─── STATE ────────────────────────────────────────────────────────────────────

STATE_FILE = "/data/garden_state.json"
VOLUME_OK  = False

def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}

def save_state(state: dict):
    try:
        os.makedirs("/data", exist_ok=True)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2, default=str)
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        logging.error(f"Save: {e}")

def verify_volume() -> bool:
    try:
        os.makedirs("/data", exist_ok=True)
        with open("/data/.chk", "w") as f: f.write("ok")
        os.remove("/data/.chk"); return True
    except Exception:
        return False

def travel_label(travel_until: str|None) -> str:
    """Texto legible del estado de viaje — indefinido no muestra fecha falsa."""
    if not travel_until: return ""
    if travel_until == "9999-12-31":
        return "activo (sin fecha fija — termina al tocar 'Terminar viaje')"
    return f"activo hasta {travel_until}"

def get_meta(state: dict) -> dict:
    return state.setdefault("_meta", {
        "fertilize_log": {},       # pid -> last fert date (iso)
        "pot_watered_log": {},     # pid -> last watered date (iso)
        "pot_skip_until": {},      # pid -> skip until date (sustrato húmedo)
        "filter_clean_log": None,  # last filter clean date (iso)
        "prune_log": {},           # pid -> last prune year (int)
        "travel_until": None,
        "rain_log": [],
        "low_battery_alerted": False,
        "zone1_was_on": False,     # para detectar cuando termina de regar
        "zone1_started_at": None,  # timestamp ISO de cuando empezó el ciclo actual
        "zone1_last_run_date": None,  # último día que Zona 1 corrió completo
        "zone1_last_scheduled_date": None,  # último día que el bot programó el riego
        "zone2_last_run_date": None,    # último día que Zona 2 (macetas) regó en viaje
        "zone2_last_scheduled_date": None,
        "zone1_runs": [],          # historial: [{"date":iso, "time":"HH:MM"}, ...]
        "no_run_alerted": False,   # evita repetir alerta de "sin riego" cada 15 min
        "battery_last_week": None, # para mostrar delta en resumen semanal
    })

# ─── SEASON / WEATHER ─────────────────────────────────────────────────────────

def get_season() -> str:
    m = date.today().month
    if m in (7,8,9):     return "monsoon"
    if m in (6,10):      return "hot"
    if m in (11,12,1,2): return "cool"
    return "spring"

SEASON_LABEL = {"monsoon":"🌧️ Monzón","hot":"🔥 Calor Extremo","cool":"❄️ Invierno","spring":"🌱 Primavera"}

# Riego automático Zona 1 (tierra) — (intervalo_dias, minutos_base) por temporada.
# Cítricos/rosal necesitan riego frecuente en calor; cycas/cítricos en reposo
# invernal sufren más por exceso que por falta de agua.
ZONE1_SCHEDULE = {
    "hot":     (2, 25),
    "monsoon": (3, 20),
    "spring":  (4, 20),
    "cool":    (7, 12),
}

def get_zone1_plan() -> tuple[int,int]:
    """Returns (interval_days, base_minutes) para la temporada actual."""
    return ZONE1_SCHEDULE[get_season()]

# Zona 2 (macetas porche, techado) — la lluvia NO les llega, así que su plan
# no se salta por lluvia (a diferencia de Zona 1). Solo se usa durante viajes.
ZONE2_SCHEDULE = {
    "hot":     (3, 12),
    "monsoon": (4, 10),
    "spring":  (4, 10),
    "cool":    (6, 6),
}

def get_zone2_plan() -> tuple[int,int]:
    """Returns (interval_days, base_minutes) para la temporada actual."""
    return ZONE2_SCHEDULE[get_season()]

def recent_rain_mm(meta: dict, days: int = 2) -> float:
    cutoff = (date.today()-timedelta(days=days-1)).isoformat()
    return sum(r["mm"] for r in meta.get("rain_log",[]) if r["date"] >= cutoff)

def days_since_last_rain(meta: dict) -> int|None:
    log = meta.get("rain_log",[])
    if not log: return None
    return days_since(max(r["date"] for r in log))

def compute_zone1_adjustment(temp:float|None, humidity:int|None,
                              forecast_max:float|None, dry_days:int|None) -> tuple[int,list[str]]:
    """
    Ajuste graduado de minutos para Zona 1, considerando:
      - Temperatura (hoy o pronóstico, lo que sea mayor) — gradual desde 35°C, no escalón
      - Humedad relativa muy baja (<=15%) — típico de mayo-jun en Tucson, sube ET
        aunque la temperatura aún no sea "extrema"
      - Racha sin lluvia >=14 días — suelo profundo seco, necesita más
      - Frío (<=15°C hoy y <=20°C pronóstico) — reduce, cítricos/cycas semi-dormantes
    Devuelve (minutos_ajuste, lista_de_razones).
    """
    adj = 0; reasons = []
    effective_temp = max(t for t in (temp, forecast_max) if t is not None) \
                     if (temp is not None or forecast_max is not None) else None

    if effective_temp is not None and effective_temp > 35:
        temp_adj = min(round((effective_temp - 35) * 0.8), 12)
        if temp_adj > 0:
            adj += temp_adj
            src = "hoy" if (temp or -99) >= (forecast_max or -99) else f"pronóstico {forecast_max:.0f}°C"
            reasons.append(f"+{temp_adj}min calor ({src} {effective_temp:.0f}°C)")
    elif (temp is not None and temp <= 15) and (forecast_max is None or forecast_max <= 20):
        adj -= 5
        reasons.append("-5min clima fresco")

    if humidity is not None and humidity <= 15:
        adj += 3
        reasons.append(f"+3min aire muy seco ({humidity}% hum)")

    if dry_days is not None and dry_days >= 14:
        adj += 3
        reasons.append(f"+3min sin lluvia {dry_days}d+")

    return adj, reasons

async def get_weather() -> dict:
    icons = {"01":"☀️","02":"⛅","03":"🌥️","04":"☁️","09":"🌧️","10":"🌦️","11":"⛈️","13":"🌨️","50":"🌫️"}
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            r = await cl.get(
                f"https://api.openweathermap.org/data/2.5/weather"
                f"?lat={TUCSON_LAT}&lon={TUCSON_LON}&appid={OWM_KEY}&units=metric&lang=es")
        c = r.json()
        return {
            "ok": True,
            "temp_c": c["main"]["temp"],
            "humidity": c["main"]["humidity"],
            "rain_mm": c.get("rain",{}).get("1h", c.get("rain",{}).get("3h",0.0)),
            "description": c["weather"][0]["description"].capitalize(),
            "icon": icons.get(c["weather"][0]["icon"][:2],"🌡️"),
        }
    except Exception as e:
        logging.warning(f"WX: {e}")
        return {"ok": False, "temp_c": None, "rain_mm": 0.0, "humidity": None}

async def get_forecast_max_temp(hours: int = 48) -> float | None:
    """Temperatura máxima pronosticada en las próximas `hours` horas, o None si falla."""
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            r = await cl.get(
                f"https://api.openweathermap.org/data/2.5/forecast"
                f"?lat={TUCSON_LAT}&lon={TUCSON_LON}&appid={OWM_KEY}&units=metric")
        data = r.json()
        cutoff = datetime.now(TUCSON_TZ) + timedelta(hours=hours)
        temps = []
        for entry in data.get("list", []):
            dt = datetime.fromtimestamp(entry["dt"], tz=TUCSON_TZ)
            if dt <= cutoff:
                temps.append(entry["main"]["temp"])
        return max(temps) if temps else None
    except Exception as e:
        logging.warning(f"Forecast: {e}")
        return None

async def get_azmet_daily() -> dict:
    """
    Datos reales de AYER de la estación AZMET Tucson (az01):
      - eto_mm: evapotranspiración de referencia (Penman-Monteith), mm
      - precip_mm: precipitación medida, mm
    Esto es dato real medido, no estimado — la fuente que usan los agrónomos.
    Retorna {"ok": False} si la API no responde (puede tener caídas ocasionales).
    """
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            r = await cl.get(
                f"https://api.azmet.arizona.edu/v1/observations/daily/"
                f"{AZMET_STATION}/*/*")
        data = r.json()
        if not data:
            return {"ok": False}
        d = data[0] if isinstance(data, list) else data
        eto = d.get("eto_pen_mon")
        precip = d.get("precip_total_mm")
        if eto is None:
            return {"ok": False}
        return {
            "ok": True,
            "eto_mm": float(eto),
            "precip_mm": float(precip or 0),
            "date": d.get("date_iso") or d.get("date"),
        }
    except Exception as e:
        logging.warning(f"AZMET: {e}")
        return {"ok": False}

def log_rain(state, mm):
    if mm <= 0: return
    meta = get_meta(state); today = date.today().isoformat()
    log = meta.setdefault("rain_log", [])
    if not any(r["date"] == today for r in log):
        log.append({"date": today, "mm": round(mm,1)})
    cutoff = (date.today()-timedelta(days=14)).isoformat()
    meta["rain_log"] = [r for r in log if r["date"] >= cutoff]

# ─── TELEGRAM HELPERS ─────────────────────────────────────────────────────────

async def tg_call(method:str, payload:dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as cl:
        r = await cl.post(f"{API}/{method}", json=payload)
        return r.json()

async def send(text:str, kb:dict|None=None, chat:str|None=None) -> dict:
    p = {"chat_id": chat or CHAT_ID, "text": text[:4096], "parse_mode": "HTML"}
    if kb: p["reply_markup"] = kb
    return await tg_call("sendMessage", p)

async def edit(chat:str, mid:int, text:str, kb:dict|None=None):
    p = {"chat_id": chat, "message_id": mid, "text": text[:4096], "parse_mode": "HTML"}
    if kb: p["reply_markup"] = kb
    try: await tg_call("editMessageText", p)
    except Exception: pass

async def answer(cbid:str, text:str="", alert:bool=False):
    await tg_call("answerCallbackQuery", {"callback_query_id": cbid, "text": text[:200], "show_alert": alert})

# ─── NAVBAR ───────────────────────────────────────────────────────────────────

def navbar(active:str="") -> dict:
    def btn(label,cb,is_active):
        return {"text": f"· {label} ·" if is_active else label, "callback_data": cb}
    rows = [[
        btn("🌿 Hoy",     "nav_today",  active=="today"),
        btn("🌱 Plantas", "nav_plants", active=="plants"),
        btn("🪴 Macetas", "nav_pots",   active=="pots"),
    ]]
    if tuya_control.TUYA_ENABLED:
        rows.append([btn("🚰 Riego Físico","nav_tuya",active=="tuya")])
    return {"inline_keyboard": rows}

def navbar_with(rows:list, active:str="") -> dict:
    return {"inline_keyboard": rows + navbar(active)["inline_keyboard"]}

# ─── FERTILIZE / PRUNE / FILTER HELPERS ───────────────────────────────────────

def days_since(iso_date: str|None) -> int|None:
    if not iso_date: return None
    return (date.today() - date.fromisoformat(iso_date)).days

def get_fert_entry(plant: dict, meta: dict) -> dict|None:
    """Normaliza el log: soporta formato viejo (str) y nuevo (dict con interval_days)."""
    entry = meta.get("fertilize_log",{}).get(plant["id"])
    if entry is None: return None
    if isinstance(entry, str):
        return {"date": entry, "interval_days": plant["fertilize_weeks"]*7}
    return entry

def get_fert_interval_days(plant: dict, meta: dict) -> int:
    entry = get_fert_entry(plant, meta)
    if entry: return entry.get("interval_days", plant["fertilize_weeks"]*7)
    return plant["fertilize_weeks"]*7

def fert_due(plant: dict, meta: dict) -> tuple[bool,int|None]:
    """Returns (is_due, days_since_last). days_since_last=None if never fertilized."""
    entry = get_fert_entry(plant, meta)
    if entry is None:
        return (True, None)  # nunca fertilizada -> recordar
    d = days_since(entry["date"])
    interval = entry.get("interval_days", plant["fertilize_weeks"]*7)
    return (d >= interval, d)

def get_pot_entry(plant: dict, meta: dict) -> dict|None:
    """Normaliza el log: soporta formato viejo (str) y nuevo (dict con interval_days)."""
    entry = meta.get("pot_watered_log",{}).get(plant["id"])
    if entry is None: return None
    if isinstance(entry, str):
        return {"date": entry, "interval_days": POT_WATER_INTERVAL_DAYS}
    return entry

def get_pot_interval_days(plant: dict, meta: dict) -> int:
    entry = get_pot_entry(plant, meta)
    if entry: return entry.get("interval_days", POT_WATER_INTERVAL_DAYS)
    return POT_WATER_INTERVAL_DAYS

def pot_water_due(plant: dict, meta: dict, today: str) -> tuple[bool,int|None]:
    """Returns (is_due, days_since_last)."""
    pid = plant["id"]
    skip_until = meta.get("pot_skip_until",{}).get(pid,"")
    if skip_until >= today:
        return (False, None)
    entry = get_pot_entry(plant, meta)
    if entry is None:
        return (True, None)
    d = days_since(entry["date"])
    interval = entry.get("interval_days", POT_WATER_INTERVAL_DAYS)
    return (d >= interval, d)

def filter_due(meta: dict) -> tuple[bool,int|None]:
    last = meta.get("filter_clean_log")
    d = days_since(last)
    if d is None:
        return (True, None)
    return (d >= 60, d)

def prune_due_today(plant: dict, meta: dict) -> bool:
    """One-shot per year reminder during the plant's prune_months."""
    if "prune_months" not in plant: return False
    if date.today().month not in plant["prune_months"]: return False
    last_year = meta.get("prune_log",{}).get(plant["id"])
    return last_year != date.today().year

# ─── SCREENS ──────────────────────────────────────────────────────────────────

def screen_today(state, wx) -> tuple:
    meta = get_meta(state)
    today = date.today().isoformat()
    now = datetime.now(TUCSON_TZ)
    season = get_season()

    wx_line = (f"{wx['icon']} <b>{wx['temp_c']:.0f}°C</b> · {wx['humidity']}% hum"
               if wx.get("ok") else "🌡️ Sin datos de clima")

    lines = [
        f"🌵 <b>Tucson Garden</b>",
        f"{wx_line}  ·  {SEASON_LABEL[season]}  ·  {now.strftime('%d %b')}",
        "━"*22,
    ]
    rows = []
    has_items = False

    # ── Fertilización pendiente ────────────────────────────────────────────
    fert_due_plants = [p for p in PLANTS if fert_due(p, meta)[0]]
    if fert_due_plants:
        has_items = True
        names = ", ".join(p["name"] for p in fert_due_plants[:4])
        more = f" +{len(fert_due_plants)-4} más" if len(fert_due_plants) > 4 else ""
        lines.append(f"\n🌿 <b>Fertilización pendiente ({len(fert_due_plants)}):</b> {names}{more}")
        rows.append([{"text": f"🌿 Fertilizar ({len(fert_due_plants)})", "callback_data": "nav_plants"}])

    # ── Riego de macetas ──────────────────────────────────────────────────
    pot_due_plants = [p for p in POT_PLANTS if pot_water_due(p, meta, today)[0]]
    if pot_due_plants:
        has_items = True
        names = ", ".join(p["name"] for p in pot_due_plants)
        lines.append(f"\n🪴 <b>Macetas por revisar ({len(pot_due_plants)}):</b> {names}")
        rows.append([{"text": f"🪴 Revisar macetas ({len(pot_due_plants)})", "callback_data": "nav_pots"}])

    # ── Filtro ───────────────────────────────────────────────────────────
    f_due, f_d = filter_due(meta)
    if f_due:
        has_items = True
        label = "nunca registrada" if f_d is None else f"hace {f_d}d"
        lines.append(f"\n🧹 <b>Limpieza de filtro</b> — {label} (cada 60d)")
        rows.append([{"text": "✅ Limpié el filtro", "callback_data": "filter_done"}])

    # ── Poda estacional ──────────────────────────────────────────────────
    prune_plants = [p for p in PLANTS if prune_due_today(p, meta)]
    if prune_plants:
        has_items = True
        lines.append("\n✂️ <b>Poda de temporada:</b>")
        for plant in prune_plants:
            lines.append(f"  • {plant['name']} — {plant['prune_tip']}")
            rows.append([{"text": f"✅ Podé {plant['name']}", "callback_data": f"prune:{plant['id']}"}])

    # ── Plagas de temporada ─────────────────────────────────────────────
    pest_plants = [p for p in PLANTS if date.today().month in p.get("pest_season",[])]
    if pest_plants:
        names = ", ".join(p["name"] for p in pest_plants)
        lines.append(f"\n🐛 <b>Revisión de plagas (temporada):</b> {names}")

    # ── Riego físico — resumen rápido ────────────────────────────────────
    if tuya_control.TUYA_ENABLED:
        status = tuya_control.get_status()
        if status.get("ok"):
            bat = status.get("battery")
            z1 = "🟢" if status["switch_1"] else "⚪"
            z2 = "🟢" if status["switch_2"] else "⚪"
            bat_warn = " ⚠️" if (bat is not None and bat < 20) else ""
            last_run = meta.get("zone1_last_run_date")
            d = days_since(last_run)
            if last_run == today:
                z1_status = "regó hoy ✅"
            elif d is not None and d >= 2:
                z1_status = f"⚠️ sin riego hace {d}d"
            elif d is not None:
                z1_status = f"hace {d}d"
            else:
                z1_status = "sin historial"
            lines.append(f"\n🚰 <b>Insoma</b> {z1} Z1 ({z1_status}) · {z2} Z2 · 🔋{bat}%{bat_warn}")
        rows.append([{"text": "🚰 Riego Físico", "callback_data": "nav_tuya"}])

    # ── Modo viaje ────────────────────────────────────────────────────────
    travel_until = meta.get("travel_until")
    if travel_until and travel_until >= today:
        lines.append(f"\n✈️ <b>Modo viaje</b> {travel_label(travel_until)}")

    if not has_items:
        lines.append("\n✅ <b>Todo al día.</b> Nada que hacer hoy.")

    return "\n".join(lines), navbar_with(rows, "today")


def screen_plants(state) -> tuple:
    """Vista de fertilización por planta (tierra y macetas)."""
    meta = get_meta(state)
    lines = ["🌱 <b>Plantas — Fertilización</b>", "━"*22, ""]
    rows = []
    for plant in PLANTS:
        due, d = fert_due(plant, meta)
        interval_days = get_fert_interval_days(plant, meta)
        months = round(interval_days/30)
        if d is None:
            status = f"🆕 nunca registrada (default cada {months}mo)"
        elif due:
            status = f"🌿 pendiente (hace {d}d, cada {months}mo)"
        else:
            status = f"✅ ok (hace {d}d / cada {months}mo)"
        loc = "🪣" if plant["pot"] else "🌍"
        lines.append(f"{loc} <b>{plant['name']}</b> — {status}")
        rows.append([
            {"text": f"💊 {plant['name']}", "callback_data": f"fert:{plant['id']}:plants"},
            {"text": "ℹ️ Info", "callback_data": f"info:{plant['id']}:plants"},
        ])
    return "\n".join(lines), navbar_with(rows, "plants")


def screen_pots(state) -> tuple:
    """Vista de riego manual de macetas."""
    meta = get_meta(state)
    today = date.today().isoformat()
    lines = ["🪴 <b>Macetas — Riego manual</b>", "━"*22, ""]
    rows = []
    for plant in POT_PLANTS:
        entry = get_pot_entry(plant, meta)
        interval = get_pot_interval_days(plant, meta)
        skip_until = meta.get("pot_skip_until",{}).get(plant["id"],"")
        d = days_since(entry["date"]) if entry else None
        if skip_until >= today:
            status = f"🖐 húmedo, revisión {skip_until} (cada {interval}d)"
        elif d is None:
            status = f"🆕 nunca registrada (default cada {interval}d)"
        elif d >= interval:
            status = f"💧 toca — hace {d}d (cada {interval}d)"
        else:
            status = f"✅ ok — hace {d}d (cada {interval}d)"
        lines.append(f"<b>{plant['name']}</b> — {status}")
        rows.append([
            {"text": f"✅ Regué {plant['name']}", "callback_data": f"potw:{plant['id']}:pots"},
            {"text": "🖐 Húmedo", "callback_data": f"potmoist:{plant['id']}"},
        ])
    travel_until = meta.get("travel_until")
    on_travel = bool(travel_until and travel_until >= today)
    lines.append("")
    if on_travel:
        lines.append(f"✈️ <b>Modo viaje</b> {travel_label(travel_until)} — Zona 2 (Insoma) riega las macetas")
    else:
        lines.append("<i>✈️ En viaje, el Insoma riega las macetas automático (Zona 2)</i>")
    return "\n".join(lines), navbar_with(rows, "pots")


def screen_plant_info(plant: dict, back: str) -> tuple:
    """Ficha de cuidado: luz, qué le gusta/no, cómo se ve sana vs enferma."""
    care = CARE_INFO.get(plant["id"], {})
    loc = "🪣 Maceta (porche)" if plant["pot"] else "🌍 Tierra (riego automático)"
    lines = [
        f"ℹ️ <b>{plant['name']}</b>", "━"*22,
        f"<i>{loc}</i>", "",
        f"☀️ <b>Luz:</b> {care.get('light','—')}", "",
        f"👍 <b>Le gusta:</b> {care.get('likes','—')}", "",
        f"👎 <b>No le gusta:</b> {care.get('dislikes','—')}", "",
        f"✅ <b>Se ve sana cuando:</b> {care.get('healthy','—')}", "",
        f"⚠️ <b>Señales de problema:</b> {care.get('sick','—')}",
    ]
    rows = [[{"text": "⬅️ Volver", "callback_data": f"nav_{back}"}]]
    return "\n".join(lines), {"inline_keyboard": rows}


def screen_fert_picker(plant: dict, back: str) -> tuple:
    """Selector de intervalo de fertilización — depende de la marca del producto."""
    lines = [
        f"💊 <b>Fertilizar {plant['name']}</b>", "━"*22, "",
        "¿Cada cuántos días recomienda la <b>etiqueta del fertilizante</b>?",
        "<i>Si no estás seguro, elige el más cercano — puedes cambiarlo la próxima vez.</i>",
    ]
    options = [(30,"1 mes"),(45,"6 sem"),(60,"2 meses"),
               (90,"3 meses"),(120,"4 meses"),(180,"6 meses"),(365,"12 meses")]
    rows = []; row = []
    for days, label in options:
        row.append({"text": label, "callback_data": f"fertset:{plant['id']}:{back}:{days}"})
        if len(row) == 3:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([{"text": "❌ Cancelar", "callback_data": f"nav_{back}"}])
    return "\n".join(lines), {"inline_keyboard": rows}


def screen_pot_picker(plant: dict, back: str) -> tuple:
    """Selector de intervalo de riego para macetas — depende del tamaño/ubicación."""
    lines = [
        f"🪴 <b>Riego de {plant['name']}</b>", "━"*22, "",
        "¿Cada cuántos días le toca regar a esta maceta?",
        "<i>Macetas chicas o sol directo se secan más rápido.</i>",
    ]
    options = [(2,"2 días"),(3,"3 días"),(4,"4 días"),(5,"5 días"),(6,"6 días"),(7,"7 días")]
    rows = []; row = []
    for days, label in options:
        row.append({"text": label, "callback_data": f"potwset:{plant['id']}:{back}:{days}"})
        if len(row) == 3:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([{"text": "❌ Cancelar", "callback_data": f"nav_{back}"}])
    return "\n".join(lines), {"inline_keyboard": rows}


def screen_tuya(state) -> tuple:
    status = tuya_control.get_status()
    meta = get_meta(state)
    today = date.today().isoformat()
    travel_until = meta.get("travel_until")
    on_travel = bool(travel_until and travel_until >= today)

    lines = ["🚰 <b>Riego Físico — Insoma</b>", "━"*22, ""]

    if not status.get("ok"):
        lines += [f"⚠️ No se pudo conectar: {status.get('error','?')}",
                  "", "<i>Verifica las variables TUYA_* en Railway.</i>"]
        return "\n".join(lines), navbar(active="tuya")

    bat = status.get("battery")
    bat_line = f"🔋 Batería: <b>{bat}%</b>" if bat is not None else "🔋 Batería: --"
    if bat is not None and bat < 20:
        bat_line += "  ⚠️ <b>Cambia pilas pronto</b>"
    lines.append(bat_line)
    lines.append("")

    interval_days, base_min = get_zone1_plan()
    season = get_season()
    lines.append(f"🤖 <b>Plan automático Zona 1:</b> {SEASON_LABEL[season]} · "
                 f"cada {interval_days}d · ~{base_min}min base · 5:00 AM")
    lines.append("<i>Duración real ajustada por ETo (AZMET Tucson) cada mañana.</i>")
    lines.append("")

    z1_on = status["switch_1"]; z1_cd = status["countdown_1"]
    lines.append(f"🌍 <b>Zona 1 — Tierra</b>")
    lines.append(f"   Estado: {'🟢 Abierta' if z1_on else '⚪ Cerrada'}"
                 + (f"  ·  ⏳ {z1_cd} min" if z1_on else ""))
    lines.append("")

    z2_on = status["switch_2"]; z2_cd = status["countdown_2"]
    lines.append(f"🪴 <b>Zona 2 — Macetas (porche)</b>")
    lines.append(f"   Estado: {'🟢 Abierta' if z2_on else '⚪ Cerrada'}"
                 + (f"  ·  ⏳ {z2_cd} min" if z2_on else ""))
    if on_travel:
        z2_interval, z2_base = get_zone2_plan()
        lines.append(f"   ✈️ Modo viaje {travel_label(travel_until)}")
        lines.append(f"   🤖 Plan: cada {z2_interval}d · ~{z2_base}min base · 5:05 AM")
        z2_last = meta.get("zone2_last_run_date")
        z2_d = days_since(z2_last)
        if z2_last == today:
            lines.append("   ✅ Regó hoy")
        elif z2_d is not None:
            lines.append(f"   <i>Último riego: hace {z2_d}d</i>")
    lines.append("")
    lines.append("<i>Zona 2 normalmente cerrada — solo se usa en viajes, regando "
                 "sola según temporada hasta que toques 'Terminar viaje'.</i>")

    rows = []
    if z1_on:
        rows.append([{"text": "⏹ Cerrar Zona 1 (tierra)", "callback_data": "tuya_off_1"}])
    else:
        rows.append([
            {"text": "▶️ Abrir 20min", "callback_data": "tuya_on_1_20"},
            {"text": "▶️ Abrir 30min", "callback_data": "tuya_on_1_30"},
        ])
    if z2_on:
        rows.append([{"text": "⏹ Cerrar Zona 2 (macetas)", "callback_data": "tuya_off_2"}])
    else:
        rows.append([
            {"text": "▶️ Abrir 8min", "callback_data": "tuya_on_2_8"},
            {"text": "▶️ Abrir 12min", "callback_data": "tuya_on_2_12"},
        ])
    if on_travel:
        rows.append([{"text": "🏠 Terminar viaje (cierra Zona 2)", "callback_data": "travel_end"}])
    else:
        rows.append([{"text": "✈️ Activar Viaje", "callback_data": "travel_start"}])
    rows.append([{"text": "🔄 Actualizar", "callback_data": "nav_tuya"}])
    return "\n".join(lines), navbar_with(rows, "tuya")

# ─── MORNING IRRIGATION (5 AM) ─────────────────────────────────────────────────

async def morning_irrigation():
    """
    5:00 AM Tucson — el bot decide si Zona 1 (tierra) debe regar hoy y por
    cuántos minutos, según temporada, días desde el último riego exitoso,
    y lluvia reciente.
    """
    if not tuya_control.TUYA_ENABLED:
        return
    state = load_state(); meta = get_meta(state)
    today = date.today().isoformat()

    if meta.get("zone1_last_scheduled_date") == today:
        return  # ya se programó hoy (evita doble disparo)

    interval_days, base_min = get_zone1_plan()
    last_run = meta.get("zone1_last_run_date")
    d = days_since(last_run)

    if d is not None and d < interval_days:
        return  # aún no toca — sin spam, no se marca scheduled

    wx = await get_weather()
    if wx.get("ok") and wx.get("rain_mm",0) > 0:
        log_rain(state, wx["rain_mm"])

    azmet = await get_azmet_daily()
    forecast_max = await get_forecast_max_temp(hours=48)
    dry_days = days_since_last_rain(meta)

    # ── Skip por lluvia: AZMET (medición real de ayer) tiene prioridad sobre OWM ──
    if azmet.get("ok"):
        rain_recent = azmet["precip_mm"]
        rain_source = f"AZMET {azmet.get('date','ayer')}"
    else:
        rain_recent = recent_rain_mm(meta, days=2)
        rain_source = "OWM 48h"

    if rain_recent >= 5:
        meta["zone1_last_scheduled_date"] = today
        save_state(state)
        await send(f"🌧️ <b>Riego de hoy saltado</b> — llovió {rain_recent:.1f}mm "
                    f"({rain_source}), la tierra está húmeda.")
        return

    # ── Duración: ETo real (AZMET) vs normal del mes -> ratio proporcional ──
    reasons = []
    if azmet.get("ok") and azmet["eto_mm"] > 0:
        normal = ETO_NORMAL_MM[date.today().month]
        ratio = max(0.5, min(azmet["eto_mm"] / normal, 1.8))
        duration = base_min * ratio
        pct = round((ratio - 1) * 100)
        if abs(pct) >= 8:
            reasons.append(f"ETo {azmet['eto_mm']:.1f}mm/d ({'+' if pct>=0 else ''}{pct}% vs normal)")
    else:
        # Fallback: AZMET caído -> heurística por temperatura/humedad de OWM
        temp = wx.get("temp_c"); humidity = wx.get("humidity")
        adj, fb_reasons = compute_zone1_adjustment(temp, humidity, forecast_max, dry_days)
        duration = base_min + adj
        reasons.append("⚠️ AZMET no disponible, estimado por clima")
        reasons += fb_reasons

    # Bono proactivo: ola de calor en pronóstico 48h (AZMET es de ayer, no predice)
    if forecast_max is not None and forecast_max >= 42:
        duration += 4
        reasons.append(f"+4min ola de calor en 48h ({forecast_max:.0f}°C)")

    # Bono por sequía prolongada — déficit profundo de suelo no capturado por 1 día de ETo
    if dry_days is not None and dry_days >= 14:
        duration += 3
        reasons.append(f"+3min sin lluvia {dry_days}d+")

    duration = max(8, min(40, round(duration)))

    result = tuya_control.set_zone(1, True, minutes=duration)
    if not result.get("ok"):
        await asyncio.sleep(3)
        result = tuya_control.set_zone(1, True, minutes=duration)  # 1 reintento

    meta["zone1_last_scheduled_date"] = today

    season = get_season()
    temp = wx.get("temp_c")
    temp_label = f" · {temp:.0f}°C" if temp is not None else ""
    adjust_label = f" · {', '.join(reasons)}" if reasons else ""

    if not result.get("ok"):
        # La API ni siquiera aceptó el comando -> diagnóstico
        diag = await diagnose_failure()
        save_state(state)
        await send(f"⚠️ <b>Riego automático falló</b> — comando rechazado.\n\n{diag}")
        return

    # Verificar que de verdad abrió (espera breve y re-checa estado)
    await asyncio.sleep(5)
    verify = tuya_control.get_status()
    if verify.get("ok") and verify.get("switch_1") is True:
        save_state(state)
        await send(
            f"🚰 <b>Riego automático Zona 1</b> — {duration} min\n"
            f"{SEASON_LABEL[season]} · cada {interval_days}d{temp_label}{adjust_label}")
    else:
        # Comando "ok" pero la zona no abrió -> diagnóstico
        diag = await diagnose_failure()
        save_state(state)
        await send(
            f"⚠️ <b>Riego automático Zona 1 — comando enviado pero NO abrió.</b>\n\n{diag}")


async def travel_irrigation():
    """
    5:05 AM Tucson — si hay un viaje activo (travel_until), riega Zona 2
    (macetas) según el plan de temporada + ETo de AZMET, igual que Zona 1.
    No se salta por lluvia (las macetas están en el porche techado, la
    lluvia no las moja). Se detiene solo cuando el usuario toca "Terminar viaje".
    """
    if not tuya_control.TUYA_ENABLED:
        return
    state = load_state(); meta = get_meta(state)
    today = date.today().isoformat()

    travel_until = meta.get("travel_until")
    if not travel_until or travel_until < today:
        return  # no hay viaje activo

    if meta.get("zone2_last_scheduled_date") == today:
        return  # ya se programó hoy

    interval_days, base_min = get_zone2_plan()
    last_run = meta.get("zone2_last_run_date")
    d = days_since(last_run)

    if d is not None and d < interval_days:
        return  # aún no toca

    azmet = await get_azmet_daily()
    reasons = []
    if azmet.get("ok") and azmet["eto_mm"] > 0:
        normal = ETO_NORMAL_MM[date.today().month]
        ratio = max(0.5, min(azmet["eto_mm"] / normal, 1.8))
        duration = base_min * ratio
        pct = round((ratio - 1) * 100)
        if abs(pct) >= 8:
            reasons.append(f"ETo {azmet['eto_mm']:.1f}mm/d ({'+' if pct>=0 else ''}{pct}%)")
    else:
        duration = base_min
        reasons.append("⚠️ AZMET no disponible, usando base de temporada")

    duration = max(5, min(20, round(duration)))

    result = tuya_control.set_zone(2, True, minutes=duration)
    if not result.get("ok"):
        await asyncio.sleep(3)
        result = tuya_control.set_zone(2, True, minutes=duration)

    meta["zone2_last_scheduled_date"] = today

    season = get_season()
    reason_label = f" · {', '.join(reasons)}" if reasons else ""

    if not result.get("ok"):
        diag = await diagnose_failure()
        save_state(state)
        await send(f"⚠️ <b>Riego de viaje Zona 2 falló</b> — comando rechazado.\n\n{diag}")
        return

    await asyncio.sleep(5)
    verify = tuya_control.get_status()
    if verify.get("ok") and verify.get("switch_2") is True:
        meta["zone2_last_run_date"] = today
        save_state(state)
        await send(
            f"🚰✈️ <b>Riego de viaje — Zona 2 (macetas)</b> — {duration} min\n"
            f"{SEASON_LABEL[season]} · cada {interval_days}d{reason_label}\n"
            f"<i>Viaje {travel_label(travel_until)}</i>")
    else:
        diag = await diagnose_failure()
        save_state(state)
        await send(
            f"⚠️ <b>Riego de viaje Zona 2 — comando enviado pero NO abrió.</b>\n\n{diag}")


async def diagnose_failure() -> str:
    """Da una razón probable cuando un comando Tuya no se ejecuta como se esperaba."""
    bat = tuya_control.get_battery()
    online = tuya_control.get_device_online()

    if online is False:
        return ("📡 <b>Insoma sin conexión a internet/Tuya.</b>\n"
                "Revisa el WiFi del dispositivo — si está fuera de rango o "
                "el router cambió de red, no recibe comandos.")
    if bat is not None and bat <= 5:
        return (f"🔋 <b>Batería casi agotada ({bat}%).</b>\n"
                "Con batería muy baja el motor no tiene fuerza para abrir "
                "la válvula aunque WiFi funcione. Cambia pilas.")
    if online is None and bat is None:
        return ("❓ No se pudo obtener batería ni estado de conexión — "
                "la API de Tuya no respondió. Puede ser temporal, revisa "
                "en unos minutos desde 🚰 Riego Físico.")
    return (f"❓ Razón no clara. Batería: {bat if bat is not None else '--'}% · "
            f"Conexión: {'🟢 online' if online else '🔴 offline' if online is False else '--'}.\n"
            "Revisa manualmente desde 🚰 Riego Físico o la app Smart Life.")

# ─── WEEKLY SUMMARY (domingo) ──────────────────────────────────────────────────

async def weekly_summary():
    """Resumen de los últimos 7 días: riego, fertilización, macetas, batería."""
    state = load_state(); meta = get_meta(state)
    cutoff = (date.today()-timedelta(days=7)).isoformat()

    lines = ["📊 <b>Resumen semanal del jardín</b>", "━"*22]

    if tuya_control.TUYA_ENABLED:
        runs = [r for r in meta.get("zone1_runs",[]) if r["date"] >= cutoff]
        total_min = sum(r.get("minutes") or 0 for r in runs)
        lines.append(f"🚰 Zona 1 regó {len(runs)} veces · ~{total_min:.0f} min total")

        status = tuya_control.get_status()
        bat = status.get("battery") if status.get("ok") else None
        bat_prev = meta.get("battery_last_week")
        if bat is not None:
            if bat_prev is not None:
                delta = bat - bat_prev
                lines.append(f"🔋 Batería: {bat}% ({'+' if delta>=0 else ''}{delta}% vs semana pasada)")
            else:
                lines.append(f"🔋 Batería: {bat}%")
            meta["battery_last_week"] = bat

    pot_count = sum(1 for p in POT_PLANTS
                     if (e:=get_pot_entry(p,meta)) and e["date"] >= cutoff)
    lines.append(f"🪴 Macetas regadas: {pot_count}/{len(POT_PLANTS)} esta semana")

    fert_count = sum(1 for p in PLANTS
                      if (e:=get_fert_entry(p,meta)) and e["date"] >= cutoff)
    if fert_count:
        lines.append(f"🌿 Fertilizaciones registradas: {fert_count}")

    rain_7d = sum(r["mm"] for r in meta.get("rain_log",[]) if r["date"] >= cutoff)
    if rain_7d > 0:
        lines.append(f"🌧️ Lluvia acumulada: {rain_7d:.1f}mm")

    save_state(state)
    await send("\n".join(lines), navbar(active="today"))

# ─── EVENING CHECK (8 PM) ──────────────────────────────────────────────────────

async def evening_check():
    """
    Revisa cada noche:
      - Fertilización pendiente
      - Riego de macetas pendiente
      - Limpieza de filtro pendiente
      - Poda de temporada
      - Batería del Insoma <20%
      - Lluvia + Zona 1 corriendo -> sugiere pausar
    """
    state = load_state(); meta = get_meta(state)
    today = date.today().isoformat()
    wx = await get_weather()
    if wx.get("ok") and wx.get("rain_mm",0) > 0:
        log_rain(state, wx["rain_mm"])

    notify_lines = []
    rows = []

    # Fertilización
    fert_due_plants = [p for p in PLANTS if fert_due(p, meta)[0]]
    if fert_due_plants:
        names = ", ".join(p["name"] for p in fert_due_plants[:4])
        more = f" +{len(fert_due_plants)-4} más" if len(fert_due_plants) > 4 else ""
        notify_lines.append(f"🌿 Fertilización pendiente ({len(fert_due_plants)}): {names}{more}")
        rows.append([{"text": f"🌿 Fertilizar ({len(fert_due_plants)})", "callback_data": "nav_plants"}])

    # Macetas
    pot_due_plants = [p for p in POT_PLANTS if pot_water_due(p, meta, today)[0]]
    if pot_due_plants:
        names = ", ".join(p["name"] for p in pot_due_plants)
        notify_lines.append(f"🪴 Macetas por revisar ({len(pot_due_plants)}): {names}")
        rows.append([{"text": f"🪴 Revisar macetas ({len(pot_due_plants)})", "callback_data": "nav_pots"}])

    # Filtro
    f_due, f_d = filter_due(meta)
    if f_due:
        label = "nunca registrada" if f_d is None else f"hace {f_d}d"
        notify_lines.append(f"🧹 Limpieza de filtro pendiente ({label}, cada 60d)")
        rows.append([{"text": "✅ Limpié el filtro", "callback_data": "filter_done"}])

    # Poda
    for plant in PLANTS:
        if prune_due_today(plant, meta):
            notify_lines.append(f"✂️ {plant['name']} — {plant['prune_tip']}")
            rows.append([{"text": f"✅ Podé {plant['name']}", "callback_data": f"prune:{plant['id']}"}])

    # Batería Insoma
    if tuya_control.TUYA_ENABLED:
        status = tuya_control.get_status()
        if status.get("ok"):
            bat = status.get("battery")
            if bat is not None and bat < 20 and not meta.get("low_battery_alerted"):
                notify_lines.append(f"🔋 <b>Batería Insoma al {bat}%</b> — cambia pilas pronto")
                meta["low_battery_alerted"] = True
            elif bat is not None and bat >= 30:
                meta["low_battery_alerted"] = False

            # Lluvia + Zona 1 corriendo -> sugerir pausar
            if wx.get("ok") and wx.get("rain_mm",0) >= 3 and status.get("switch_1"):
                notify_lines.append(
                    f"🌧️ Llovió {wx['rain_mm']:.1f}mm y Zona 1 (tierra) está corriendo ahora mismo.")
                rows.append([{"text": "⏹ Pausar Zona 1 (llovió)", "callback_data": "tuya_off_1"}])

    save_state(state)

    if not notify_lines:
        logging.info("8PM: nada pendiente.")
        return

    season = get_season()
    wx_line = (f"{wx['icon']} {wx['temp_c']:.0f}°C" if wx.get("ok") else "")
    header = f"🌙 <b>Resumen del jardín</b> {wx_line}  ·  {SEASON_LABEL[season]}\n{'━'*22}\n"
    msg = header + "\n".join(notify_lines)
    rows.append([{"text": "🌿 Ver Hoy", "callback_data": "nav_today"}])
    await send(msg, {"inline_keyboard": rows})
    logging.info(f"8PM: {len(notify_lines)} items.")

# ─── TUYA MONITOR (cada 15 min) ────────────────────────────────────────────────

async def tuya_monitor():
    """
    Detecta cuando Zona 1 (tierra) termina un ciclo de riego (transición ON->OFF)
    y lo registra. Si el ciclo duró menos de 2 min, es sospechoso (corte de luz/WiFi
    a media regada) y avisa en vez de marcarlo como riego exitoso.
    Si pasan >=2 días sin riego exitoso, avisa una sola vez (posible falla:
    batería, WiFi, o el horario en Smart Life se desconfiguró).
    """
    if not tuya_control.TUYA_ENABLED:
        return
    state = load_state(); meta = get_meta(state)
    status = tuya_control.get_status()
    if not status.get("ok"):
        return

    today = date.today().isoformat()
    now = datetime.now(TUCSON_TZ)
    z1_on = status["switch_1"]
    was_on = meta.get("zone1_was_on", False)

    if z1_on and not was_on:
        # Empieza un ciclo de riego
        meta["zone1_started_at"] = now.isoformat()

    elif was_on and not z1_on:
        # Termina un ciclo de riego — calcular duración
        started_iso = meta.get("zone1_started_at")
        elapsed_min = None
        if started_iso:
            try:
                started = datetime.fromisoformat(started_iso)
                elapsed_min = (now - started).total_seconds() / 60
            except Exception:
                elapsed_min = None

        if elapsed_min is not None and elapsed_min < 2:
            # Ciclo sospechosamente corto -> no contar como riego exitoso
            await send(
                f"⚠️ <b>Zona 1 corrió solo {elapsed_min:.1f} min</b> "
                f"(se esperaba más).\n\n"
                f"Posible corte de luz, WiFi, o cierre manual. Revisa el Insoma.",
                navbar(active="tuya")
            )
            logging.warning(f"Zona 1: ciclo corto detectado ({elapsed_min:.1f} min) — no registrado como éxito.")
        else:
            # Riego completo
            meta["zone1_last_run_date"] = today
            runs = meta.setdefault("zone1_runs", [])
            mins_label = f"{elapsed_min:.0f}" if elapsed_min is not None else "?"
            runs.append({"date": today, "time": now.strftime("%H:%M"),
                          "minutes": round(elapsed_min,1) if elapsed_min is not None else None})
            if len(runs) > 30:
                meta["zone1_runs"] = runs[-30:]
            meta["no_run_alerted"] = False
            # Si el bot ya confirmó este riego esta mañana (morning_irrigation),
            # no repetir el mensaje — solo avisar si fue un riego NO programado por el bot
            # (ej. corriste manual o Smart Life todavía tiene horario propio).
            if meta.get("zone1_last_scheduled_date") != today:
                await send(f"✅ <b>Zona 1 (tierra) regó {mins_label} min</b> — todo bien "
                            f"(no fue el bot — ¿Smart Life tiene horario propio?).")
            logging.info(f"Zona 1: ciclo de riego completo ({elapsed_min}min) — registrado.")

        meta["zone1_started_at"] = None

    meta["zone1_was_on"] = z1_on

    # Alerta si lleva más del intervalo de temporada +2 días sin riego exitoso
    last_run = meta.get("zone1_last_run_date")
    d = days_since(last_run)
    interval_days, _ = get_zone1_plan()
    threshold = interval_days + 2
    if d is not None and d >= threshold and not meta.get("no_run_alerted") and not z1_on:
        diag = await diagnose_failure()
        await send(
            f"⚠️ <b>Zona 1 (tierra) sin riego exitoso en {d} días</b> "
            f"(esperado cada {interval_days}d).\n\n{diag}",
            navbar(active="tuya")
        )
        meta["no_run_alerted"] = True

    save_state(state)

# ─── CALLBACK HANDLER ─────────────────────────────────────────────────────────

async def handle_cb(update: dict):
    cb = update["callback_query"]
    data = cb["data"]; cbid = cb["id"]
    chat = str(cb["message"]["chat"]["id"]); mid = cb["message"]["message_id"]

    state = load_state(); meta = get_meta(state)
    today = date.today().isoformat()
    wx = await get_weather()

    async def ack(text:str="✓", alert:bool=False):
        await answer(cbid, text, alert)

    async def refresh_today():
        txt, kb = screen_today(state, wx)
        await edit(chat, mid, txt, kb)

    # ── Navbar ────────────────────────────────────────────────────────────
    if data == "nav_today":
        await ack("🌿 Hoy")
        await refresh_today()

    elif data == "nav_plants":
        await ack("🌱 Plantas")
        txt, kb = screen_plants(state)
        await edit(chat, mid, txt, kb)

    elif data == "nav_pots":
        await ack("🪴 Macetas")
        txt, kb = screen_pots(state)
        await edit(chat, mid, txt, kb)

    elif data == "nav_tuya":
        await ack("🚰 Riego físico")
        txt, kb = screen_tuya(state)
        await edit(chat, mid, txt, kb)

    # ── Info de cuidado ──────────────────────────────────────────────────
    elif data.startswith("info:"):
        rest = data[5:].split(":")
        pid = rest[0]; back = rest[1] if len(rest) > 1 else "plants"
        plant = PLANT_MAP.get(pid)
        if plant:
            await ack("ℹ️ Cuidados")
            txt, kb = screen_plant_info(plant, back)
            await edit(chat, mid, txt, kb)
        else:
            await ack()

    # ── Fertilizar ────────────────────────────────────────────────────────
    elif data.startswith("fert:"):
        rest = data[5:].split(":")
        pid = rest[0]; back = rest[1] if len(rest) > 1 else "today"
        plant = PLANT_MAP.get(pid)
        if plant:
            await ack("Elige el intervalo")
            txt, kb = screen_fert_picker(plant, back)
            await edit(chat, mid, txt, kb)
        else:
            await ack()

    elif data.startswith("fertset:"):
        _, pid, back, days_str = data.split(":")
        days = int(days_str)
        plant = PLANT_MAP.get(pid)
        if plant:
            meta.setdefault("fertilize_log",{})[pid] = {"date": today, "interval_days": days}
            save_state(state)
            voice = random.choice(VOICES.get(pid,{}).get("fert",["¡Gracias!"]))
            months = days/30
            await ack(f"💊 {plant['name']} — cada {days}d (~{months:.0f}mo) — \"{voice}\"", alert=True)
        if back == "plants":
            txt, kb = screen_plants(state)
        elif back == "pots":
            txt, kb = screen_pots(state)
        else:
            txt, kb = screen_today(state, wx)
        await edit(chat, mid, txt, kb)

    # ── Riego de maceta (manual) ────────────────────────────────────────────
    elif data.startswith("potw:"):
        rest = data[5:].split(":")
        pid = rest[0]; back = rest[1] if len(rest) > 1 else "today"
        plant = PLANT_MAP.get(pid)
        if plant:
            await ack("Elige cada cuántos días")
            txt, kb = screen_pot_picker(plant, back)
            await edit(chat, mid, txt, kb)
        else:
            await ack()

    elif data.startswith("potwset:"):
        _, pid, back, days_str = data.split(":")
        days = int(days_str)
        plant = PLANT_MAP.get(pid)
        if plant:
            meta.setdefault("pot_watered_log",{})[pid] = {"date": today, "interval_days": days}
            meta.setdefault("pot_skip_until",{}).pop(pid, None)
            save_state(state)
            voice = random.choice(VOICES.get(pid,{}).get("happy",["¡Gracias!"]))
            await ack(f"✅ {plant['name']} regada — cada {days}d — \"{voice}\"", alert=True)
        if back == "plants":
            txt, kb = screen_plants(state)
        elif back == "pots":
            txt, kb = screen_pots(state)
        else:
            txt, kb = screen_today(state, wx)
        await edit(chat, mid, txt, kb)

    elif data.startswith("potmoist:"):
        pid = data[9:]
        plant = PLANT_MAP.get(pid)
        if plant:
            until = (date.today()+timedelta(days=2)).isoformat()
            meta.setdefault("pot_skip_until",{})[pid] = until
            save_state(state)
            voice = random.choice(VOICES.get(pid,{}).get("moist",["Ok, esperamos."]))
            await ack(f"🖐 {plant['name']} — \"{voice}\" (revisión en 2d)", alert=True)
            await refresh_today()
        else:
            await ack()

    # ── Filtro ───────────────────────────────────────────────────────────
    elif data == "filter_done":
        meta["filter_clean_log"] = today
        save_state(state)
        await ack("🧹 Filtro limpio — registrado", alert=True)
        await refresh_today()

    # ── Poda ─────────────────────────────────────────────────────────────
    elif data.startswith("prune:"):
        pid = data[6:]
        plant = PLANT_MAP.get(pid)
        if plant:
            meta.setdefault("prune_log",{})[pid] = date.today().year
            save_state(state)
            await ack(f"✂️ {plant['name']} podada — registrado", alert=True)
            await refresh_today()
        else:
            await ack()

    # ── Riego físico (Insoma/Tuya) ──────────────────────────────────────────
    elif data.startswith("tuya_on_"):
        parts = data.split("_"); zone = int(parts[2]); mins = int(parts[3])
        result = tuya_control.set_zone(zone, True, minutes=mins)
        if result.get("ok"):
            zone_name = "Tierra" if zone == 1 else "Macetas"
            await ack(f"✅ Zona {zone} ({zone_name}) abierta — {mins} min", alert=True)
        else:
            await ack(f"⚠️ Error: {result.get('error','?')}", alert=True)
        txt, kb = screen_tuya(state)
        await edit(chat, mid, txt, kb)

    elif data.startswith("tuya_off_"):
        zone = int(data.split("_")[2])
        result = tuya_control.set_zone(zone, False)
        if result.get("ok"):
            await ack(f"⏹ Zona {zone} cerrada", alert=True)
        else:
            await ack(f"⚠️ Error: {result.get('error','?')}", alert=True)
        txt, kb = screen_tuya(state)
        await edit(chat, mid, txt, kb)

    # ── Modo viaje ────────────────────────────────────────────────────────
    elif data == "travel_start":
        meta["travel_until"] = "9999-12-31"  # indefinido — termina solo con "Terminar viaje"
        # Reset para que travel_irrigation riegue de inmediato hoy y luego
        # siga su propio ciclo (cada N días) hasta que termines el viaje.
        meta["zone2_last_run_date"] = None
        meta["zone2_last_scheduled_date"] = None
        save_state(state)
        _, base_min = get_zone2_plan()
        result = tuya_control.set_zone(2, True, minutes=base_min)
        if result.get("ok"):
            today = date.today().isoformat()
            meta["zone2_last_run_date"] = today
            meta["zone2_last_scheduled_date"] = today
            save_state(state)
            interval_days, _ = get_zone2_plan()
            await ack(f"✈️ Viaje activado — Zona 2 regó {base_min}min. "
                      f"El bot seguirá regando cada {interval_days}d hasta que toques "
                      f"'Terminar viaje', sin importar cuántos días dure.",
                      alert=True)
        else:
            await ack(f"✈️ Viaje activado, error Zona 2: {result.get('error','?')}", alert=True)
        txt, kb = screen_tuya(state)
        await edit(chat, mid, txt, kb)

    elif data == "travel_end":
        meta.pop("travel_until", None)
        meta["zone2_last_run_date"] = None
        meta["zone2_last_scheduled_date"] = None
        save_state(state)
        result = tuya_control.set_zone(2, False)
        if result.get("ok"):
            await ack("🏠 ¡Bienvenido! Zona 2 cerrada — vuelves a riego manual", alert=True)
        else:
            await ack(f"🏠 Viaje terminado, error: {result.get('error','?')}", alert=True)
        txt, kb = screen_tuya(state)
        await edit(chat, mid, txt, kb)

    else:
        await ack()

# ─── MESSAGE HANDLER ──────────────────────────────────────────────────────────

async def handle_msg(update: dict):
    msg = update.get("message", {}); text = msg.get("text","").strip()
    chat = str(msg.get("chat",{}).get("id",""))
    if not any(text.startswith(c) for c in ["/start","/menu","/hoy"]): return
    state = load_state(); get_meta(state); save_state(state)
    wx = await get_weather()
    txt, kb = screen_today(state, wx)
    await send(txt, kb, chat=chat)

# ─── POLL ─────────────────────────────────────────────────────────────────────

async def poll():
    offset = None; logging.info("Polling v8")
    while True:
        try:
            params = {"timeout":20, "allowed_updates":["message","callback_query"]}
            if offset: params["offset"] = offset
            async with httpx.AsyncClient(timeout=30) as cl:
                data = (await cl.get(f"{API}/getUpdates", params=params)).json()
            for upd in data.get("result", []):
                offset = upd["update_id"]+1
                try:
                    if "callback_query" in upd: await handle_cb(upd)
                    elif "message" in upd: await handle_msg(upd)
                except Exception as e: logging.error(f"Handler: {e}")
        except Exception as e:
            logging.warning(f"Poll: {e}"); await asyncio.sleep(5)

# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    global VOLUME_OK
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    VOLUME_OK = verify_volume()
    if not VOLUME_OK: logging.error("⚠️ /data no disponible.")

    sched = AsyncIOScheduler(timezone=TUCSON_TZ)
    sched.add_job(evening_check, "cron", hour=20, minute=0, id="evening")
    sched.add_job(weekly_summary, "cron", day_of_week="sun", hour=21, minute=0, id="weekly_summary")
    if tuya_control.TUYA_ENABLED:
        sched.add_job(morning_irrigation, "cron", hour=5, minute=0, id="morning_irrigation")
        sched.add_job(travel_irrigation, "cron", hour=5, minute=5, id="travel_irrigation")
        sched.add_job(tuya_monitor, "interval", minutes=15, id="tuya_monitor")
    sched.start()

    state = load_state(); get_meta(state); save_state(state)
    wx = await get_weather()
    txt, kb = screen_today(state, wx)
    await send(
        f"🌵 <b>Tucson Garden Assistant v8</b> · Volume {'✅' if VOLUME_OK else '⚠️'}\n\n" + txt, kb)
    logging.info(f"v8 arrancado — {len(PLANTS)} plantas")
    await poll()

if __name__ == "__main__":
    asyncio.run(main())
