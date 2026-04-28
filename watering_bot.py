"""
🌵 Plant Watering Bot — Tucson AZ v6 🎮
════════════════════════════════════════
Interfaz de botones completa (inline keyboards):
  • /start  → Menú principal con botones
  • 🌿 Ver mis plantas  → Lista con estado de cada una
  • Tap en planta      → Tarjeta detallada + botones de acción
  • [✅ Ya Regué]      → Confirma el riego desde el botón
  • [⏭ Saltar hoy]    → Skip con un toque
  • [💊 Fertilicé]    → Registrar fertilización
  • 💧 Regar todo      → Marca todas de una
  • 📊 Mi progreso     → Nivel, racha, logros
  • 🌤 Clima ahora     → Condiciones actuales
  • 8 PM notificación  → Botones directos en el aviso nocturno
════════════════════════════════════════
"""

import os, json, random, logging, asyncio, httpx
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ─── CONFIG ───────────────────────────────────────────────────────────────────

TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
OWM_KEY = os.environ["OPENWEATHER_API_KEY"]

TUCSON_TZ       = ZoneInfo("America/Phoenix")
TUCSON_LAT      = 32.2226
TUCSON_LON      = -110.9747
API             = f"https://api.telegram.org/bot{TOKEN}"

TUCSON_ETO_REF  = {
    1:2.1, 2:3.0, 3:4.5, 4:6.2, 5:7.8,
    6:8.9, 7:7.2, 8:6.8, 9:5.5, 10:4.1,
    11:2.6, 12:1.9,
}

# ─── PLANT VOICES ─────────────────────────────────────────────────────────────

VOICES = {
    "cycas_1": {
        "happy":   ["Llevo millones de años en la Tierra y sigo aquí. Gracias al agua... y a ti. Tal vez.",
                    "Mis antepasados vivieron con los dinosaurios. Yo sobreviví Tucson. No es poca cosa.",
                    "Estoy en mi mejor momento. No me toques las frondas.",
                    "El agua fluyó. La vida continúa. Soy eterna."],
        "thirsty": ["...Oye. Oye tú. Las raíces ya están preguntando por el agua.",
                    "Tengo millones de años de historia y me tienes esperando. Qué falta de respeto.",
                    "Mis frondas están calculando cuánto tiempo más pueden aguantar. El resultado no te va a gustar.",
                    "Soy una cycas. Tengo paciencia infinita. Pero HOY toca el agua. Hoy."],
        "dying":   ["🚨 Estoy recurriendo a reservas del Jurásico. Agua. Ya.",
                    "Los dinosaurios me fallaron. El clima me ha fallado. Y ahora tú también. Decepcionante.",
                    "Mis raíces han enviado un memorándum formal solicitando hidratación inmediata.",
                    "He sobrevivido extinciones masivas. Pero esto... esto es NEGLIGENCIA."],
        "rained":  ["La lluvia me recuerda tiempos más gloriosos. Gracias, cielo.",
                    "El monzón llegó. Como siempre ha llegado. Soy antigua. El agua me conoce."],
        "winter":  ["El frío me invita a meditar. No necesito agua. Solo silencio y respeto.",
                    "Invierno. El tiempo de la contemplación. Deja de molestarme."],
    },
    "cycas_2": {
        "happy":   ["El agua llegó. Como el sol llegará mañana. Todo tiene su tiempo.",
                    "Hidratada. En paz. Lista para otro ciclo de millones de años.",
                    "Mis raíces están satisfechas. Eso es suficiente.",
                    "No necesito mucho. Solo lo justo. Y llegó."],
        "thirsty": ["El tiempo sin agua es solo tiempo. Pero... ya va siendo tiempo.",
                    "No es urgencia. Es simplemente... necesidad. Pronto, por favor.",
                    "El suelo habla. Dice que está seco. Yo solo traduzco el mensaje.",
                    "¿Puede una cycas sobrevivir la negligencia humana? Esperemos no averiguarlo."],
        "dying":   ["🚨 La filosofía tiene límites. Este es uno de ellos. Agua. Ahora.",
                    "He aceptado el calor, el viento, la caliche de Tucson. El olvido, no.",
                    "Las hojas internas están redistribuyendo la humedad. Elegante. Y desesperado."],
        "rained":  ["La lluvia es la respuesta que la tierra da cuando nadie pregunta.",
                    "El cielo recordó lo que tú a veces olvidas."],
        "winter":  ["El frío reduce mis necesidades. Como la meditación reduce las preocupaciones."],
    },
    "rosal": {
        "happy":   ["Finalmente. Agua. En la base como debe ser. Eres aprendible.",
                    "Mis pétalos están radiantes esta noche. ¿Lo notas?",
                    "Con este riego, mañana abro tres botones nuevos. De nada.",
                    "Ah, el agua. El único lenguaje que entiendo antes de las 9 PM."],
        "thirsty": ["¿Ya viste la hora? MIS RAÍCES LLEVAN ESPERANDO TODO EL DÍA.",
                    "Un rosal sin agua es una tragedia. Una tragedia con espinas. Muévete.",
                    "No soy un cactus. Repite conmigo: NO SOY UN CACTUS.",
                    "El mulch solo hace tanto. El resto te toca a ti."],
        "dying":   ["🚨 Mis hojas están cerrando poros. Mis botones no van a abrir. Esto ES TU CULPA.",
                    "Si yo me seco, tú te quedas sin rosas. Sin fragancia. Sin belleza. ¿Eso quieres?",
                    "🚨 EMERGENCIA FLORAL. Repito: EMERGENCIA FLORAL. Riego INMEDIATO."],
        "rained":  ["¡Llovió! Mis hojas se quedaron secas como deben. Alguien sabe respetar a las rosas."],
        "winter":  ["El invierno me da chance de descansar. Igual necesito atención. Soy un rosal, no una piedra."],
    },
    "toronja": {
        "happy":   ["Así me gusta. Agua profunda, en el drip line. Buen trabajo.",
                    "Mis raíces están contentas. Eso se traduce en fruta. Recuerda eso.",
                    "Hidratada. Las flores van a oler increíble esta semana.",
                    "El riego llegó a tiempo. Tus jugos del domingo te lo agradecen."],
        "thirsty": ["Las raíces llegaron al límite del drip line buscando humedad. Ayúdame.",
                    "Mis hojas están un poco menos brillantes. Agua, por favor.",
                    "No voy a tirar fruta todavía. Pero si esperas más... no prometo nada.",
                    "Soy paciente. Pero soy una toronja, no un nopal."],
        "dying":   ["🚨 Estoy priorizando frutas sobre ramas. Eso no es buena señal. Agua ya.",
                    "Si ves hojas amarillas mañana, ya sabes por qué.",
                    "🚨 Mis frutas están mandando agua a las ramas para sobrevivir. Aborto de fruto. No lo queremos."],
        "rained":  ["¡Llovió! El monzón hizo su trabajo. Yo hago el mío.",
                    "La lluvia llegó al drip line perfecto. La naturaleza sabe lo que hace."],
        "winter":  ["En invierno descanso. Pero no te olvides de mí completamente."],
    },
    "limon": {
        "happy":   ["¡Perfecto! Agua justa, en el sitio correcto, sin encharcamiento. ¡PERFECTO!",
                    "Mis raíces están en equilibrio óptimo de humedad.",
                    "Sin hojas amarillas. Sin raíces encharcadas. Todo según el plan.",
                    "El pH del suelo está bien. La humedad está bien. Todo está bien. Por ahora."],
        "thirsty": ["Necesito agua. No demasiada. No poca. La cantidad exacta. ¿Entiendes?",
                    "Mis hojas están monitoreando los niveles de humedad y el reporte no es favorable.",
                    "Hay una ventana de riego óptima y se está cerrando.",
                    "No es que esté seco-seco. Es que el nivel subóptimo afecta la calidad del fruto."],
        "dying":   ["🚨 Estatus: crítico. Protocolo de emergencia activado.",
                    "Mis hojas están enrollando los bordes para reducir transpiración. SERIO.",
                    "🚨 Hay una zona segura de humedad y me estás sacando de ella."],
        "rained":  ["Llovió 8mm. Calculé el aporte hídrico. Estamos en zona segura. Por ahora."],
        "winter":  ["Invierno. Menos agua. Yo monitoreo. Tú ejecutas. Seguimos el protocolo."],
    },
    "mandarina": {
        "happy":   ["Gracias. Mis mandarinas van a estar dulces este año. Te lo prometo.",
                    "El agua llegó. Mis raíces están contentas. Todo bien por aquí.",
                    "De todas las plantas del jardín, yo soy la más fácil. Solo no me olvides.",
                    "Bien regada. El drip line absorbió todo perfecto."],
        "thirsty": ["Oye, sin presión, pero ya llevan unos días las raíces medio secas...",
                    "No soy dramática como el rosal, pero sí necesito agua. Pronto.",
                    "El Tucson de julio no perdona. Yo soy fuerte, pero tengo mis límites.",
                    "Un riego profundo esta noche y mañana seguimos como si nada. ¿Trato?"],
        "dying":   ["🚨 Ya no estoy siendo tranquila. Necesito agua. Ahora mismo.",
                    "Mis mandarinas van a caer si no hay agua pronto.",
                    "🚨 Sigo siendo la más amable del jardín pero AGUA. POR. FAVOR."],
        "rained":  ["¡Gracias monzón! Este es mi momento favorito del año."],
        "winter":  ["El invierno está bien. Poco riego, mucho descanso. Me parece justo."],
    },
    "lilly_asiatica": {
        "happy":   ["¡Agua! ¡Llegó el agua! ¡Mis pétalos están felices! ¡Todo está bien!",
                    "El sustrato está perfecto. Húmedo pero no encharcado. ¡Gracias!",
                    "Mis flores van a abrir mañana. ¿Las viste? Son bonitas, ¿verdad?",
                    "Regada a tiempo. ¡Soy feliz! ¡Buenas noches!"],
        "thirsty": ["Oye... el sustrato está un poquito seco... no quiero alarmar a nadie pero...",
                    "¿Puedes meter el dedo en la tierra? ¿Seco verdad? Necesito agua.",
                    "En maceta el sol de Tucson es MUCHO. Agua pronto.",
                    "Mis hojas están un poco menos erguidas. Es una señal de sed."],
        "dying":   ["🚨 ¡Estoy doblando las hojas! ¡AGUA AHORA POR FAVOR!",
                    "El sustrato está completamente seco. Todo seco. 🆘",
                    "🚨 Mis flores van a caer si no hay agua ESTA NOCHE.",
                    "¡La maceta pesa como papel! ¡Sin agua! ¡Hazlo!"],
        "rained":  ["Llovió pero... ¿llegó a mi maceta? A veces el techo... solo digo.",
                    "¡Llovió! Aunque en maceta no siempre entra bien. ¿Puedes revisar?"],
        "winter":  ["Hace frío. Necesito menos agua pero no cero agua. No me abandones."],
    },
    "geranio": {
        "happy":   ["Agua al sustrato, lejos de las flores. Bien hecho.",
                    "Estoy bien. Sin dramas. Un poco de agua y sigo floreciendo.",
                    "Las flores están sanas. El sustrato tiene humedad. Todo correcto.",
                    "No necesito mucho. Solo constancia. Y tú eres constante. Aprecio eso."],
        "thirsty": ["El sustrato ya está seco un par de centímetros. Casi es hora.",
                    "Soy relajado pero no soy inmortal. Agua pronto, ¿sí?",
                    "Las hojas están un poco caídas. No dramáticamente. Solo... notablemente.",
                    "Llevo esperando con paciencia. La paciencia tiene su límite."],
        "dying":   ["🚨 El sustrato está seco hasta el fondo. Agua.",
                    "Las hojas están colgando. Esto ya no es estilo, es deshidratación.",
                    "🚨 Soy el más tranquilo del jardín y te pido agua con urgencia. Eso debería decirte algo."],
        "rained":  ["Llovió. Revisé el sustrato. Tiene humedad. Estamos bien."],
        "winter":  ["Con el frío casi no necesito agua. Solo no me dejes completamente olvidado."],
    },
    "vinca": {
        "happy":   ["¡Oye! ¡Fui regada! ¡Mis flores de colores están happy! ¡Viva!",
                    "Sobreviví el verano de Tucson y sigo floreciendo. Soy una leyenda.",
                    "Blanca, rosa, magenta — tengo flores de todos colores. Y ahora agua. La vida es buena.",
                    "El sustrato está perfecto. Mañana abro más flores. Cuéntalas."],
        "thirsty": ["Soy resistente al calor pero no soy roca. Agua pronto, campeón.",
                    "Mis flores siguen abiertas pero el sustrato ya se siente seco.",
                    "Tucson + maceta grande + sin agua = problema pronto. Tú lo sabes.",
                    "¿Ya metiste el dedo al sustrato? Seco, ¿verdad? Riégame."],
        "dying":   ["🚨 Mis flores están cerrando temprano. AGUA.",
                    "La maceta pesa menos que ayer. Tendencia preocupante.",
                    "🚨 Soy la más resistente del jardín y estoy pidiendo ayuda. ¿Qué más quieres saber?"],
        "rained":  ["¡Llovió y llegó a mi maceta! ¡Hoy es un buen día!",
                    "La lluvia del monzón es mi favorita. Agua del cielo. Romance puro."],
        "winter":  ["Con el frío me pongo más tranquila. Menos flores, menos agua.",
                    "Invierno en Tucson es suave. Pero igual necesito agua, aunque poca."],
    },
}

