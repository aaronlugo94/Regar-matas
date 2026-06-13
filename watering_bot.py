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
        "zone1_runs": [],          # historial: [{"date":iso, "time":"HH:MM"}, ...]
        "no_run_alerted": False,   # evita repetir alerta de "sin riego" cada 15 min
    })

# ─── SEASON / WEATHER ─────────────────────────────────────────────────────────

def get_season() -> str:
    m = date.today().month
    if m in (7,8,9):     return "monsoon"
    if m in (6,10):      return "hot"
    if m in (11,12,1,2): return "cool"
    return "spring"

SEASON_LABEL = {"monsoon":"🌧️ Monzón","hot":"🔥 Calor Extremo","cool":"❄️ Invierno","spring":"🌱 Primavera"}

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
        lines.append(f"\n✈️ <b>Modo viaje activo</b> hasta {travel_until}")

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
        lines.append(f"✈️ <b>Modo viaje activo</b> hasta {travel_until} — Zona 2 (Insoma) riega las macetas")
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
        lines.append(f"   ✈️ Modo viaje activo hasta {travel_until}")
    lines.append("")
    lines.append("<i>Zona 2 normalmente cerrada — solo se usa en viajes.</i>")

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
        rows.append([
            {"text": "✈️ Viaje 3d", "callback_data": "travel_start_3"},
            {"text": "✈️ Viaje 5d", "callback_data": "travel_start_5"},
            {"text": "✈️ Viaje 7d", "callback_data": "travel_start_7"},
        ])
    rows.append([{"text": "🔄 Actualizar", "callback_data": "nav_tuya"}])
    return "\n".join(lines), navbar_with(rows, "tuya")

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
            await send(f"✅ <b>Zona 1 (tierra) regó {mins_label} min</b> — todo bien.")
            logging.info(f"Zona 1: ciclo de riego completo ({elapsed_min}min) — registrado.")

        meta["zone1_started_at"] = None

    meta["zone1_was_on"] = z1_on

    # Alerta si lleva >=2 días sin riego exitoso
    last_run = meta.get("zone1_last_run_date")
    d = days_since(last_run)
    if d is not None and d >= 2 and not meta.get("no_run_alerted") and not z1_on:
        await send(
            f"⚠️ <b>Zona 1 (tierra) sin riego exitoso en {d} días.</b>\n\n"
            f"Revisa: horario en Smart Life, batería del Insoma, "
            f"o que la llave principal esté abierta.",
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
    elif data.startswith("travel_start_"):
        days = int(data.split("_")[2])
        until = (date.today()+timedelta(days=days)).isoformat()
        meta["travel_until"] = until
        save_state(state)
        result = tuya_control.set_zone(2, True, minutes=12)
        if result.get("ok"):
            await ack(f"✈️ Viaje activado ({days}d) — Zona 2 abierta 12min", alert=True)
        else:
            await ack(f"✈️ Viaje activado, error Zona 2: {result.get('error','?')}", alert=True)
        txt, kb = screen_tuya(state)
        await edit(chat, mid, txt, kb)

    elif data == "travel_end":
        meta.pop("travel_until", None)
        save_state(state)
        result = tuya_control.set_zone(2, False)
        if result.get("ok"):
            await ack("🏠 ¡Bienvenido! Zona 2 cerrada", alert=True)
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
    if tuya_control.TUYA_ENABLED:
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