# ─── PLANTS ───────────────────────────────────────────────────────────────────

PLANTS = [
    {"id":"cycas_1",       "name":"Cycas #1 🌴",           "location":"tierra",
     "base_days":14, "heat_factor":0.60, "monsoon_bonus":5, "cool_factor":2.0,
     "pot":False, "pot_diameter_cm":None, "drought_tolerance":3,
     "fertilize_weeks":12, "pest_season":[6,7,8],
     # 2.5 L/min @ 20-25s/L. Cycas necesita ~20L profundo → 8 min
     "watering_profile":{"flow_lpm":2.5,"duration_min":8,"heat_extra_min":4,"cool_less_min":3,
                         "method":"Manguera lenta en espiral, tronco → afuera",
                         "target":"Zona raíces (~50 cm del tronco) — NO mojar frondas"}},
    {"id":"cycas_2",       "name":"Cycas #2 🌴",           "location":"tierra",
     "base_days":14, "heat_factor":0.60, "monsoon_bonus":5, "cool_factor":2.0,
     "pot":False, "pot_diameter_cm":None, "drought_tolerance":3,
     "fertilize_weeks":12, "pest_season":[6,7,8],
     "watering_profile":{"flow_lpm":2.5,"duration_min":8,"heat_extra_min":4,"cool_less_min":3,
                         "method":"Manguera lenta en espiral, tronco → afuera",
                         "target":"Zona raíces (~50 cm del tronco) — NO mojar frondas"}},
    {"id":"rosal",         "name":"Rosal 🌹",               "location":"tierra",
     "base_days":4,  "heat_factor":0.50, "monsoon_bonus":2, "cool_factor":1.6,
     "pot":False, "pot_diameter_cm":None, "drought_tolerance":1,
     "fertilize_weeks":4, "pest_season":[3,4,5],
     # Rosal ~15L → 6 min @ 2.5 L/min. Flujo suave para no erosionar base
     "watering_profile":{"flow_lpm":2.5,"duration_min":6,"heat_extra_min":3,"cool_less_min":2,
                         "method":"Manguera muy suave al ras del suelo, circular",
                         "target":"Base del tallo — NUNCA hojas ni pétalos"}},
    {"id":"toronja",       "name":"Toronja 🍊",             "location":"tierra",
     "base_days":7,  "heat_factor":0.65, "monsoon_bonus":3, "cool_factor":1.7,
     "pot":False, "pot_diameter_cm":None, "drought_tolerance":2,
     "fertilize_weeks":6, "pest_season":[3,4,10,11],
     # Cítrico adulto ~25L → 10 min @ 2.5 L/min
     "watering_profile":{"flow_lpm":2.5,"duration_min":10,"heat_extra_min":4,"cool_less_min":3,
                         "method":"Manguera flujo medio, círculo amplio",
                         "target":"Drip line (~80 cm del tronco)"}},
    {"id":"limon",         "name":"Limón 🍋",               "location":"tierra",
     "base_days":7,  "heat_factor":0.65, "monsoon_bonus":3, "cool_factor":1.7,
     "pot":False, "pot_diameter_cm":None, "drought_tolerance":2,
     "fertilize_weeks":6, "pest_season":[3,4,10,11],
     "watering_profile":{"flow_lpm":2.5,"duration_min":10,"heat_extra_min":4,"cool_less_min":3,
                         "method":"Manguera flujo medio, círculo amplio",
                         "target":"Drip line (~70 cm del tronco)"}},
    {"id":"mandarina",     "name":"Mandarina 🍊",           "location":"tierra",
     "base_days":7,  "heat_factor":0.65, "monsoon_bonus":3, "cool_factor":1.7,
     "pot":False, "pot_diameter_cm":None, "drought_tolerance":2,
     "fertilize_weeks":6, "pest_season":[3,4,10,11],
     "watering_profile":{"flow_lpm":2.5,"duration_min":10,"heat_extra_min":4,"cool_less_min":3,
                         "method":"Manguera flujo medio, círculo amplio",
                         "target":"Drip line (~75 cm del tronco)"}},
    {"id":"lilly_asiatica","name":"Lilly Asiática 🌸",      "location":"maceta",
     "base_days":3,  "heat_factor":0.40, "monsoon_bonus":1, "cool_factor":1.5,
     "pot":True, "pot_diameter_cm":25, "drought_tolerance":1,
     "fertilize_weeks":3, "pest_season":[4,5,9,10],
     # Maceta 25cm ~2L → goteo suave ~0.8 L/min, 2.5 min
     "watering_profile":{"flow_lpm":0.8,"duration_min":3,"heat_extra_min":1,"cool_less_min":1,
                         "method":"Regadera o goteo muy suave, uniforme sobre toda la maceta",
                         "target":"Sustrato — hasta que escurra por los drenajes"}},
    {"id":"geranio",       "name":"Geranio 🌺",             "location":"maceta",
     "base_days":4,  "heat_factor":0.50, "monsoon_bonus":1, "cool_factor":1.5,
     "pot":True, "pot_diameter_cm":20, "drought_tolerance":2,
     "fertilize_weeks":4, "pest_season":[4,5],
     # Maceta 20cm ~1.5L → goteo ~0.8 L/min, 2 min
     "watering_profile":{"flow_lpm":0.8,"duration_min":2,"heat_extra_min":1,"cool_less_min":1,
                         "method":"Regadera suave directo al sustrato",
                         "target":"Base — NO flores ni hojas"}},
    {"id":"vinca",         "name":"Vinca de Madagascar 🌼", "location":"maceta",
     "base_days":3,  "heat_factor":0.45, "monsoon_bonus":1, "cool_factor":1.5,
     "pot":True, "pot_diameter_cm":45, "drought_tolerance":2,
     "fertilize_weeks":4, "pest_season":[4,5,9],
     # Maceta grande 45cm ~4L → goteo suave ~0.8 L/min, 5 min
     "watering_profile":{"flow_lpm":0.8,"duration_min":5,"heat_extra_min":2,"cool_less_min":1,
                         "method":"Regadera suave y uniforme sobre el sustrato",
                         "target":"Sustrato — hasta drenar. NO mojar flores"}},
]

PLANT_MAP = {p["id"]: p for p in PLANTS}

# ─── GAMIFICATION ─────────────────────────────────────────────────────────────

LEVELS = [
    (0,   "🌱 Jardinero Novato"),
    (10,  "💧 Regador Consistente"),
    (25,  "🌿 Cuidador de Plantas"),
    (50,  "🌻 Guardián del Jardín"),
    (100, "🌵 Veterano del Desierto"),
    (200, "🦅 Maestro del Desierto"),
    (365, "👑 Leyenda de Tucson"),
]

ACHIEVEMENTS = [
    {"id":"first_water",      "name":"Primera Gota 💧",        "desc":"Regaste por primera vez",
     "check": lambda m,s: m.get("total_waterings",0) >= 1},
    {"id":"week_streak",      "name":"Semana Perfecta 🔥",     "desc":"7 días de racha",
     "check": lambda m,s: m.get("streak",0) >= 7},
    {"id":"month_streak",     "name":"Mes de Hierro 💪",       "desc":"30 días de racha",
     "check": lambda m,s: m.get("streak",0) >= 30},
    {"id":"hundred_waterings","name":"Centurión 💯",           "desc":"100 riegos registrados",
     "check": lambda m,s: m.get("total_waterings",0) >= 100},
    {"id":"all_plants_day",   "name":"Ronda Completa 🎯",      "desc":"Todas las plantas el mismo día",
     "check": lambda m,s: m.get("all_same_day",False)},
    {"id":"heat_survivor",    "name":"Sobreviviente 🔥",       "desc":"Jardín vivo con >40°C registrados",
     "check": lambda m,s: m.get("days_over_40c",0) >= 1},
    {"id":"rain_saver",       "name":"Ahorrista 🌧️",          "desc":"La lluvia salvó tus plantas 5 veces",
     "check": lambda m,s: m.get("rain_saves",0) >= 5},
    {"id":"early_bird",       "name":"Madrugador ⚡",          "desc":"Regaste antes de las 9 PM por 5 días",
     "check": lambda m,s: m.get("early_waterings",0) >= 5},
    {"id":"night_owl",        "name":"Jardinero Nocturno 🦉",  "desc":"Regaste después de medianoche 3 veces",
     "check": lambda m,s: m.get("midnight_waterings",0) >= 3},
    {"id":"fertilizer_pro",   "name":"Nutricionista 🌿",       "desc":"Fertilizaste 3 plantas en un mes",
     "check": lambda m,s: m.get("fertilizations_this_month",0) >= 3},
    {"id":"comeback",         "name":"El Gran Regreso 🏆",     "desc":"Volviste 7 días tras romper racha",
     "check": lambda m,s: m.get("comeback_streak",0) >= 7},
    {"id":"year_garden",      "name":"Un Año en el Jardín 🎂", "desc":"365 días usando el bot",
     "check": lambda m,s: m.get("days_using_bot",0) >= 365},
]

def get_level(total: int) -> tuple:
    current, nxt = LEVELS[0][1], None
    for i, (thr, name) in enumerate(LEVELS):
        if total >= thr:
            current = name
            nxt = LEVELS[i+1][1] if i+1 < len(LEVELS) else None
        else:
            break
    return current, nxt

def xp_bar(total: int) -> str:
    for i, (thr, _) in enumerate(LEVELS):
        if i+1 < len(LEVELS) and total < LEVELS[i+1][0]:
            prog   = total - thr
            needed = LEVELS[i+1][0] - thr
            filled = int((prog/needed)*10)
            return f"[{'█'*filled}{'░'*(10-filled)}] {prog}/{needed}"
    return "[██████████] MAX 👑"

def check_achievements(state: dict, meta: dict) -> list:
    unlocked = meta.setdefault("unlocked_achievements", [])
    new_ones  = []
    for ach in ACHIEVEMENTS:
        if ach["id"] not in unlocked:
            try:
                if ach["check"](meta, state):
                    unlocked.append(ach["id"])
                    new_ones.append(ach)
            except Exception:
                pass
    return new_ones

# ─── STATE ────────────────────────────────────────────────────────────────────

STATE_FILE = "/data/watering_state.json"
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
        logging.error(f"Save error: {e}")

def verify_volume() -> bool:
    try:
        os.makedirs("/data", exist_ok=True)
        with open("/data/.chk", "w") as f: f.write("ok")
        os.remove("/data/.chk")
        return True
    except Exception:
        return False

def get_meta(state: dict) -> dict:
    return state.setdefault("_meta", {
        "streak":0, "streak_no_skip":0, "comeback_streak":0,
        "last_streak_date":None, "last_activity":None,
        "total_waterings":0, "rain_saves":0, "early_waterings":0,
        "midnight_waterings":0, "frost_alerts_acted":0,
        "fertilizations_this_month":0, "fert_reset_month":None,
        "monsoon_seasons_survived":0, "days_over_40c":0,
        "days_using_bot":0, "all_same_day":False,
        "rain_log":[], "travel_until":None,
        "fertilize_log":{}, "watering_history":[],
        "unlocked_achievements":[], "bot_start_date":date.today().isoformat(),
    })

# ─── RAIN / SEASON / ET ───────────────────────────────────────────────────────

def log_rain(state, mm):
    if mm <= 0: return
    meta  = get_meta(state)
    today = date.today().isoformat()
    log   = meta.setdefault("rain_log", [])
    if not any(r["date"] == today for r in log):
        log.append({"date": today, "mm": round(mm,1)})
    cutoff = (date.today()-timedelta(days=14)).isoformat()
    meta["rain_log"] = [r for r in log if r["date"] >= cutoff]

def recent_rain(state, days=3) -> float:
    meta   = get_meta(state)
    cutoff = (date.today()-timedelta(days=days)).isoformat()
    return sum(r["mm"] for r in meta.get("rain_log",[]) if r["date"] >= cutoff)

def get_season() -> str:
    m = date.today().month
    if m in (7,8,9):       return "monsoon"
    if m in (6,10):        return "hot"
    if m in (11,12,1,2):   return "cool"
    return "spring"

SEASON_LABELS = {
    "monsoon":"🌧️ Monzón","hot":"🔥 Calor Extremo",
    "cool":"❄️ Invierno","spring":"🌱 Primavera",
}

def et_factor(temp_c, humidity, wind_ms) -> float:
    if temp_c is None: return 1.0
    eto_ref = TUCSON_ETO_REF.get(date.today().month, 5.0)
    hum     = humidity or 25
    vpd     = max(0, 1-hum/100) * 0.6108 * (2.71828**(17.27*temp_c/(temp_c+237.3)))
    eto_now = vpd * (1+(wind_ms or 0)*0.04) * 3.5
    return max(0.5, min(1.8, eto_now/eto_ref))

# ─── INTERVAL CALC ────────────────────────────────────────────────────────────

def pot_adj_i(d): return 0 if not d else (-1 if d<18 else (0 if d<=35 else (1 if d<=50 else 2)))
def pot_adj_d(d): return 0 if not d else (-1 if d<18 else (0 if d<=35 else (1 if d<=50 else 2)))

def get_adaptive(state, pid) -> float:
    hist = [h for h in get_meta(state).get("watering_history",[]) if h["pid"]==pid]
    if len(hist) < 3: return 1.0
    ratios = [h["actual"]/h["suggested"] for h in hist[-5:] if h["suggested"]>0]
    return max(0.75, min(1.25, sum(ratios)/len(ratios))) if ratios else 1.0

def calc_interval(plant, temp_c, season, et=1.0, soil_rain=0.0, adaptive=1.0) -> int:
    base = plant["base_days"]
    if season=="cool":      iv = int(base*plant["cool_factor"])
    elif season=="monsoon": iv = base+plant["monsoon_bonus"]
    elif season=="hot":     iv = max(1, int(base*plant["heat_factor"]))
    else:                   iv = base
    if temp_c is not None:
        if temp_c>=41:    iv = max(1, int(iv*0.65))
        elif temp_c>=38:  iv = max(1, int(iv*0.80))
        elif temp_c<=8:   iv = int(iv*1.60)
    iv = max(1, int(iv/et))
    if not plant["pot"] and soil_rain>0:
        iv += min(base//2, int(soil_rain/5))
    if plant["pot"]:
        iv += pot_adj_i(plant.get("pot_diameter_cm"))
        if season!="cool": iv = max(1, iv-1)
    return max(1, round(iv*adaptive))

def calc_duration(plant, temp_c, season, et=1.0) -> int:
    wp   = plant["watering_profile"]
    mins = wp["duration_min"]
    if season=="cool":                        mins = max(1, mins-wp["cool_less_min"])
    elif temp_c is not None and temp_c>=38:   mins += wp["heat_extra_min"]
    if et>1.4:                                mins += 1
    if plant["pot"]:                          mins += pot_adj_d(plant.get("pot_diameter_cm"))
    return max(1, mins)

def plant_status(plant, state, temp_c, season, et, soil_r) -> dict:
    """Returns full status dict for a plant."""
    pid        = plant["id"]
    adaptive   = get_adaptive(state, pid)
    interval   = calc_interval(plant, temp_c, season, et, soil_r, adaptive)
    mins       = calc_duration(plant, temp_c, season, et)
    last       = state.get(pid, {}).get("last_watered")
    today      = date.today().isoformat()

    if last is None:
        days_since = 0
        overdue    = 0
        status_str = "🆕 Nueva"
    else:
        days_since = (date.today()-date.fromisoformat(last)).days
        overdue    = days_since - interval
        if overdue > 1:     status_str = f"🚨 Atrasada +{overdue}d"
        elif overdue == 1:  status_str = "🔶 Atrasada 1d"
        elif overdue == 0:  status_str = "⏰ Toca hoy"
        elif interval-days_since == 1: status_str = "🟡 Mañana"
        else:               status_str = f"✅ En {interval-days_since}d"

    watered_today = last == today
    return {
        "interval": interval, "mins": mins, "overdue": overdue,
        "days_since": days_since, "status_str": status_str,
        "watered_today": watered_today, "last": last,
    }

# ─── WEATHER ──────────────────────────────────────────────────────────────────

async def get_weather() -> dict:
    icon_map = {"01":"☀️","02":"⛅","03":"🌥️","04":"☁️","09":"🌧️",
                "10":"🌦️","11":"⛈️","13":"🌨️","50":"🌫️"}
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            cr, fr = await asyncio.gather(
                cl.get(f"https://api.openweathermap.org/data/2.5/weather"
                       f"?lat={TUCSON_LAT}&lon={TUCSON_LON}&appid={OWM_KEY}&units=metric&lang=es"),
                cl.get(f"https://api.openweathermap.org/data/2.5/forecast"
                       f"?lat={TUCSON_LAT}&lon={TUCSON_LON}&appid={OWM_KEY}&units=metric&cnt=16"),
            )
        c, f  = cr.json(), fr.json()
        tom   = (date.today()+timedelta(days=1)).isoformat()
        rain_tom, min_tom = 0.0, 99.0
        for slot in f.get("list",[]):
            sd = datetime.fromtimestamp(slot["dt"], tz=TUCSON_TZ).date().isoformat()
            if sd == tom:
                rain_tom += slot.get("rain",{}).get("3h",0.0)
                min_tom   = min(min_tom, slot["main"]["temp_min"])
        return {
            "ok":True,
            "temp_c":c["main"]["temp"], "feels_like":c["main"]["feels_like"],
            "humidity":c["main"]["humidity"], "wind_ms":c.get("wind",{}).get("speed",0),
            "rain_mm":c.get("rain",{}).get("3h",0.0),
            "rain_tomorrow":rain_tom,
            "min_temp_tomorrow":min_tom if min_tom<99 else None,
            "description":c["weather"][0]["description"].capitalize(),
            "icon":icon_map.get(c["weather"][0]["icon"][:2],"🌡️"),
        }
    except Exception as e:
        logging.warning(f"Weather error: {e}")
        return {"ok":False,"temp_c":None,"rain_mm":0.0,"rain_tomorrow":0.0,
                "min_temp_tomorrow":None,"humidity":None,"wind_ms":0}

# ─── TELEGRAM API HELPERS ─────────────────────────────────────────────────────

async def api_call(method: str, payload: dict) -> dict:
    """Generic Telegram API call."""
    async with httpx.AsyncClient(timeout=15) as cl:
        r = await cl.post(f"{API}/{method}", json=payload)
        return r.json()

async def send_msg(text: str, reply_markup: dict | None = None, chat_id: str | None = None) -> dict:
    payload = {
        "chat_id":    chat_id or CHAT_ID,
        "text":       text[:4096],
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await api_call("sendMessage", payload)

async def edit_msg(chat_id: str, message_id: int, text: str, reply_markup: dict | None = None):
    payload = {
        "chat_id":    chat_id,
        "message_id": message_id,
        "text":       text[:4096],
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    await api_call("editMessageText", payload)

async def answer_callback(callback_id: str, text: str = "", alert: bool = False):
    await api_call("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text":  text[:200],
        "show_alert": alert,
    })

# ─── KEYBOARD BUILDERS ────────────────────────────────────────────────────────

def kb_main_menu() -> dict:
    """Menú principal."""
    return {"inline_keyboard": [
        [{"text": "🌿 Ver mis plantas",   "callback_data": "menu_plants"},
         {"text": "💧 Regar todo",        "callback_data": "water_all"}],
        [{"text": "▶️ Iniciar riego",     "callback_data": "timer_prepare"},
         {"text": "🌤 Clima ahora",       "callback_data": "menu_weather"}],
        [{"text": "📊 Mi progreso",       "callback_data": "menu_progress"},
         {"text": "🏆 Logros",            "callback_data": "menu_achievements"}],
        [{"text": "📅 Mañana",            "callback_data": "menu_tomorrow"},
         {"text": "✈️ Modo viaje",        "callback_data": "menu_travel"}],
    ]}

def kb_plant_list(state, temp_c, season, et, soil_r) -> dict:
    """Lista de plantas como botones con indicador de estado."""
    rows = []
    row  = []
    for i, plant in enumerate(PLANTS):
        st    = plant_status(plant, state, temp_c, season, et, soil_r)
        # Indicador visual en el botón
        if st["watered_today"]:         icon = "✅"
        elif st["overdue"] > 1:         icon = "🚨"
        elif st["overdue"] >= 0:        icon = "💧"
        else:                           icon = "🟢"
        label = f"{icon} {plant['name']}"
        row.append({"text": label, "callback_data": f"plant_{plant['id']}"})
        if len(row) == 2 or i == len(PLANTS)-1:
            rows.append(row)
            row = []
    rows.append([{"text": "⬅️ Menú principal", "callback_data": "menu_main"}])
    return {"inline_keyboard": rows}

def kb_plant_actions(pid: str, watered_today: bool) -> dict:
    """Botones de acción para una planta específica."""
    water_btn = (
        {"text": "✅ Ya la regué", "callback_data": f"water_{pid}"}
        if not watered_today else
        {"text": "✅ Regada hoy", "callback_data": f"noop_{pid}"}
    )
    return {"inline_keyboard": [
        [water_btn],
        [{"text": "⏭ Saltar hoy",     "callback_data": f"skip_{pid}"},
         {"text": "💊 Fertilicé",     "callback_data": f"fert_{pid}"}],
        [{"text": "⬅️ Mis plantas",   "callback_data": "menu_plants"},
         {"text": "🏠 Menú",          "callback_data": "menu_main"}],
    ]}

def kb_water_all_confirm() -> dict:
    return {"inline_keyboard": [
        [{"text": "💧 Sí, regar todo", "callback_data": "water_all_confirm"},
         {"text": "❌ Cancelar",       "callback_data": "menu_main"}],
    ]}

def kb_back_main() -> dict:
    return {"inline_keyboard": [
        [{"text": "⬅️ Menú principal", "callback_data": "menu_main"}]
    ]}

def kb_travel() -> dict:
    return {"inline_keyboard": [
        [{"text": "✈️ 3 días",  "callback_data": "travel_3"},
         {"text": "✈️ 5 días",  "callback_data": "travel_5"},
         {"text": "✈️ 7 días",  "callback_data": "travel_7"}],
        [{"text": "✈️ 10 días", "callback_data": "travel_10"},
         {"text": "✈️ 14 días", "callback_data": "travel_14"}],
        [{"text": "🏠 Cancelar viaje",  "callback_data": "travel_off"},
         {"text": "⬅️ Menú",           "callback_data": "menu_main"}],
    ]}

# ─── TIMER SESSION (in-memory, per chat) ──────────────────────────────────────
# Guarda el estado del timer guiado mientras el usuario está regando.
# { chat_id: { "queue": [pid,...], "current": pid, "started_at": datetime,
#              "mins": int, "completed": [pid,...] } }

TIMER_SESSIONS: dict = {}

def kb_timer_running(pid: str, step: int, total: int) -> dict:
    """Botones mientras corre el timer de una planta."""
    return {"inline_keyboard": [
        [{"text": f"⏭ Siguiente planta ({step}/{total})",
          "callback_data": f"timer_next_{pid}"}],
        [{"text": "✅ Terminé todas",   "callback_data": "timer_done"},
         {"text": "❌ Cancelar riego", "callback_data": "timer_cancel"}],
    ]}

def kb_timer_start(due_pids: list) -> dict:
    """Botón para iniciar el timer guiado."""
    return {"inline_keyboard": [
        [{"text": f"▶️ Iniciar riego guiado ({len(due_pids)} plantas)",
          "callback_data": "timer_start"}],
        [{"text": "⬅️ Menú", "callback_data": "menu_main"}],
    ]}

def screen_timer_plant(pid: str, mins: float, step: int, total: int,
                       started_at: datetime) -> str:
    plant    = PLANT_MAP[pid]
    wp       = plant["watering_profile"]
    elapsed  = (datetime.now(TUCSON_TZ) - started_at).seconds // 60
    secs_tot = int(mins * 60)
    mm_s     = int(secs_tot % 60)
    mm_m     = int(mins)

    # Barra de progreso visual
    progress_pct = min(1.0, elapsed / max(1, mins))
    filled       = int(progress_pct * 12)
    bar          = "█" * filled + "░" * (12 - filled)

    voice = random.choice(VOICES.get(pid, {}).get("thirsty", ["Agua, por favor."]))

    lines = [
        f"⏱ <b>RIEGO EN CURSO</b>  [{step}/{total}]",
        f"{'━'*22}",
        f"",
        f"🪴 <b>{plant['name']}</b>",
        f"<i>\"{voice}\"</i>",
        f"",
        f"⏳ Tiempo: <b>{mm_m}:{mm_s:02d} min</b>",
        f"💧 Flujo: <b>{wp['flow_lpm']} L/min</b>  →  ~<b>{round(wp['flow_lpm']*mins,1)} L</b>",
        f"",
        f"🔧 {wp['method']}",
        f"🎯 {wp['target']}",
        f"",
        f"[{bar}] {int(progress_pct*100)}%",
        f"",
        f"<i>Toca ⏭ cuando termines esta planta</i>",
    ]
    return "\n".join(lines)

def screen_timer_summary(completed: list, skipped_timer: list) -> str:
    total_min = sum(PLANT_MAP[pid]["watering_profile"]["duration_min"]
                    for pid in completed if pid in PLANT_MAP)
    total_L   = sum(PLANT_MAP[pid]["watering_profile"]["flow_lpm"] *
                    PLANT_MAP[pid]["watering_profile"]["duration_min"]
                    for pid in completed if pid in PLANT_MAP)
    names = "\n".join(f"  ✅ {PLANT_MAP[pid]['name']}" for pid in completed if pid in PLANT_MAP)
    lines = [
        f"🎉 <b>¡Riego completado!</b>",
        f"{'━'*22}",
        f"",
        names,
    ]
    if skipped_timer:
        skip_names = "\n".join(f"  ⏭ {PLANT_MAP[pid]['name']}"
                               for pid in skipped_timer if pid in PLANT_MAP)
        lines += ["", skip_names]
    lines += [
        f"",
        f"{'━'*22}",
        f"⏱ Tiempo total: ~<b>{total_min} min</b>",
        f"💧 Agua usada: ~<b>{total_L:.0f} L</b>",
        f"",
        f"<i>Toca el botón para registrar el riego</i>",
    ]
    return "\n".join(lines)

def kb_timer_done_confirm() -> dict:
    return {"inline_keyboard": [
        [{"text": "✅ Registrar todo como regado", "callback_data": "timer_confirm_all"}],
        [{"text": "⬅️ Menú", "callback_data": "menu_main"}],
    ]}

# ─── SCREEN BUILDERS ──────────────────────────────────────────────────────────

def screen_main(meta: dict, wx: dict) -> str:
    total, streak = meta.get("total_waterings",0), meta.get("streak",0)
    level, _      = get_level(total)
    season        = get_season()
    now           = datetime.now(TUCSON_TZ)

    wx_line = (f"{wx['icon']} <b>{wx['temp_c']:.1f}°C</b> · {wx['humidity']}% hum"
               if wx.get("ok") else "🌡️ Clima no disponible")

    return (
        f"🌵 <b>Tucson Garden</b>\n"
        f"{'━'*22}\n"
        f"📅 {now.strftime('%A %d %b')} · {SEASON_LABELS[season]}\n"
        f"{wx_line}\n\n"
        f"👤 {level}\n"
        f"💧 {total} riegos  ·  🔥 {streak} días racha\n"
        f"{'━'*22}\n"
        f"<i>¿Qué quieres hacer?</i>"
    )

def screen_plant_list(state, temp_c, season, et, soil_r) -> str:
    now    = datetime.now(TUCSON_TZ)
    lines  = [f"🌿 <b>Mis plantas</b> — {now.strftime('%d %b')}",
              f"{'━'*22}", ""]
    due_count = 0
    for plant in PLANTS:
        st = plant_status(plant, state, temp_c, season, et, soil_r)
        lines.append(f"{st['status_str']}  {plant['name']}")
        if st["overdue"] >= 0 and not st["watered_today"]:
            due_count += 1
    lines += ["", f"{'━'*22}"]
    if due_count:
        lines.append(f"💧 <b>{due_count} planta(s) necesitan agua hoy</b>")
    else:
        lines.append("✅ <b>Todo al día — buen trabajo</b>")
    lines.append("\n<i>Toca una planta para ver detalles</i>")
    return "\n".join(lines)

def screen_plant_detail(plant: dict, state: dict, temp_c, season, et, soil_r) -> str:
    st  = plant_status(plant, state, temp_c, season, et, soil_r)
    wp  = plant["watering_profile"]
    pid = plant["id"]

    # Voz de la planta
    v = VOICES.get(pid, {})
    if st["watered_today"]:
        voice = random.choice(v.get("happy", ["Gracias por el agua."]))
    elif season == "cool":
        voice = random.choice(v.get("winter", v.get("happy", ["Estoy bien."])))
    elif st["overdue"] > 1:
        voice = random.choice(v.get("dying", ["Necesito agua urgente."]))
    elif st["overdue"] >= 0:
        voice = random.choice(v.get("thirsty", ["Necesito agua."]))
    else:
        voice = random.choice(v.get("happy", ["Estoy bien."]))

    loc = "🪣 Maceta" if plant["pot"] else "🌍 Tierra"

    lines = [
        f"{plant['name']}  ·  {loc}",
        f"{'━'*22}",
        f"",
        f"<i>\"{voice}\"</i>",
        f"",
        f"{'━'*22}",
        f"📊 Estado: <b>{st['status_str']}</b>",
    ]

    if st["last"]:
        lines.append(f"🗓 Último riego: hace <b>{st['days_since']} días</b>")

    lines += [
        f"📆 Intervalo actual: cada <b>{st['interval']} días</b>",
        f"",
        f"<b>Cómo regar esta noche:</b>",
        f"⏱ <b>{st['mins']} minutos</b>  ·  💧 <b>{wp['flow_lpm']} L/min</b>  →  ~<b>{round(wp['flow_lpm']*st['mins'],1)} L</b>",
        f"🔧 {wp['method']}",
        f"🎯 {wp['target']}",
    ]

    # Fertilización pendiente
    fert_weeks = plant.get("fertilize_weeks")
    if fert_weeks and get_season() != "cool":
        flog = get_meta(state).get("fertilize_log", {})
        last_f = flog.get(pid)
        if last_f:
            days_f = (date.today()-date.fromisoformat(last_f)).days
            if days_f >= fert_weeks*7:
                lines += ["", f"🌿 <b>¡Fertilización pendiente!</b> (hace {days_f} días)"]
        else:
            lines += ["", f"🌿 Fertiliza cada {fert_weeks} semanas"]

    # Plaga de temporada
    month = date.today().month
    if month in plant.get("pest_season", []):
        pest_tips = {
            "cycas_1":   "🐛 Revisa cochinilla en base de frondas",
            "cycas_2":   "🐛 Revisa cochinilla en base de frondas",
            "rosal":     "🐛 Revisa pulgón en brotes nuevos",
            "toronja":   "🐛 Revisa minador de hoja y escama",
            "limon":     "🐛 Revisa minador de hoja y escama",
            "mandarina": "🐛 Revisa escama y trips en frutos",
            "lilly_asiatica": "🐛 Revisa ácaros debajo de hojas",
            "geranio":   "🐛 Revisa mosca blanca debajo de hojas",
            "vinca":     "🐛 Revisa ácaros y trips",
        }
        if pid in pest_tips:
            lines += ["", pest_tips[pid]]

    return "\n".join(lines)

def screen_progress(meta: dict, state: dict) -> str:
    total  = meta.get("total_waterings", 0)
    streak = meta.get("streak", 0)
    level, nxt = get_level(total)
    unlocked   = len(meta.get("unlocked_achievements", []))
    rain30     = sum(r["mm"] for r in meta.get("rain_log", [])
                     if r["date"] >= (date.today()-timedelta(days=30)).isoformat())
    start      = meta.get("bot_start_date", date.today().isoformat())
    days_using = (date.today()-date.fromisoformat(start)).days

    lines = [
        f"📊 <b>Mi progreso</b>",
        f"{'━'*22}",
        f"",
        f"👤 <b>{level}</b>",
        f"⬆️ {xp_bar(total)}",
        f"",
        f"💧 Riegos totales: <b>{total}</b>",
        f"🔥 Racha actual: <b>{streak} días</b>",
        f"📅 Días usando el bot: <b>{days_using}</b>",
        f"🌧️ Lluvia este mes: <b>{rain30:.0f} mm</b>",
        f"🏆 Logros: <b>{unlocked}/{len(ACHIEVEMENTS)}</b>",
    ]
    if nxt:
        lines += ["", f"<i>Próximo nivel: {nxt}</i>"]
    return "\n".join(lines)

def screen_achievements(meta: dict) -> str:
    total    = meta.get("total_waterings", 0)
    level, _ = get_level(total)
    unlocked = set(meta.get("unlocked_achievements", []))
    lines    = [
        f"🏆 <b>Logros</b>",
        f"👤 {level}  ·  {len(unlocked)}/{len(ACHIEVEMENTS)}",
        f"{'━'*22}",
        "",
    ]
    for ach in ACHIEVEMENTS:
        done = ach["id"] in unlocked
        lines.append(f"{'✅' if done else '🔒'} <b>{ach['name']}</b>")
        if not done:
            lines.append(f"   <i>{ach['desc']}</i>")
    return "\n".join(lines)

def screen_weather(wx: dict) -> str:
    if not wx.get("ok"):
        return "🌡️ <b>Clima</b>\n\nNo se pudo obtener el clima ahora mismo."
    lines = [
        f"🌤 <b>Clima — Tucson, AZ</b>",
        f"{'━'*22}",
        f"",
        f"{wx['icon']} {wx['description']}",
        f"🌡️ <b>{wx['temp_c']:.1f}°C</b> · sensación {wx['feels_like']:.0f}°C",
        f"💧 Humedad: {wx['humidity']}%",
        f"💨 Viento: {wx['wind_ms']:.1f} m/s",
    ]
    if wx.get("rain_mm", 0) > 0:
        lines.append(f"🌧️ Lluvia reciente: {wx['rain_mm']:.1f} mm")
    if wx.get("rain_tomorrow", 0) >= 3:
        lines.append(f"☔ Mañana: ~{wx['rain_tomorrow']:.0f} mm pronosticados")
    if wx.get("min_temp_tomorrow") and wx["min_temp_tomorrow"] < 5:
        lines.append(f"🥶 Mínima mañana: {wx['min_temp_tomorrow']:.1f}°C — protege macetas")
    return "\n".join(lines)

def screen_tomorrow(state, temp_c, season, et, soil_r) -> str:
    due = []
    for plant in PLANTS:
        pid      = plant["id"]
        last     = state.get(pid, {}).get("last_watered")
        adaptive = get_adaptive(state, pid)
        interval = calc_interval(plant, temp_c, season, et, soil_r, adaptive)
        if last:
            days_then = (date.today()-date.fromisoformat(last)).days + 1
            if days_then >= interval:
                due.append(plant)
    if not due:
        return "📅 <b>Mañana</b>\n\n✅ No toca regar ninguna planta mañana. ¡Descansa!"
    names = "\n".join(f"  • {p['name']}" for p in due)
    return f"📅 <b>Mañana tocan:</b>\n\n{names}\n\n<i>{len(due)} planta(s)</i>"

# ─── REGISTER WATERING ────────────────────────────────────────────────────────

def register_watering(state: dict, pids: list, temp_c, season, et, soil_r, now: datetime):
    """Core logic to mark plants as watered and update all stats."""
    meta  = get_meta(state)
    today = date.today().isoformat()

    newly = []
    for pid in pids:
        plant    = PLANT_MAP.get(pid)
        if not plant: continue
        pstate   = state.setdefault(pid, {})
        last     = pstate.get("last_watered")
        adaptive = get_adaptive(state, pid)
        interval = calc_interval(plant, temp_c, season, et, soil_r, adaptive)

        if last == today:
            continue  # ya regada hoy

        if last:
            actual = (date.today()-date.fromisoformat(last)).days
            meta.setdefault("watering_history", []).append(
                {"date": today, "pid": pid, "suggested": interval, "actual": actual}
            )
        pstate["last_watered"] = today
        pstate.pop("skip_until", None)
        newly.append(pid)

    if not newly:
        return newly

    meta["total_waterings"] = meta.get("total_waterings", 0) + len(newly)
    meta["last_activity"]   = today

    # Reset fertilization counter monthly
    if meta.get("fert_reset_month") != date.today().month:
        meta["fertilizations_this_month"] = 0
        meta["fert_reset_month"] = date.today().month

    # Prune history
    hist = meta.get("watering_history", [])
    if len(hist) > 90:
        meta["watering_history"] = hist[-90:]

    # All same day achievement
    if all(state.get(p["id"],{}).get("last_watered") == today for p in PLANTS):
        meta["all_same_day"] = True

    # Streak
    last_s    = meta.get("last_streak_date")
    yesterday = (date.today()-timedelta(days=1)).isoformat()
    if last_s == yesterday:
        meta["streak"] = meta.get("streak", 0) + 1
        meta["streak_no_skip"] = meta.get("streak_no_skip", 0) + 1
    elif last_s != today:
        if meta.get("streak", 0) > 0:
            meta["comeback_streak"] = 0
        meta["streak"] = 1
        meta["streak_no_skip"] = 1
        meta["comeback_streak"] = meta.get("comeback_streak", 0) + 1
    meta["last_streak_date"] = today

    # Time-based achievements
    if now.hour <= 20:
        meta["early_waterings"] = meta.get("early_waterings", 0) + 1
    if 0 <= now.hour < 4:
        meta["midnight_waterings"] = meta.get("midnight_waterings", 0) + 1

    return newly

# ─── EVENING PUSH NOTIFICATION ────────────────────────────────────────────────

async def evening_check():
    """8 PM push — lista de plantas con botones directos."""
    now    = datetime.now(TUCSON_TZ)
    season = get_season()
    wx     = await get_weather()
    state  = load_state()
    today  = date.today().isoformat()
    meta   = get_meta(state)

    temp_c    = wx.get("temp_c")
    rain_mm   = wx.get("rain_mm", 0.0)
    et        = et_factor(temp_c, wx.get("humidity"), wx.get("wind_ms", 0))

    if rain_mm > 0: log_rain(state, rain_mm)
    soil_r = recent_rain(state, days=3)

    # Modo viaje
    travel_until = meta.get("travel_until")
    if travel_until and travel_until >= today:
        save_state(state)
        return

    # Días >40°C
    if temp_c and temp_c >= 40:
        meta["days_over_40c"] = meta.get("days_over_40c", 0) + 1

    # Días usando bot
    start = date.fromisoformat(meta.get("bot_start_date", today))
    meta["days_using_bot"] = (date.today()-start).days

    due, skipped = [], []

    for plant in PLANTS:
        pid      = plant["id"]
        pstate   = state.setdefault(pid, {})
        last     = pstate.get("last_watered")
        adaptive = get_adaptive(state, pid)
        interval = calc_interval(plant, temp_c, season, et, soil_r, adaptive)
        mins     = calc_duration(plant, temp_c, season, et)
        pstate.update({"interval_days": interval, "duration_min": mins})

        if last is None:
            pstate["last_watered"] = today
            due.append((plant, interval, mins, 0))
            continue

        days_since = (date.today()-date.fromisoformat(last)).days
        skip_until = pstate.get("skip_until", "")
        if skip_until >= today:
            skipped.append(plant)
            continue

        if days_since >= interval:
            if not plant["pot"] and rain_mm >= 8.0:
                meta["rain_saves"] = meta.get("rain_saves", 0) + 1
                skipped.append(plant)
            else:
                overdue = days_since - interval
                due.append((plant, interval, mins, overdue))

    new_ach = check_achievements(state, meta)
    save_state(state)

    # Achievement notifications
    for ach in new_ach:
        await send_msg(
            f"🏆 <b>¡LOGRO DESBLOQUEADO!</b>\n\n"
            f"<b>{ach['name']}</b>\n{ach['desc']}\n\n"
            f"<i>Sigue así, jardinero 💪</i>"
        )

    if not due:
        logging.info("8 PM: nada por regar.")
        return

    # Build notification
    total_min = sum(m for _, _, m, _ in due)
    total_L   = sum(p["watering_profile"]["flow_lpm"]*m for p, _, m, _ in due)
    level, _  = get_level(meta.get("total_waterings", 0))
    streak    = meta.get("streak", 0)

    # Dynamic intro
    if temp_c and temp_c >= 40:
        intro = f"🔥 <b>{temp_c:.0f}°C en Tucson.</b> Tus plantas están contando los minutos."
    elif rain_mm >= 5:
        intro = f"🌧️ <b>Llovió {rain_mm:.0f}mm hoy.</b> El cielo ayudó. Tú haz tu parte."
    elif streak >= 7:
        intro = f"🔥 <b>¡{streak} días de racha!</b> Tus plantas lo están notando."
    else:
        intro = random.choice([
            "🌙 La noche llegó. Es hora de darles agua.",
            "🌵 Tucson no da tregua. El jardín tampoco puede esperar.",
            "💧 El momento del riego ha llegado.",
            "🌙 Buenas noches. El jardín tiene hambre de agua.",
        ])

    wx_line = (f"{wx['icon']} <b>{temp_c:.1f}°C</b> · {wx.get('humidity')}%hum"
               if wx.get("ok") else "🌡️ Clima no disponible")

    # Plant lines
    plant_lines = []
    due.sort(key=lambda x: -x[3])  # urgentes primero
    for plant, interval, mins, overdue in due:
        flow   = plant["watering_profile"]["flow_lpm"]
        liters = round(flow*mins, 1)
        v      = VOICES.get(plant["id"], {})
        voice  = random.choice(v.get("thirsty" if overdue==0 else "dying", ["Necesito agua."]))
        if overdue > 1:   urg = f"🚨 +{overdue}d"
        elif overdue == 1: urg = "🔶 +1d"
        else:              urg = "⏰"
        plant_lines.append(
            f"{urg} <b>{plant['name']}</b>\n"
            f"<i>\"{voice}\"</i>\n"
            f"⏱{mins}min · 💧{flow}L/min · ~{liters}L"
        )

    skipped_line = ""
    if skipped:
        skipped_line = "\n⏭ Saltadas: " + ", ".join(p["name"] for p in skipped)

    msg = (
        f"{'━'*22}\n"
        f"{intro}\n"
        f"{'━'*22}\n\n"
        f"{wx_line}  ·  👤 {level}  ·  🔥{streak}d\n\n"
        f"🪴 <b>{len(due)} planta(s) esta noche:</b>\n\n" +
        "\n\n".join(plant_lines) +
        f"\n\n{'━'*22}\n"
        f"⏳ ~{total_min} min  ·  💧 ~{total_L:.0f} L"
        + skipped_line
    )

    # Inline keyboard con las plantas que tocan + regar todo
    rows = []
    for plant, _, _, _ in due[:4]:  # max 4 botones individuales
        rows.append([{"text": f"✅ {plant['name']}", "callback_data": f"water_{plant['id']}"}])
    if len(due) > 1:
        rows.append([{"text": "💧 Regar todas de una vez", "callback_data": "water_all_confirm"}])
    rows.append([{"text": "🌿 Ver jardín completo", "callback_data": "menu_plants"}])

    await send_msg(msg, reply_markup={"inline_keyboard": rows})

    # Frost alert separado
    min_tom = wx.get("min_temp_tomorrow")
    if min_tom and min_tom < 2:
        pots = [p["name"] for p in PLANTS if p["pot"]]
        await send_msg(
            f"🥶 <b>ALERTA DE HELADA</b>\n\n"
            f"Mañana mínima: <b>{min_tom:.1f}°C</b>\n\n"
            f"⚠️ Mete o cubre:\n" + "\n".join(f"  • {n}" for n in pots)
        )

    logging.info(f"Evening push: {len(due)} plantas.")

async def weekly_summary():
    season = get_season()
    wx     = await get_weather()
    state  = load_state()
    meta   = get_meta(state)
    temp_c = wx.get("temp_c")
    et     = et_factor(temp_c, wx.get("humidity"), wx.get("wind_ms",0))
    soil_r = recent_rain(state, days=3)

    msg  = screen_progress(meta, state)
    tips = {
        "monsoon":"🌧️ <b>Tips Monzón:</b> Revisa drenaje de macetas. La humedad engaña.",
        "hot":    "🔥 <b>Tips Calor:</b> Mulch en cítricos. Macetas pueden necesitar agua diaria.",
        "cool":   "❄️ <b>Tips Invierno:</b> Cycas en modo meditación. Protege vinca si baja de 5°C.",
        "spring": "🌱 <b>Tips Primavera:</b> Fertiliza cítricos. Poda el rosal. Revisa pulgón.",
    }
    await send_msg(msg, reply_markup=kb_back_main())
    if season in tips:
        await send_msg(tips[season], reply_markup=kb_main_menu())

# ─── CALLBACK HANDLER ─────────────────────────────────────────────────────────

async def handle_callback(update: dict):
    cb      = update["callback_query"]
    data    = cb["data"]
    cb_id   = cb["id"]
    chat_id = str(cb["message"]["chat"]["id"])
    msg_id  = cb["message"]["message_id"]

    wx     = await get_weather()
    state  = load_state()
    meta   = get_meta(state)
    season = get_season()
    temp_c = wx.get("temp_c")
    et     = et_factor(temp_c, wx.get("humidity"), wx.get("wind_ms",0))
    soil_r = recent_rain(state, days=3)
    now    = datetime.now(TUCSON_TZ)

    await answer_callback(cb_id)  # dismiss loading spinner immediately

    # ── Menú principal ─────────────────────────────────────────────────────
    if data == "menu_main":
        await edit_msg(chat_id, msg_id, screen_main(meta, wx), kb_main_menu())

    # ── Lista de plantas ───────────────────────────────────────────────────
    elif data == "menu_plants":
        await edit_msg(chat_id, msg_id,
                       screen_plant_list(state, temp_c, season, et, soil_r),
                       kb_plant_list(state, temp_c, season, et, soil_r))

    # ── Detalle de planta ──────────────────────────────────────────────────
    elif data.startswith("plant_"):
        pid   = data[6:]
        plant = PLANT_MAP.get(pid)
        if plant:
            st  = plant_status(plant, state, temp_c, season, et, soil_r)
            txt = screen_plant_detail(plant, state, temp_c, season, et, soil_r)
            await edit_msg(chat_id, msg_id, txt,
                           kb_plant_actions(pid, st["watered_today"]))

    # ── Regar planta individual ────────────────────────────────────────────
    elif data.startswith("water_") and not data.startswith("water_all"):
        pid   = data[6:]
        plant = PLANT_MAP.get(pid)
        if plant:
            newly = register_watering(state, [pid], temp_c, season, et, soil_r, now)
            new_ach = check_achievements(state, meta)
            save_state(state)

            if newly:
                voice = random.choice(VOICES.get(pid,{}).get("happy",["¡Gracias!"]))
                await answer_callback(cb_id, f"✅ {plant['name']} regada!", alert=False)
                st  = plant_status(plant, state, temp_c, season, et, soil_r)
                txt = screen_plant_detail(plant, state, temp_c, season, et, soil_r)
                await edit_msg(chat_id, msg_id, txt, kb_plant_actions(pid, True))
                for ach in new_ach:
                    await send_msg(f"🏆 <b>¡LOGRO!</b> {ach['name']}\n{ach['desc']}")
            else:
                await answer_callback(cb_id, "Ya estaba regada hoy ✅")

    # ── Regar todo (confirmar) ─────────────────────────────────────────────
    elif data == "water_all":
        await edit_msg(chat_id, msg_id,
                       "💧 <b>¿Regar todas las plantas?</b>\n\nEsto marcará las 9 plantas como regadas hoy.",
                       kb_water_all_confirm())

    elif data == "water_all_confirm":
        all_ids = [p["id"] for p in PLANTS]
        newly   = register_watering(state, all_ids, temp_c, season, et, soil_r, now)
        new_ach = check_achievements(state, meta)
        save_state(state)

        streak = meta.get("streak", 0)
        total  = meta.get("total_waterings", 0)
        level, _ = get_level(total)

        # Celebración por planta
        voices_txt = ""
        for pid in newly[:3]:
            p     = PLANT_MAP[pid]
            voice = random.choice(VOICES.get(pid,{}).get("happy",["¡Gracias!"]))
            voices_txt += f"\n{p['name']}: <i>\"{voice}\"</i>"

        msg = (
            f"🎉 <b>¡JARDÍN COMPLETO!</b>\n"
            f"{'━'*22}\n"
            f"Regaste {len(newly)} planta(s) de una.\n"
            + voices_txt +
            f"\n\n{'━'*22}\n"
            f"👤 {level}  ·  💧 {total}  ·  🔥{streak}d"
        )
        await edit_msg(chat_id, msg_id, msg, kb_back_main())
        for ach in new_ach:
            await send_msg(f"🏆 <b>¡LOGRO!</b> {ach['name']}\n{ach['desc']}")

    # ── Skip planta ────────────────────────────────────────────────────────
    elif data.startswith("skip_"):
        pid   = data[5:]
        plant = PLANT_MAP.get(pid)
        if plant:
            tomorrow = (date.today()+timedelta(days=1)).isoformat()
            state.setdefault(pid, {})["skip_until"] = tomorrow
            save_state(state)
            voice = random.choice(VOICES.get(pid,{}).get("happy",["Ok, descansaré hoy."]))
            await answer_callback(cb_id, f"⏭ {plant['name']} saltada hasta mañana")
            await edit_msg(chat_id, msg_id,
                           f"⏭ <b>{plant['name']}</b> saltada hasta mañana\n\n<i>\"{voice}\"</i>",
                           kb_back_main())

    # ── Fertilizar ─────────────────────────────────────────────────────────
    elif data.startswith("fert_"):
        pid   = data[5:]
        plant = PLANT_MAP.get(pid)
        if plant:
            meta.setdefault("fertilize_log", {})[pid] = date.today().isoformat()
            meta["fertilizations_this_month"] = meta.get("fertilizations_this_month",0) + 1
            new_ach = check_achievements(state, meta)
            save_state(state)
            voice = random.choice(VOICES.get(pid,{}).get("happy",["¡Gracias!"]))
            await answer_callback(cb_id, f"🌿 {plant['name']} fertilizada", alert=False)
            await edit_msg(chat_id, msg_id,
                           f"🌿 <b>{plant['name']}</b> fertilizada hoy\n\n<i>\"{voice}\"</i>",
                           kb_back_main())
            for ach in new_ach:
                await send_msg(f"🏆 <b>¡LOGRO!</b> {ach['name']}\n{ach['desc']}")

    # ── Progreso ───────────────────────────────────────────────────────────
    elif data == "menu_progress":
        await edit_msg(chat_id, msg_id, screen_progress(meta, state), kb_back_main())

    # ── Logros ─────────────────────────────────────────────────────────────
    elif data == "menu_achievements":
        await edit_msg(chat_id, msg_id, screen_achievements(meta), kb_back_main())

    # ── Clima ──────────────────────────────────────────────────────────────
    elif data == "menu_weather":
        await edit_msg(chat_id, msg_id, screen_weather(wx), kb_back_main())

    # ── Mañana ─────────────────────────────────────────────────────────────
    elif data == "menu_tomorrow":
        await edit_msg(chat_id, msg_id,
                       screen_tomorrow(state, temp_c, season, et, soil_r),
                       kb_back_main())

    # ── Viaje menu ─────────────────────────────────────────────────────────
    elif data == "menu_travel":
        travel_until = meta.get("travel_until")
        active_msg   = (f"\n\n✈️ Viaje activo hasta: <b>{travel_until}</b>"
                        if travel_until and travel_until >= date.today().isoformat() else "")
        await edit_msg(chat_id, msg_id,
                       f"✈️ <b>Modo Viaje</b>\n\n¿Cuántos días te vas?{active_msg}",
                       kb_travel())

    elif data.startswith("travel_") and data != "travel_off":
        days  = int(data.split("_")[1])
        until = (date.today()+timedelta(days=days)).isoformat()
        meta["travel_until"] = until
        stressed = []
        for plant in PLANTS:
            pid      = plant["id"]
            last     = state.get(pid, {}).get("last_watered")
            adaptive = get_adaptive(state, pid)
            interval = calc_interval(plant, temp_c, season, et, 0, adaptive)
            if last:
                when_back = (date.today()-date.fromisoformat(last)).days + days
                overdue   = when_back - interval
                if overdue > 0:
                    stressed.append((plant["name"], overdue))
        stressed.sort(key=lambda x: -x[1])
        save_state(state)

        stress_txt = ""
        if stressed:
            stress_txt = "\n\n🚨 <b>Riesgo al regresar:</b>\n"
            stress_txt += "\n".join(f"  • {n}: +{d}d" for n,d in stressed)
            stress_txt += "\n\n💡 Riega bien antes de salir o pide a alguien que lo haga."
        else:
            stress_txt = "\n\n✅ Todas aguantarán sin problema."

        await edit_msg(chat_id, msg_id,
                       f"✈️ <b>Modo viaje: {days} días</b>\n"
                       f"Pausado hasta <b>{until}</b>{stress_txt}",
                       kb_back_main())

    elif data == "travel_off":
        meta.pop("travel_until", None)
        save_state(state)
        await edit_msg(chat_id, msg_id,
                       "🏠 <b>¡De regreso!</b>\nNotificaciones reactivadas.",
                       kb_main_menu())

    elif data.startswith("noop_"):
        await answer_callback(cb_id, "Ya regada hoy ✅")

    # ── Timer: preparar ────────────────────────────────────────────────────
    elif data == "timer_prepare":
        # Build queue: plantas que tocan hoy, en orden tierra→maceta
        due_pids = []
        for plant in PLANTS:
            pid      = plant["id"]
            last     = state.get(pid, {}).get("last_watered")
            adaptive = get_adaptive(state, pid)
            interval = calc_interval(plant, temp_c, season, et, soil_r, adaptive)
            today    = date.today().isoformat()
            if last == today:
                continue  # ya regada
            if last is None:
                due_pids.append(pid)
                continue
            days_since = (date.today()-date.fromisoformat(last)).days
            if days_since >= interval:
                due_pids.append(pid)

        if not due_pids:
            await edit_msg(chat_id, msg_id,
                           "✅ <b>No hay plantas que regar hoy.</b>\n\n"
                           "Todas están al día. ¡Bien hecho!",
                           kb_back_main())
            return

        # Guardar queue en sesión
        TIMER_SESSIONS[chat_id] = {
            "queue":      due_pids[1:],
            "current":    due_pids[0],
            "started_at": datetime.now(TUCSON_TZ),
            "mins":       calc_duration(PLANT_MAP[due_pids[0]], temp_c, season, et),
            "completed":  [],
            "step":       1,
            "total":      len(due_pids),
        }

        pid0  = due_pids[0]
        plant0 = PLANT_MAP[pid0]
        mins0  = calc_duration(plant0, temp_c, season, et)
        total_min = sum(calc_duration(PLANT_MAP[p], temp_c, season, et) for p in due_pids)

        lines = [
            f"▶️ <b>Riego guiado — {len(due_pids)} plantas</b>",
            f"{'━'*22}",
            f"⏱ Tiempo total estimado: ~<b>{total_min} min</b>",
            f"",
        ]
        for i, pid in enumerate(due_pids):
            p    = PLANT_MAP[pid]
            mins = calc_duration(p, temp_c, season, et)
            loc  = "🪣" if p["pot"] else "🌍"
            lines.append(f"  {i+1}. {p['name']} {loc} — {mins} min")

        lines += ["", "<i>El bot te avisa cuándo pasar a la siguiente.</i>"]

        await edit_msg(chat_id, msg_id, "\n".join(lines),
                       kb_timer_start(due_pids))

    # ── Timer: iniciar ─────────────────────────────────────────────────────
    elif data == "timer_start":
        session = TIMER_SESSIONS.get(chat_id)
        if not session:
            await answer_callback(cb_id, "Sesión expirada, vuelve al menú")
            return
        session["started_at"] = datetime.now(TUCSON_TZ)
        pid   = session["current"]
        mins  = session["mins"]
        step  = session["step"]
        total = session["total"]
        txt   = screen_timer_plant(pid, mins, step, total, session["started_at"])
        await edit_msg(chat_id, msg_id, txt, kb_timer_running(pid, step, total))

        # Programar recordatorio automático cuando pase el tiempo
        async def auto_remind(cid, pid_r, mins_r, step_r, total_r):
            await asyncio.sleep(mins_r * 60)
            sess = TIMER_SESSIONS.get(cid)
            if sess and sess.get("current") == pid_r:
                plant_r = PLANT_MAP[pid_r]
                await send_msg(
                    f"⏰ <b>¡Tiempo!</b> {plant_r['name']} — {mins_r} min completados\n\n"
                    f"Toca <b>⏭ Siguiente planta</b> cuando estés listo.",
                    reply_markup=kb_timer_running(pid_r, step_r, total_r),
                    chat_id=cid,
                )
        asyncio.create_task(auto_remind(chat_id, pid, mins, step, total))

    # ── Timer: siguiente planta ────────────────────────────────────────────
    elif data.startswith("timer_next_"):
        pid_done = data[len("timer_next_"):]
        session  = TIMER_SESSIONS.get(chat_id)
        if not session:
            await answer_callback(cb_id, "Sesión expirada")
            return

        session["completed"].append(pid_done)
        await answer_callback(cb_id, f"✅ {PLANT_MAP.get(pid_done,{}).get('name','')} lista")

        if not session["queue"]:
            # Terminamos
            txt = screen_timer_summary(session["completed"], [])
            await edit_msg(chat_id, msg_id, txt, kb_timer_done_confirm())
        else:
            next_pid = session["queue"].pop(0)
            next_mins = calc_duration(PLANT_MAP[next_pid], temp_c, season, et)
            session["current"]    = next_pid
            session["mins"]       = next_mins
            session["step"]      += 1
            session["started_at"] = datetime.now(TUCSON_TZ)
            step  = session["step"]
            total = session["total"]
            txt   = screen_timer_plant(next_pid, next_mins, step, total, session["started_at"])
            await edit_msg(chat_id, msg_id, txt, kb_timer_running(next_pid, step, total))

            # Auto-recordatorio para siguiente planta
            async def auto_remind_next(cid, pid_r, mins_r, step_r, total_r):
                await asyncio.sleep(mins_r * 60)
                sess = TIMER_SESSIONS.get(cid)
                if sess and sess.get("current") == pid_r:
                    plant_r = PLANT_MAP[pid_r]
                    await send_msg(
                        f"⏰ <b>¡Tiempo!</b> {plant_r['name']} — {mins_r} min completados\n\n"
                        f"Toca <b>⏭ Siguiente planta</b> cuando estés listo.",
                        reply_markup=kb_timer_running(pid_r, step_r, total_r),
                        chat_id=cid,
                    )
            asyncio.create_task(auto_remind_next(chat_id, next_pid, next_mins, step, total))

    # ── Timer: terminé todas manualmente ──────────────────────────────────
    elif data == "timer_done":
        session = TIMER_SESSIONS.get(chat_id)
        if not session:
            await answer_callback(cb_id, "Sesión expirada")
            return
        # Marcar current como completada también
        if session.get("current") and session["current"] not in session["completed"]:
            session["completed"].append(session["current"])
        txt = screen_timer_summary(session["completed"], session.get("queue", []))
        await edit_msg(chat_id, msg_id, txt, kb_timer_done_confirm())

    # ── Timer: registrar riegos ────────────────────────────────────────────
    elif data == "timer_confirm_all":
        session = TIMER_SESSIONS.get(chat_id, {})
        pids    = session.get("completed", [])
        if pids:
            newly   = register_watering(state, pids, temp_c, season, et, soil_r, now)
            new_ach = check_achievements(state, meta)
            save_state(state)
            TIMER_SESSIONS.pop(chat_id, None)

            streak   = meta.get("streak", 0)
            total_w  = meta.get("total_waterings", 0)
            level, _ = get_level(total_w)

            voices_txt = ""
            for pid in pids[:3]:
                p     = PLANT_MAP.get(pid)
                if p:
                    voice = random.choice(VOICES.get(pid,{}).get("happy",["¡Gracias!"]))
                    voices_txt += f"\n{p['name']}: <i>\"{voice}\"</i>"

            await edit_msg(chat_id, msg_id,
                f"🎉 <b>¡Jardín regado!</b>\n"
                f"{'━'*22}\n"
                f"{len(pids)} planta(s) registradas."
                + voices_txt +
                f"\n\n{'━'*22}\n"
                f"👤 {level}  ·  💧{total_w}  ·  🔥{streak}d",
                kb_main_menu())
            for ach in new_ach:
                await send_msg(f"🏆 <b>¡LOGRO!</b> {ach['name']}\n{ach['desc']}")
        else:
            await edit_msg(chat_id, msg_id, "No hay riegos que registrar.", kb_main_menu())

    # ── Timer: cancelar ────────────────────────────────────────────────────
    elif data == "timer_cancel":
        TIMER_SESSIONS.pop(chat_id, None)
        await edit_msg(chat_id, msg_id,
                       "❌ <b>Riego cancelado.</b>\n\nVuelve cuando quieras.",
                       kb_main_menu())

# ─── MESSAGE HANDLER ──────────────────────────────────────────────────────────

async def handle_message(update: dict):
    """/start y cualquier mensaje de texto."""
    msg    = update.get("message", {})
    text   = msg.get("text", "").strip()
    chat_id = str(msg.get("chat", {}).get("id", ""))

    if not text.startswith("/start") and not text.startswith("/menu"):
        return  # ignorar texto libre

    wx     = await get_weather()
    state  = load_state()
    meta   = get_meta(state)
    save_state(state)

    await send_msg(screen_main(meta, wx), reply_markup=kb_main_menu(), chat_id=chat_id)

# ─── POLLING LOOP ─────────────────────────────────────────────────────────────

async def poll():
    offset = None
    logging.info("Polling started")
    while True:
        try:
            params = {"timeout": 20, "allowed_updates": ["message", "callback_query"]}
            if offset:
                params["offset"] = offset

            async with httpx.AsyncClient(timeout=30) as cl:
                r    = await cl.get(f"{API}/getUpdates", params=params)
                data = r.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                try:
                    if "callback_query" in update:
                        await handle_callback(update)
                    elif "message" in update:
                        await handle_message(update)
                except Exception as e:
                    logging.error(f"Handler error: {e}")

        except Exception as e:
            logging.warning(f"Poll error: {e}")
            await asyncio.sleep(5)

# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    global VOLUME_OK
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    VOLUME_OK = verify_volume()
    if not VOLUME_OK:
        logging.error("⚠️ /data no disponible. Configura Railway Volume.")

    scheduler = AsyncIOScheduler(timezone=TUCSON_TZ)
    scheduler.add_job(evening_check,  "cron", hour=20, minute=0, id="evening")
    scheduler.add_job(weekly_summary, "cron", day_of_week="sun", hour=9, minute=0, id="weekly")
    scheduler.start()

    vol_icon = "✅" if VOLUME_OK else "⚠️"
    state    = load_state()
    meta     = get_meta(state)
    wx       = await get_weather()
    save_state(state)

    await send_msg(
        f"🌵 <b>Tucson Garden Bot v6 🎮</b>\n"
        f"📍 Tucson, AZ  ·  {len(PLANTS)} plantas  ·  Volume {vol_icon}\n\n"
        f"¡Listo! Usa los botones para navegar.",
        reply_markup=kb_main_menu()
    )

    logging.info(f"🌵 v6 arrancado — {len(PLANTS)} plantas, interfaz de botones")
    await poll()

if __name__ == "__main__":
    asyncio.run(main())
