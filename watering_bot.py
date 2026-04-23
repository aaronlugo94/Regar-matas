"""
🌵 Plant Watering Bot — Tucson AZ Edition v5 🎮
═══════════════════════════════════════════════════════════════
GAMIFICACIÓN COMPLETA:
  • Cada planta tiene personalidad propia y te habla en su voz
  • Sistema de niveles: Jardinero Novato → Maestro del Desierto
  • 20+ logros desbloqueables con notificación instantánea
  • Drama y tensión cuando las plantas están sedientas
  • Celebración épica cuando riegas todo a tiempo
  • Títulos dinámicos según tu desempeño
  • Frases aleatorias por planta, estado climático y temporada
  • Boss fight: semanas de calor extremo con cuenta regresiva
═══════════════════════════════════════════════════════════════
"""

import os, json, random, logging, asyncio, httpx
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ─── CONFIG ───────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID    = os.environ["TELEGRAM_CHAT_ID"]
OPENWEATHER_API_KEY = os.environ["OPENWEATHER_API_KEY"]

TUCSON_TZ  = ZoneInfo("America/Phoenix")
TUCSON_LAT, TUCSON_LON = 32.2226, -110.9747

TUCSON_ETO_REF = {
    1: 2.1, 2: 3.0, 3: 4.5, 4: 6.2, 5: 7.8,
    6: 8.9, 7: 7.2, 8: 6.8, 9: 5.5, 10: 4.1,
    11: 2.6, 12: 1.9,
}

# ─── PLANT PERSONALITIES ──────────────────────────────────────────────────────
# Cada planta tiene:
#   personality   : carácter general
#   voice_happy   : frases cuando está bien hidratada
#   voice_thirsty : frases cuando necesita agua (hoy toca)
#   voice_dying   : frases de drama cuando lleva días atrasada
#   voice_rained  : cuando la lluvia la salvó
#   voice_winter  : en invierno / poco riego

PLANT_VOICES = {
    "cycas_1": {
        "personality": "anciana sabia y dramática",
        "voice_happy": [
            "Llevo millones de años en la Tierra y sigo aquí. Gracias al agua... y a ti. Tal vez.",
            "Mis antepasados vivieron con los dinosaurios. Yo sobreviví Tucson. No es poca cosa.",
            "Estoy en mi mejor momento. No me toques las frondas.",
            "El agua fluyó. La vida continúa. Soy eterna.",
        ],
        "voice_thirsty": [
            "...Oye. Oye tú. Las raíces ya están preguntando por el agua.",
            "Tengo millones de años de historia y me tienes esperando. Qué falta de respeto.",
            "Mis frondas están calculando cuánto tiempo más pueden aguantar. El resultado no te va a gustar.",
            "Soy una cycas. Tengo paciencia infinita. Pero HOY toca el agua. Hoy.",
        ],
        "voice_dying": [
            "🚨 Estoy recurriendo a las reservas de emergencia que guardé desde el Jurásico. Agua. Ya.",
            "Los dinosaurios me fallaron. El clima me ha fallado. Y ahora tú también. Decepcionante.",
            "Mis raíces han enviado un memorándum formal solicitando hidratación inmediata.",
            "He sobrevivido extinciones masivas. Pero esto... esto es NEGLIGENCIA.",
        ],
        "voice_rained": [
            "La lluvia me recuerda tiempos más gloriosos. Gracias, cielo. A ti te lo agradezco.",
            "El monzón llegó. Como siempre ha llegado. Soy antigua. El agua me conoce.",
        ],
        "voice_winter": [
            "El frío me invita a meditar. No necesito agua. Solo silencio y respeto.",
            "Invierno. El tiempo de la contemplación. Deja de molestarme.",
        ],
    },

    "cycas_2": {
        "personality": "filósofa estoica",
        "voice_happy": [
            "El agua llegó. Como el sol llegará mañana. Todo tiene su tiempo.",
            "Hidratada. En paz. Lista para otro ciclo de millones de años.",
            "Mis raíces están satisfechas. Eso es suficiente.",
            "No necesito mucho. Solo lo justo. Y llegó.",
        ],
        "voice_thirsty": [
            "El tiempo sin agua es solo tiempo. Pero... ya va siendo tiempo.",
            "No es urgencia. Es simplemente... necesidad. Pronto, por favor.",
            "El suelo habla. Dice que está seco. Yo solo traduzco el mensaje.",
            "Una pregunta filosófica: ¿puede una cycas sobrevivir la negligencia humana? Esperemos que no tengamos que averiguarlo.",
        ],
        "voice_dying": [
            "🚨 La filosofía tiene límites. Este es uno de ellos. Agua. Ahora.",
            "He aceptado el calor, el viento, la caliche de Tucson. El olvido, no.",
            "Las hojas internas están redistribuyendo la humedad. Es un proceso elegante. Y desesperado.",
        ],
        "voice_rained": [
            "La lluvia es la respuesta que la tierra da cuando nadie pregunta.",
            "El cielo recordó lo que tú a veces olvidas.",
        ],
        "voice_winter": [
            "El frío reduce mis necesidades. Como la meditación reduce las preocupaciones.",
        ],
    },

    "rosal": {
        "personality": "diva exigente y dramática",
        "voice_happy": [
            "Finalmente. Agua. Limpia. Fresca. En la base como debe ser. Eres aprendible.",
            "Mis pétalos están radiantes esta noche. ¿Lo notas? Por supuesto que sí.",
            "Con este riego, mañana abro tres botones nuevos. De nada.",
            "Ah, el agua. El único lenguaje que entiendo antes de las 9 PM.",
        ],
        "voice_thirsty": [
            "Perdón, ¿perdón? ¿Ya viste la hora? MIS RAÍCES LLEVAN ESPERANDO TODO EL DÍA.",
            "Un rosal sin agua es una tragedia. Una tragedia con espinas. Muévete.",
            "No soy un cactus. Repite conmigo: NO SOY UN CACTUS.",
            "El mulch solo hace tanto. El resto te toca a ti. ¿Lo entiendes?",
        ],
        "voice_dying": [
            "🚨 Mis hojas están cerrando poros. Mis botones no van a abrir. Esto ES TU CULPA.",
            "Si yo me seco, tú te quedas sin rosas. Sin fragancia. Sin belleza. ¿Eso quieres?",
            "He mandado señales. Hojas caídas. Tallos tristes. ¿Necesitas que te hable más claro?",
            "🚨 EMERGENCIA FLORAL. Repito: EMERGENCIA FLORAL. Se requiere riego INMEDIATO.",
        ],
        "voice_rained": [
            "La lluvia estuvo bien... pero no llegó a la base. La próxima vez yo lo hago mejor.",
            "¡Llovió! Mis hojas se quedaron secas como deben. Alguien sabe respetar a las rosas.",
        ],
        "voice_winter": [
            "El invierno me da chance de descansar. Igual necesito atención. Soy un rosal, no una piedra.",
        ],
    },

    "toronja": {
        "personality": "mamá nutricia y directa",
        "voice_happy": [
            "Así me gusta. Agua profunda, en el drip line, como enseñé. Buen trabajo.",
            "Mis raíces están contentas. Eso se traduce en fruta. Recuerda eso.",
            "Hidratada. Las flores van a oler increíble esta semana. Ya verás.",
            "El riego llegó a tiempo. Mis frutas lo agradecen. Tus jugos del domingo también.",
        ],
        "voice_thirsty": [
            "Oye, las raíces ya llegaron hasta el límite del drip line buscando humedad. Ayúdame.",
            "Mis hojas están un poco menos brillantes de lo normal. ¿Lo notas? Agua, por favor.",
            "No voy a tirar fruta todavía. Pero si esperas más... no te prometo nada.",
            "Soy paciente. Pero soy una toronja, no un nopal. Necesito agua esta semana.",
        ],
        "voice_dying": [
            "🚨 Estoy priorizando las frutas sobre las ramas. Eso no es buena señal. Agua ya.",
            "Si ves hojas amarillas mañana, ya sabes por qué. Esto es preventable. Ahora.",
            "🚨 Mis frutas están enviando agua a las ramas para sobrevivir. Eso se llama aborto de fruto. No lo queremos.",
        ],
        "voice_rained": [
            "¡Llovió! El monzón hizo su trabajo. Yo hago el mío. Juntos sacamos la cosecha.",
            "La lluvia llegó al drip line perfecto. La naturaleza sabe lo que hace.",
        ],
        "voice_winter": [
            "En invierno descanso. Pero no te olvides de mí completamente. Un riego cada tantos días, ¿sí?",
        ],
    },

    "limon": {
        "personality": "ansioso y perfeccionista",
        "voice_happy": [
            "¡Perfecto! Agua justa, en el sitio correcto, sin encharcamiento. ¡PERFECTO!",
            "Mis raíces están en equilibrio óptimo de humedad. Esto es exactamente lo que pedí.",
            "Sin hojas amarillas. Sin raíces encharcadas. Todo según el plan. Excelente.",
            "El pH del suelo está bien. La humedad está bien. Tú estás bien. Todo está bien. Por ahora.",
        ],
        "voice_thirsty": [
            "Necesito agua. No demasiada. No poca. La cantidad exacta. ¿Entiendes? Exacta.",
            "Mis hojas están monitoreando los niveles de humedad y el reporte no es favorable.",
            "Hay una ventana de riego óptima y se está cerrando. Actúa ahora, por favor.",
            "No es que esté seco-seco. Es que el nivel subóptimo de humedad afecta la calidad del fruto. Detalles.",
        ],
        "voice_dying": [
            "🚨 Estatus: crítico. Protocolo de emergencia activado. Se requiere intervención hídrica INMEDIATA.",
            "Mis hojas están enrollando los bordes para reducir transpiración. Esto es SERIO.",
            "🚨 El encharcamiento me mata. La sequía también. Hay una zona segura y me estás sacando de ella.",
        ],
        "voice_rained": [
            "Llovió 8mm. Calculé el aporte hídrico. Estamos en zona segura. Por ahora.",
            "La lluvia fue... aceptable. El drenaje funcionó. Respiré.",
        ],
        "voice_winter": [
            "Invierno. Menos agua. Yo monitoreo. Tú ejecutas. Seguimos el protocolo.",
        ],
    },

    "mandarina": {
        "personality": "tranquila y generosa",
        "voice_happy": [
            "Gracias. Mis mandarinas van a estar dulces este año. Eso te lo prometo.",
            "El agua llegó. Mis raíces están contentas. Todo bien por aquí.",
            "De todas las plantas del jardín, yo soy la más fácil. Solo no me olvides.",
            "Bien regada. El drip line absorbió todo perfecto. Gracias, en serio.",
        ],
        "voice_thirsty": [
            "Oye, sin presión, pero ya llevan unos días las raíces medio secas...",
            "No soy dramática como el rosal, pero sí necesito agua. Pronto, please.",
            "El Tucson de julio no perdona. Yo soy fuerte, pero tengo mis límites.",
            "Un riego profundo esta noche y mañana seguimos como si nada. ¿Trato?",
        ],
        "voice_dying": [
            "🚨 Ya no estoy siendo tranquila. Necesito agua. Ahora mismo.",
            "Mis mandarinas van a caer si no hay agua pronto. No es chiste.",
            "🚨 Sigo siendo la más amable del jardín pero AGUA. POR. FAVOR.",
        ],
        "voice_rained": [
            "¡Gracias monzón! Este es mi momento favorito del año.",
            "La lluvia cayó justo donde la necesitaba. Magia del desierto.",
        ],
        "voice_winter": [
            "El invierno está bien. Poco riego, mucho descanso. Me parece justo.",
        ],
    },

    "lilly_asiatica": {
        "personality": "nerviosa y muy sensible",
        "voice_happy": [
            "¡Agua! ¡Llegó el agua! ¡Mis pétalos están felices! ¡Todo está bien! ¡Por hoy!",
            "El sustrato está perfecto. Húmedo pero no encharcado. Exactamente correcto. ¡Gracias!",
            "Mis flores van a abrir mañana. ¿Las viste? ¿Las viste bien? Son bonitas, ¿verdad?",
            "Regada a tiempo. Soy feliz. El jardín es hermoso. Tú eres increíble. ¡Buenas noches!",
        ],
        "voice_thirsty": [
            "Oye... oye... el sustrato está un poquito seco... no quiero alarmar a nadie pero...",
            "¿Puedes meter el dedo en la tierra? ¿Dos centímetros? ¿Seco verdad? Necesito agua.",
            "No es que me esté muriendo pero en maceta el sol de Tucson es MUCHO. Agua pronto.",
            "Mis hojas están un poco menos erguidas de lo normal. Es una señal. Una señal de sed.",
        ],
        "voice_dying": [
            "🚨 ¡Estoy doblando las hojas! ¡Esto es una crisis! ¡AGUA AHORA POR FAVOR!",
            "El sustrato está completamente seco. Dos centímetros, tres centímetros, todo seco. 🆘",
            "🚨 Mis flores van a caer si no hay agua esta noche. No en dos días. ESTA NOCHE.",
            "¡La maceta pesa como papel! ¡Eso significa que no hay agua! ¡Es muy fácil de verificar! ¡Hazlo!",
        ],
        "voice_rained": [
            "Llovió pero... ¿llegó a mi maceta? A veces el techo de la terraza... solo digo.",
            "¡Llovió! Aunque en maceta no siempre entra bien. ¿Puedes revisar?",
        ],
        "voice_winter": [
            "Hace frío. Necesito menos agua pero no cero agua. No me abandones en invierno.",
        ],
    },

    "geranio": {
        "personality": "relajado y práctico",
        "voice_happy": [
            "Agua al sustrato, lejos de las flores. Como siempre. Bien hecho.",
            "Estoy bien. Sin dramas. Un poco de agua y sigo floreciendo.",
            "Las flores están sanas. El sustrato tiene humedad. Todo correcto por aquí.",
            "No necesito mucho. Solo constancia. Y tú eres constante. Aprecio eso.",
        ],
        "voice_thirsty": [
            "El sustrato ya está seco un par de centímetros. Ya casi es hora.",
            "Soy relajado pero no soy inmortal. Agua pronto, ¿sí?",
            "Las hojas están un poco caídas. No dramáticamente. Solo... notablemente.",
            "Llevo esperando con paciencia. La paciencia tiene su límite. Este es.",
        ],
        "voice_dying": [
            "🚨 Okay, ya no estoy relajado. El sustrato está seco hasta el fondo. Agua.",
            "Las hojas están colgando. Esto ya no es estilo, es deshidratación.",
            "🚨 Soy el más tranquilo del jardín y te estoy pidiendo agua con urgencia. Eso debería decirte algo.",
        ],
        "voice_rained": [
            "Llovió. Revisé el sustrato. Tiene humedad. Estamos bien.",
            "La lluvia hizo su parte. Apreciado.",
        ],
        "voice_winter": [
            "Invierno fresco. Menos riego. Me parece un trato justo.",
            "Con el frío casi no necesito agua. Solo no me dejes completamente olvidado.",
        ],
    },

    "vinca": {
        "personality": "fiesta y optimista, superviviente orgullosa",
        "voice_happy": [
            "¡Oye! ¡Fui regada! ¡Mis flores de colores están happy! ¡Viva!",
            "Sobreviví el verano de Tucson y sigo floreciendo. Soy una leyenda. Gracias por el agua.",
            "Blanca, rosa, magenta — tengo flores de todos colores. Y ahora tengo agua. La vida es buena.",
            "El sustrato está perfecto. Mañana abro más flores. Cuéntalas si quieres.",
        ],
        "voice_thirsty": [
            "Soy resistente al calor pero no soy roca. Agua pronto, campeón.",
            "Mis flores siguen abiertas pero el sustrato ya se siente seco. Señal.",
            "Tucson + maceta grande + sin agua = problema pronto. Tú lo sabes. Yo lo sé.",
            "¿Ya metiste el dedo al sustrato? Seco, ¿verdad? Eso pensé. Riégame.",
        ],
        "voice_dying": [
            "🚨 Mis flores están cerrando temprano. Eso no es buena señal. AGUA.",
            "La maceta pesa menos que ayer. Y ayer pesaba menos que antes de ayer. Tendencia preocupante.",
            "🚨 Soy la más resistente del jardín y estoy pidiendo ayuda. ¿Qué más quieres saber?",
        ],
        "voice_rained": [
            "¡Llovió y llegó a mi maceta! ¡Hoy es un buen día! ¡Todo es hermoso!",
            "La lluvia del monzón es mi favorita. Agua del cielo. Romance puro.",
        ],
        "voice_winter": [
            "Con el frío me pongo más tranquila. Menos flores, menos agua. Temporada de descanso.",
            "Invierno en Tucson es suave comparado con otros lugares. Pero igual necesito agua, aunque poca.",
        ],
    },
}

# ─── GAMIFICATION ─────────────────────────────────────────────────────────────

# Niveles del jardinero
LEVELS = [
    (0,   "🌱 Jardinero Novato"),
    (10,  "💧 Regador Consistente"),
    (25,  "🌿 Cuidador de Plantas"),
    (50,  "🌻 Guardián del Jardín"),
    (100, "🌵 Veterano del Desierto"),
    (200, "🦅 Maestro del Desierto"),
    (365, "👑 Leyenda de Tucson"),
]

# Logros desbloqueables
ACHIEVEMENTS = [
    {
        "id": "first_water",
        "name": "Primera Gota 💧",
        "desc": "Regaste por primera vez",
        "check": lambda meta, state: meta.get("total_waterings", 0) >= 1,
    },
    {
        "id": "week_streak",
        "name": "Semana Perfecta 🔥",
        "desc": "7 días de racha regando",
        "check": lambda meta, state: meta.get("streak", 0) >= 7,
    },
    {
        "id": "month_streak",
        "name": "Mes de Hierro 💪",
        "desc": "30 días de racha regando",
        "check": lambda meta, state: meta.get("streak", 0) >= 30,
    },
    {
        "id": "hundred_waterings",
        "name": "Centurión del Riego 💯",
        "desc": "100 riegos registrados",
        "check": lambda meta, state: meta.get("total_waterings", 0) >= 100,
    },
    {
        "id": "all_plants_day",
        "name": "Ronda Completa 🎯",
        "desc": "Regaste todas las plantas el mismo día",
        "check": lambda meta, state: meta.get("all_same_day", False),
    },
    {
        "id": "monsoon_master",
        "name": "Maestro del Monzón 🌧️",
        "desc": "Sobreviviste una temporada de monzón completa (Jul-Sep)",
        "check": lambda meta, state: meta.get("monsoon_seasons_survived", 0) >= 1,
    },
    {
        "id": "heat_survivor",
        "name": "Sobreviviente del Infierno 🔥",
        "desc": "Mantuviste el jardín vivo con >40°C registrados",
        "check": lambda meta, state: meta.get("days_over_40c", 0) >= 1,
    },
    {
        "id": "never_skipped",
        "name": "Sin Excusas ✅",
        "desc": "Regaste 14 días consecutivos sin ningún skip",
        "check": lambda meta, state: meta.get("streak_no_skip", 0) >= 14,
    },
    {
        "id": "rain_saver",
        "name": "Ahorrista 🌧️",
        "desc": "La lluvia salvó tus plantas 5 veces",
        "check": lambda meta, state: meta.get("rain_saves", 0) >= 5,
    },
    {
        "id": "early_bird",
        "name": "Madrugador 🌅",
        "desc": "Respondiste /regada antes de las 9 PM por 5 días",
        "check": lambda meta, state: meta.get("early_waterings", 0) >= 5,
    },
    {
        "id": "night_owl",
        "name": "Jardinero Nocturno 🦉",
        "desc": "Regaste después de medianoche 3 veces",
        "check": lambda meta, state: meta.get("midnight_waterings", 0) >= 3,
    },
    {
        "id": "frost_protector",
        "name": "Guardián del Frío ❄️",
        "desc": "Protegiste tus plantas de una helada",
        "check": lambda meta, state: meta.get("frost_alerts_acted", 0) >= 1,
    },
    {
        "id": "fertlizer_pro",
        "name": "Nutricionista Verde 🌿",
        "desc": "Fertilizaste 3 plantas en el mismo mes",
        "check": lambda meta, state: meta.get("fertilizations_this_month", 0) >= 3,
    },
    {
        "id": "comeback",
        "name": "El Gran Regreso 🏆",
        "desc": "Rompiste una racha pero volviste por 7 días",
        "check": lambda meta, state: meta.get("comeback_streak", 0) >= 7,
    },
    {
        "id": "year_garden",
        "name": "Un Año en el Jardín 🎂",
        "desc": "365 días usando el bot",
        "check": lambda meta, state: meta.get("days_using_bot", 0) >= 365,
    },
]

def get_level(total_waterings: int) -> tuple[str, str | None]:
    """Devuelve (nivel_actual, siguiente_nivel_o_None)."""
    current = LEVELS[0][1]
    nxt     = None
    for i, (threshold, name) in enumerate(LEVELS):
        if total_waterings >= threshold:
            current = name
            nxt = LEVELS[i + 1][1] if i + 1 < len(LEVELS) else None
        else:
            break
    return current, nxt

def get_xp_bar(total_waterings: int) -> str:
    """Barra de progreso al siguiente nivel."""
    for i, (threshold, _) in enumerate(LEVELS):
        if i + 1 < len(LEVELS) and total_waterings < LEVELS[i + 1][0]:
            current_floor = threshold
            next_threshold = LEVELS[i + 1][0]
            progress = total_waterings - current_floor
            needed   = next_threshold - current_floor
            pct      = progress / needed
            filled   = int(pct * 10)
            bar      = "█" * filled + "░" * (10 - filled)
            return f"[{bar}] {progress}/{needed} XP"
    return "[██████████] MAX"

def check_achievements(state: dict, meta: dict) -> list[dict]:
    """Devuelve lista de logros recién desbloqueados."""
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

def plant_voice(plant: dict, state: dict, days_overdue: int, rained: bool = False,
                season: str = "spring") -> str:
    pid    = plant["id"]
    voices = PLANT_VOICES.get(pid, {})

    if season == "cool":
        pool = voices.get("voice_winter", voices.get("voice_happy", ["..."]))
    elif rained:
        pool = voices.get("voice_rained", voices.get("voice_happy", ["..."]))
    elif days_overdue <= 0:
        pool = voices.get("voice_thirsty", ["Necesito agua."])
    elif days_overdue <= 1:
        pool = voices.get("voice_dying", ["🚨 Urgente."])[:2]
    else:
        pool = voices.get("voice_dying", ["🚨 ¡Urgente!"])

    return random.choice(pool)

def happy_voice(plant: dict) -> str:
    pid    = plant["id"]
    voices = PLANT_VOICES.get(pid, {})
    pool   = voices.get("voice_happy", ["¡Gracias por el agua!"])
    return random.choice(pool)

# ─── PLANTS ───────────────────────────────────────────────────────────────────

PLANTS = [
    {
        "id": "cycas_1", "name": "Cycas #1 🌴", "location": "tierra",
        "base_days": 14, "heat_factor": 0.60, "monsoon_bonus": 5,
        "cool_factor": 2.0, "pot": False, "pot_diameter_cm": None,
        "drought_tolerance": 3, "fertilize_weeks": 12, "pest_season": [6, 7, 8],
        "watering_profile": {
            "flow_lpm": 4, "duration_min": 8, "heat_extra_min": 4, "cool_less_min": 3,
            "method": "manguera lenta en espiral, tronco → afuera",
            "target": "zona raíces (~50 cm del tronco) — NO mojar frondas",
        },
    },
    {
        "id": "cycas_2", "name": "Cycas #2 🌴", "location": "tierra",
        "base_days": 14, "heat_factor": 0.60, "monsoon_bonus": 5,
        "cool_factor": 2.0, "pot": False, "pot_diameter_cm": None,
        "drought_tolerance": 3, "fertilize_weeks": 12, "pest_season": [6, 7, 8],
        "watering_profile": {
            "flow_lpm": 4, "duration_min": 8, "heat_extra_min": 4, "cool_less_min": 3,
            "method": "manguera lenta en espiral, tronco → afuera",
            "target": "zona raíces (~50 cm del tronco) — NO mojar frondas",
        },
    },
    {
        "id": "rosal", "name": "Rosal 🌹", "location": "tierra",
        "base_days": 4, "heat_factor": 0.50, "monsoon_bonus": 2,
        "cool_factor": 1.6, "pot": False, "pot_diameter_cm": None,
        "drought_tolerance": 1, "fertilize_weeks": 4, "pest_season": [3, 4, 5],
        "watering_profile": {
            "flow_lpm": 3, "duration_min": 6, "heat_extra_min": 3, "cool_less_min": 2,
            "method": "manguera muy suave al ras del suelo, circular",
            "target": "base del tallo — NUNCA hojas ni pétalos",
        },
    },
    {
        "id": "toronja", "name": "Toronja 🍊", "location": "tierra",
        "base_days": 7, "heat_factor": 0.65, "monsoon_bonus": 3,
        "cool_factor": 1.7, "pot": False, "pot_diameter_cm": None,
        "drought_tolerance": 2, "fertilize_weeks": 6, "pest_season": [3, 4, 10, 11],
        "watering_profile": {
            "flow_lpm": 5, "duration_min": 12, "heat_extra_min": 5, "cool_less_min": 4,
            "method": "manguera flujo medio, círculo amplio",
            "target": "drip line (~80 cm del tronco)",
        },
    },
    {
        "id": "limon", "name": "Limón 🍋", "location": "tierra",
        "base_days": 7, "heat_factor": 0.65, "monsoon_bonus": 3,
        "cool_factor": 1.7, "pot": False, "pot_diameter_cm": None,
        "drought_tolerance": 2, "fertilize_weeks": 6, "pest_season": [3, 4, 10, 11],
        "watering_profile": {
            "flow_lpm": 5, "duration_min": 12, "heat_extra_min": 5, "cool_less_min": 4,
            "method": "manguera flujo medio, círculo amplio",
            "target": "drip line (~70 cm del tronco)",
        },
    },
    {
        "id": "mandarina", "name": "Mandarina 🍊", "location": "tierra",
        "base_days": 7, "heat_factor": 0.65, "monsoon_bonus": 3,
        "cool_factor": 1.7, "pot": False, "pot_diameter_cm": None,
        "drought_tolerance": 2, "fertilize_weeks": 6, "pest_season": [3, 4, 10, 11],
        "watering_profile": {
            "flow_lpm": 5, "duration_min": 12, "heat_extra_min": 5, "cool_less_min": 4,
            "method": "manguera flujo medio, círculo amplio",
            "target": "drip line (~75 cm del tronco)",
        },
    },
    {
        "id": "lilly_asiatica", "name": "Lilly Asiática 🌸", "location": "maceta",
        "base_days": 3, "heat_factor": 0.40, "monsoon_bonus": 1,
        "cool_factor": 1.5, "pot": True, "pot_diameter_cm": 25,
        "drought_tolerance": 1, "fertilize_weeks": 3, "pest_season": [4, 5, 9, 10],
        "watering_profile": {
            "flow_lpm": 1, "duration_min": 2, "heat_extra_min": 1, "cool_less_min": 1,
            "method": "regadera o goteo suave, uniforme sobre toda la maceta",
            "target": "sustrato — hasta que escurra por los drenajes",
        },
    },
    {
        "id": "geranio", "name": "Geranio 🌺", "location": "maceta",
        "base_days": 4, "heat_factor": 0.50, "monsoon_bonus": 1,
        "cool_factor": 1.5, "pot": True, "pot_diameter_cm": 20,
        "drought_tolerance": 2, "fertilize_weeks": 4, "pest_season": [4, 5],
        "watering_profile": {
            "flow_lpm": 1, "duration_min": 2, "heat_extra_min": 1, "cool_less_min": 1,
            "method": "regadera suave directo al sustrato",
            "target": "base — NO flores ni hojas",
        },
    },
    {
        "id": "vinca", "name": "Vinca de Madagascar 🌼", "location": "maceta",
        "base_days": 3, "heat_factor": 0.45, "monsoon_bonus": 1,
        "cool_factor": 1.5, "pot": True, "pot_diameter_cm": 45,
        "drought_tolerance": 2, "fertilize_weeks": 4, "pest_season": [4, 5, 9],
        "watering_profile": {
            "flow_lpm": 1, "duration_min": 3, "heat_extra_min": 2, "cool_less_min": 1,
            "method": "regadera suave y uniforme sobre el sustrato",
            "target": "sustrato — hasta drenar por abajo. NO mojar flores",
        },
    },
]

PLANT_MAP = {p["id"]: p for p in PLANTS}

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
        "streak": 0, "streak_no_skip": 0, "comeback_streak": 0,
        "last_streak_date": None, "last_activity": None,
        "total_waterings": 0, "rain_saves": 0, "early_waterings": 0,
        "midnight_waterings": 0, "frost_alerts_acted": 0,
        "fertilizations_this_month": 0, "monsoon_seasons_survived": 0,
        "days_over_40c": 0, "days_using_bot": 0,
        "all_same_day": False, "rain_log": [], "travel_until": None,
        "fertilize_log": {}, "watering_history": [],
        "unlocked_achievements": [], "bot_start_date": date.today().isoformat(),
    })

# ─── RAIN / SEASON / ET ───────────────────────────────────────────────────────

def log_rain(state: dict, mm: float):
    if mm <= 0: return
    meta  = get_meta(state)
    today = date.today().isoformat()
    log   = meta.setdefault("rain_log", [])
    if not any(r["date"] == today for r in log):
        log.append({"date": today, "mm": round(mm, 1)})
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    meta["rain_log"] = [r for r in log if r["date"] >= cutoff]

def recent_rain(state: dict, days: int = 3) -> float:
    meta   = get_meta(state)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return sum(r["mm"] for r in meta.get("rain_log", []) if r["date"] >= cutoff)

def get_season() -> str:
    m = date.today().month
    if m in (7, 8, 9):       return "monsoon"
    if m in (6, 10):         return "hot"
    if m in (11, 12, 1, 2):  return "cool"
    return "spring"

SEASON_LABELS = {
    "monsoon": "🌧️ Monzón", "hot": "🔥 Calor Extremo",
    "cool": "❄️ Invierno",  "spring": "🌱 Primavera",
}

def et_factor(temp_c, humidity, wind_ms) -> float:
    if temp_c is None: return 1.0
    eto_ref  = TUCSON_ETO_REF.get(date.today().month, 5.0)
    hum      = humidity or 25
    vpd      = max(0, 1 - hum/100) * 0.6108 * (2.71828 ** (17.27*temp_c/(temp_c+237.3)))
    eto_now  = vpd * (1 + (wind_ms or 0)*0.04) * 3.5
    return max(0.5, min(1.8, eto_now / eto_ref))

# ─── INTERVALS ────────────────────────────────────────────────────────────────

def pot_adj_interval(d): return 0 if not d else (-1 if d<18 else (0 if d<=35 else (1 if d<=50 else 2)))
def pot_adj_duration(d): return 0 if not d else (-1 if d<18 else (0 if d<=35 else (1 if d<=50 else 2)))

def get_adaptive(state: dict, pid: str) -> float:
    meta    = get_meta(state)
    history = [h for h in meta.get("watering_history", []) if h["pid"] == pid]
    if len(history) < 3: return 1.0
    ratios  = [h["actual"]/h["suggested"] for h in history[-5:] if h["suggested"] > 0]
    return max(0.75, min(1.25, sum(ratios)/len(ratios))) if ratios else 1.0

def calc_interval(plant, temp_c, season, et=1.0, soil_rain=0.0, adaptive=1.0) -> int:
    base = plant["base_days"]
    if season == "cool":      iv = int(base * plant["cool_factor"])
    elif season == "monsoon": iv = base + plant["monsoon_bonus"]
    elif season == "hot":     iv = max(1, int(base * plant["heat_factor"]))
    else:                     iv = base
    if temp_c is not None:
        if temp_c >= 41:    iv = max(1, int(iv * 0.65))
        elif temp_c >= 38:  iv = max(1, int(iv * 0.80))
        elif temp_c <= 8:   iv = int(iv * 1.60)
    iv = max(1, int(iv / et))
    if not plant["pot"] and soil_rain > 0:
        iv += min(base // 2, int(soil_rain / 5))
    if plant["pot"]:
        iv += pot_adj_interval(plant.get("pot_diameter_cm"))
        if season != "cool": iv = max(1, iv - 1)
    return max(1, round(iv * adaptive))

def calc_duration(plant, temp_c, season, et=1.0) -> int:
    wp   = plant["watering_profile"]
    mins = wp["duration_min"]
    if season == "cool":                         mins = max(1, mins - wp["cool_less_min"])
    elif temp_c is not None and temp_c >= 38:    mins += wp["heat_extra_min"]
    if et > 1.4:                                 mins += 1
    if plant["pot"]:                             mins += pot_adj_duration(plant.get("pot_diameter_cm"))
    return max(1, mins)

# ─── WEATHER ──────────────────────────────────────────────────────────────────

async def get_weather() -> dict:
    base_url = (f"https://api.openweathermap.org/data/2.5/weather"
                f"?lat={TUCSON_LAT}&lon={TUCSON_LON}&appid={OPENWEATHER_API_KEY}&units=metric&lang=es")
    fcast_url = (f"https://api.openweathermap.org/data/2.5/forecast"
                 f"?lat={TUCSON_LAT}&lon={TUCSON_LON}&appid={OPENWEATHER_API_KEY}&units=metric&cnt=16")
    icon_map = {"01":"☀️","02":"⛅","03":"🌥️","04":"☁️","09":"🌧️","10":"🌦️","11":"⛈️","13":"🌨️","50":"🌫️"}
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            cr, fr = await asyncio.gather(cl.get(base_url), cl.get(fcast_url))
        c, f = cr.json(), fr.json()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        rain_tom, min_tom = 0.0, 99.0
        for slot in f.get("list", []):
            sd = datetime.fromtimestamp(slot["dt"], tz=TUCSON_TZ).date().isoformat()
            if sd == tomorrow:
                rain_tom += slot.get("rain", {}).get("3h", 0.0)
                min_tom   = min(min_tom, slot["main"]["temp_min"])
        return {
            "ok": True,
            "temp_c": c["main"]["temp"], "feels_like": c["main"]["feels_like"],
            "humidity": c["main"]["humidity"], "wind_ms": c.get("wind", {}).get("speed", 0),
            "rain_mm": c.get("rain", {}).get("3h", 0.0),
            "rain_tomorrow": rain_tom,
            "min_temp_tomorrow": min_tom if min_tom < 99 else None,
            "description": c["weather"][0]["description"].capitalize(),
            "icon": icon_map.get(c["weather"][0]["icon"][:2], "🌡️"),
        }
    except Exception as e:
        logging.warning(f"Weather error: {e}")
        return {"ok": False, "temp_c": None, "rain_mm": 0.0, "rain_tomorrow": 0.0,
                "min_temp_tomorrow": None, "humidity": None, "wind_ms": 0}

# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

async def send_telegram(text: str):
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        async with httpx.AsyncClient(timeout=15) as cl:
            await cl.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "HTML"},
            )
        await asyncio.sleep(0.2)

async def tg(text: str):
    """Alias corto."""
    async with httpx.AsyncClient(timeout=15) as cl:
        await cl.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
        )

# ─── EVENING CHECK ────────────────────────────────────────────────────────────

async def evening_check():
    now    = datetime.now(TUCSON_TZ)
    season = get_season()
    wx     = await get_weather()
    state  = load_state()
    today  = date.today().isoformat()
    meta   = get_meta(state)

    temp_c       = wx.get("temp_c")
    rain_mm      = wx.get("rain_mm", 0.0)
    rain_tomorrow = wx.get("rain_tomorrow", 0.0)
    et           = et_factor(temp_c, wx.get("humidity"), wx.get("wind_ms", 0))

    if rain_mm > 0:
        log_rain(state, rain_mm)

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
    meta["days_using_bot"] = (date.today() - start).days

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
            due.append((plant, interval, mins, 0, False))
            continue

        days_since = (date.today() - date.fromisoformat(last)).days
        skip_until = pstate.get("skip_until", "")
        if skip_until >= today:
            skipped.append((plant, "skip manual"))
            continue

        if days_since >= interval:
            if not plant["pot"] and rain_mm >= 8.0:
                meta["rain_saves"] = meta.get("rain_saves", 0) + 1
                skipped.append((plant, f"💧 lluvia {rain_mm:.0f}mm"))
            else:
                overdue = days_since - interval
                due.append((plant, interval, mins, overdue, False))

    if not due and not skipped:
        logging.info("8 PM: nada por regar.")
        save_state(state)
        return

    # ── Notificación de logros ──
    new_ach = check_achievements(state, meta)
    for ach in new_ach:
        await tg(f"🏆 <b>¡LOGRO DESBLOQUEADO!</b>\n\n"
                 f"<b>{ach['name']}</b>\n{ach['desc']}\n\n"
                 f"<i>Sigue así, jardinero 💪</i>")

    save_state(state)

    # ── Header épico ──
    level, nxt_level = get_level(meta.get("total_waterings", 0))
    streak = meta.get("streak", 0)
    total  = meta.get("total_waterings", 0)

    # Intro dramática según condiciones
    if temp_c and temp_c >= 40:
        intro = f"🔥 <b>{temp_c:.0f}°C en Tucson.</b> Esto es el infierno. Tus plantas lo saben."
    elif rain_mm >= 5:
        intro = f"🌧️ <b>Llovió {rain_mm:.0f} mm hoy.</b> El cielo te ayudó. Tú haz tu parte."
    elif season == "monsoon":
        intro = "⛈️ <b>Temporada de monzón.</b> La humedad engaña. El calor no perdona."
    elif streak >= 7:
        intro = f"🔥 <b>¡{streak} días de racha!</b> Tus plantas lo están notando."
    else:
        intros = [
            "🌙 La noche llegó. Es hora de darles agua.",
            "🌵 Tucson no da tregua. Tu jardín tampoco puede esperar.",
            "💧 El momento del riego ha llegado. Tus plantas están listas.",
            "🌙 Buenas noches. El jardín tiene hambre de agua.",
        ]
        intro = random.choice(intros)

    lines = [
        f"{'━'*25}",
        intro,
        f"{'━'*25}",
        f"",
        f"👤 {level}  |  💧 {total} riegos  |  🔥 {streak}d racha",
    ]

    if wx["ok"]:
        lines.append(f"{wx['icon']} {wx['description']} <b>{temp_c:.1f}°C</b> · {wx['humidity']}% hum")
    if rain_tomorrow >= 5:
        lines.append(f"☔ Mañana: {rain_tomorrow:.0f}mm pronosticados — considera esperar tierra")

    lines += ["", f"🪴 <b>{len(due)} planta(s) esta noche:</b>", ""]

    total_min, total_L = 0, 0.0
    compact = len(due) > 5

    for plant, interval, mins, overdue, _ in due:
        wp     = plant["watering_profile"]
        flow   = wp["flow_lpm"]
        liters = round(flow * mins, 1)
        total_min += mins
        total_L   += liters
        loc = "🪣" if plant["pot"] else "🌍"

        # Voz de la planta
        voice = plant_voice(plant, state, overdue, season=season)

        # Urgency visual
        if overdue <= 0:   urgency = "⏰"
        elif overdue == 1: urgency = "🔶"
        else:              urgency = f"🚨 +{overdue}d"

        if compact:
            lines += [
                f"{plant['name']} {urgency} {loc}",
                f"  <i>\"{voice}\"</i>",
                f"  \u23f1{mins}min \u00b7 \U0001f4a7{flow}L/min \u00b7 ~{liters}L",
                f"  \U0001f3af {wp['target']}",
                "",
            ]
        else:
            lines += [
                f"{'─'*20}",
                f"{plant['name']}  {urgency}  {loc}",
                f"<i>\"{voice}\"</i>",
                f"",
                f"  ⏱ <b>{mins} min</b>  ·  💧 <b>{flow} L/min</b>  →  ~<b>{liters} L</b>",
                f"  🔧 {wp['method']}",
                f"  🎯 {wp['target']}",
                "",
            ]

    lines += [
        f"{'━'*25}",
        f"⏳ Total: <b>~{total_min} min</b>  ·  💧 <b>~{total_L:.0f} L</b>",
    ]

    if nxt_level:
        xp_bar = get_xp_bar(total)
        lines.append(f"⬆️ Progreso → {nxt_level}: {xp_bar}")

    if skipped:
        lines += ["", "⏭️ <b>Saltadas:</b> " + "  ".join(f"{p['name']} ({r})" for p, r in skipped)]

    if rain_tomorrow >= 5:
        lines += ["", f"☔ <i>Si llueve mañana >8mm, las plantas de tierra se salvan solas.</i>"]

    lines += [
        "",
        "<code>/regada todo</code>  <code>/regada [id]</code>  <code>/status</code>",
        "<code>/mañana</code>  <code>/skip [id]</code>  <code>/viaje N</code>  <code>/logros</code>",
    ]

    await tg("\n".join(lines))

    # Frost alert separado
    min_tom = wx.get("min_temp_tomorrow")
    if min_tom and min_tom < 2:
        pots = [p["name"] for p in PLANTS if p["pot"]]
        await tg(
            f"🥶 <b>ALERTA DE HELADA</b>\n\n"
            f"Mañana mínima: <b>{min_tom:.1f}°C</b>\n\n"
            f"⚠️ Mete o cubre:\n" + "\n".join(f"  • {n}" for n in pots)
        )

    logging.info(f"Evening: {len(due)} plantas.")

# ─── WATERING CELEBRATION ─────────────────────────────────────────────────────

async def watering_celebration(state: dict, newly: list[str], now: datetime):
    """Mensaje de celebración después de regar."""
    meta   = get_meta(state)
    total  = meta.get("total_waterings", 0)
    streak = meta.get("streak", 0)
    level, nxt = get_level(total)

    lines = []

    # Celebración por cantidad
    if len(newly) == len(PLANTS):
        celebs = [
            "🎉 <b>¡RONDA COMPLETA!</b> Regaste TODAS las plantas. Eres un profesional.",
            "🏆 <b>¡JARDÍN SATISFECHO!</b> Todas tus plantas te lo agradecen esta noche.",
            "💪 <b>¡TODO REGADO!</b> El jardín de Tucson está en buenas manos.",
        ]
        lines.append(random.choice(celebs))
        meta["all_same_day"] = True
        meta["last_activity"] = today
    else:
        celebs = [
            f"✅ <b>¡Listo!</b> {len(newly)} planta(s) regada(s).",
            f"💧 <b>Hecho.</b> {len(newly)} planta(s) hidratada(s) esta noche.",
        ]
        lines.append(random.choice(celebs))

    # Reacción de cada planta regada
    lines.append("")
    for pid in newly[:4]:  # max 4 para no hacer el mensaje enorme
        plant = PLANT_MAP.get(pid)
        if plant:
            voice = happy_voice(plant)
            lines.append("  " + plant['name'] + ": <i>\"" + voice + "\"</i>")

    if len(newly) > 4:
        lines.append(f"  <i>...y {len(newly)-4} más agradecidas.</i>")

    # Stats
    lines += ["", f"📊 {level}  ·  💧 {total} riegos totales"]
    if streak >= 2:
        lines.append(f"🔥 Racha: <b>{streak} días</b> consecutivos")
    if nxt:
        lines.append(f"⬆️ {get_xp_bar(total)} → {nxt}")

    # Hora tardía
    if now.hour >= 22:
        lines += ["", "🦉 <i>Jardinero nocturno detectado. Tus plantas duermen contentas.</i>"]
    elif now.hour <= 20:
        lines += ["", "⚡ <i>Madrugador del riego. Tus plantas te lo agradecen.</i>"]
        meta["early_waterings"] = meta.get("early_waterings", 0) + 1

    if now.hour >= 0 and now.hour < 4:
        meta["midnight_waterings"] = meta.get("midnight_waterings", 0) + 1

    await tg("\n".join(lines))

# ─── STATUS ───────────────────────────────────────────────────────────────────

async def send_status():
    state  = load_state()
    season = get_season()
    wx     = await get_weather()
    temp_c = wx.get("temp_c")
    et     = et_factor(temp_c, wx.get("humidity"), wx.get("wind_ms", 0))
    soil_r = recent_rain(state, days=3)
    meta   = get_meta(state)
    now    = datetime.now(TUCSON_TZ)
    total  = meta.get("total_waterings", 0)
    streak = meta.get("streak", 0)
    level, nxt = get_level(total)

    lines = [
        f"📊 <b>ESTADO DEL JARDÍN</b>",
        f"📅 {now.strftime('%d %b %Y %H:%M')}  ·  {SEASON_LABELS[season]}",
        f"👤 {level}  ·  💧{total} riegos  ·  🔥{streak}d",
        f"{'━'*25}",
    ]

    for is_pot, label in [(False, "🌍 Tierra"), (True, "🪣 Macetas")]:
        group = [p for p in PLANTS if p["pot"] == is_pot]
        lines.append(f"\n<b>{label}</b>")
        for plant in group:
            pid      = plant["id"]
            last     = state.get(pid, {}).get("last_watered", "nunca")
            adaptive = get_adaptive(state, pid)
            interval = calc_interval(plant, temp_c, season, et, soil_r, adaptive)
            mins     = calc_duration(plant, temp_c, season, et)

            if last != "nunca":
                days_ago = (date.today() - date.fromisoformat(last)).days
                left     = interval - days_ago
                bar      = "🔴" if left<=0 else ("🟡" if left==1 else ("🟢" if left<=3 else "✅"))
                nxt_str  = "HOY" if left<=0 else ("mañana" if left==1 else f"en {left}d")
                lines.append(f"  {bar} {plant['name']}: {nxt_str} · {mins}min/{interval}d")
            else:
                lines.append(f"  ❓ {plant['name']}: sin registro")

    unlocked = len(meta.get("unlocked_achievements", []))
    lines += [
        "",
        f"{'━'*25}",
        f"🏆 Logros: {unlocked}/{len(ACHIEVEMENTS)}",
        f"🌧️ Lluvia reciente: {recent_rain(state, 3):.0f}mm",
    ]
    if nxt:
        lines.append(f"⬆️ {get_xp_bar(total)} → {nxt}")

    await tg("\n".join(lines))

# ─── LOGROS ───────────────────────────────────────────────────────────────────

async def send_logros():
    state   = load_state()
    meta    = get_meta(state)
    total   = meta.get("total_waterings", 0)
    level, _ = get_level(total)
    unlocked = set(meta.get("unlocked_achievements", []))

    lines = [
        f"🏆 <b>LOGROS DEL JARDÍN</b>",
        f"👤 {level}  ·  {len(unlocked)}/{len(ACHIEVEMENTS)} desbloqueados",
        f"{'━'*25}",
    ]

    for ach in ACHIEVEMENTS:
        done = ach["id"] in unlocked
        icon = "✅" if done else "🔒"
        lines.append(f"{icon} <b>{ach['name']}</b>: {ach['desc']}")

    await tg("\n".join(lines))

# ─── MAÑANA ───────────────────────────────────────────────────────────────────

async def send_tomorrow():
    state  = load_state()
    season = get_season()
    wx     = await get_weather()
    temp_c = wx.get("temp_c")
    et     = et_factor(temp_c, wx.get("humidity"), wx.get("wind_ms", 0))
    soil_r = recent_rain(state, days=3)

    due_tomorrow = []
    for plant in PLANTS:
        pid      = plant["id"]
        last     = state.get(pid, {}).get("last_watered")
        adaptive = get_adaptive(state, pid)
        interval = calc_interval(plant, temp_c, season, et, soil_r, adaptive)
        if last:
            days_then = (date.today() - date.fromisoformat(last)).days + 1
            if days_then >= interval:
                due_tomorrow.append(plant)

    if not due_tomorrow:
        await tg("✅ <b>Mañana el jardín descansa.</b> No toca regar ninguna planta. 🎉")
    else:
        names = "\n".join(f"  • {p['name']}" for p in due_tomorrow)
        await tg(f"📅 <b>Vista previa — mañana tocan:</b>\n\n{names}\n\n<i>{len(due_tomorrow)} planta(s)</i>")

# ─── HISTORIAL ────────────────────────────────────────────────────────────────

async def send_historial():
    state  = load_state()
    meta   = get_meta(state)
    now    = datetime.now(TUCSON_TZ)
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    hist   = [h for h in meta.get("watering_history", []) if h.get("date", "") >= cutoff]
    rain30 = sum(r["mm"] for r in meta.get("rain_log", []) if r.get("date", "") >= cutoff)

    lines = [
        "📈 <b>HISTORIAL — últimos 30 días</b>",
        f"{'━'*25}",
    ]

    for plant in PLANTS:
        pid     = plant["id"]
        entries = [h for h in hist if h["pid"] == pid]
        af      = get_adaptive(state, pid)
        last    = state.get(pid, {}).get("last_watered", "—")
        if entries:
            avg_r = sum(e["actual"] for e in entries)/len(entries)
            avg_s = sum(e["suggested"] for e in entries)/len(entries)
            trend = ("📉 riegas antes" if af<0.9 else ("📈 riegas después" if af>1.1 else "✅ en ritmo"))
            lines.append(f"{plant['name']}: {len(entries)}x · real {avg_r:.1f}d / sug {avg_s:.1f}d · {trend}")
        else:
            lines.append(f"{plant['name']}: sin datos · último {last}")

    total  = meta.get("total_waterings", 0)
    streak = meta.get("streak", 0)
    lines += [
        f"{'━'*25}",
        f"💧 Riegos totales: {total}  ·  🔥 Racha: {streak}d",
        f"🌧️ Lluvia 30d: {rain30:.0f}mm",
    ]
    await tg("\n".join(lines))

# ─── WEEKLY SUMMARY ───────────────────────────────────────────────────────────

async def weekly_summary():
    await send_status()
    season = get_season()
    tips = {
        "monsoon": "🌧️ <b>Boss de la semana: El Monzón</b>\nTormentas frecuentes = revisa drenaje de macetas. La humedad engaña — toca el sustrato antes de regar.",
        "hot":     "🔥 <b>Boss de la semana: El Calor Extremo</b>\nMultiplica tu riego. Mulch en cítricos y rosal. Las macetas pueden necesitar agua DIARIA esta semana.",
        "cool":    "❄️ <b>Temporada de descanso</b>\nCycas en modo meditación. Cítricos con mínimo riego. Protege vinca y geranio si el pronóstico baja de 5°C.",
        "spring":  "🌱 <b>¡Temporada de crecimiento!</b>\nFertiliza cítricos ahora. Poda el rosal post-floración. Revisa pulgón en brotes nuevos.",
    }
    if season in tips:
        await tg(tips[season])

# ─── COMMAND POLLING ──────────────────────────────────────────────────────────

async def poll_commands():
    url_base = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    offset   = None
    all_ids  = {p["id"] for p in PLANTS}

    while True:
        try:
            params = {"timeout": 20, "allowed_updates": ["message"]}
            if offset: params["offset"] = offset

            async with httpx.AsyncClient(timeout=30) as cl:
                data = (await cl.get(f"{url_base}/getUpdates", params=params)).json()

            for update in data.get("result", []):
                offset  = update["update_id"] + 1
                msg     = update.get("message", {})
                raw     = msg.get("text", "").strip()
                text    = raw.lower()
                parts   = text.split()
                cmd     = parts[0].lstrip("/") if parts else ""
                arg     = parts[1] if len(parts) > 1 else ""
                now     = datetime.now(TUCSON_TZ)

                # /regada
                if cmd == "regada":
                    state   = load_state()
                    meta    = get_meta(state)
                    today   = date.today().isoformat()
                    season  = get_season()
                    wx      = await get_weather()
                    temp_c  = wx.get("temp_c")
                    et      = et_factor(temp_c, wx.get("humidity"), wx.get("wind_ms", 0))
                    soil_r  = recent_rain(state, days=3)
                    targets = list(all_ids) if (not arg or arg == "todo") else [arg]
                    marked  = [pid for pid in targets if pid in all_ids]
                    newly, already = [], []

                    for pid in marked:
                        plant    = PLANT_MAP[pid]
                        adaptive = get_adaptive(state, pid)
                        interval = calc_interval(plant, temp_c, season, et, soil_r, adaptive)
                        pstate   = state.setdefault(pid, {})
                        last     = pstate.get("last_watered")
                        if last == today:
                            already.append(pid)
                        else:
                            if last:
                                actual = (date.today() - date.fromisoformat(last)).days
                                meta.setdefault("watering_history", []).append({
                                    "date": today, "pid": pid,
                                    "suggested": interval, "actual": actual,
                                })
                            pstate["last_watered"] = today
                            pstate.pop("skip_until", None)
                            newly.append(pid)

                    if newly:
                        meta["total_waterings"] = meta.get("total_waterings", 0) + len(newly)
                        meta["last_activity"]   = today

                        # Reset fertilizations counter if new month
                        last_fert_month = meta.get("fert_reset_month")
                        if last_fert_month != date.today().month:
                            meta["fertilizations_this_month"] = 0
                            meta["fert_reset_month"] = date.today().month

                        # Prune watering_history — keep last 90 entries only
                        hist = meta.get("watering_history", [])
                        if len(hist) > 90:
                            meta["watering_history"] = hist[-90:]

                        # Streak
                        last_s = meta.get("last_streak_date")
                        yesterday = (date.today() - timedelta(days=1)).isoformat()
                        if last_s == yesterday:
                            meta["streak"] = meta.get("streak", 0) + 1
                            meta["streak_no_skip"] = meta.get("streak_no_skip", 0) + 1
                        elif last_s != today:
                            if meta.get("streak", 0) > 0:
                                meta["comeback_streak"] = 0  # broke streak, reset comeback
                            meta["streak"] = 1
                            meta["streak_no_skip"] = 1
                            meta["comeback_streak"] = meta.get("comeback_streak", 0) + 1
                        meta["last_streak_date"] = today

                    new_ach = check_achievements(state, meta)
                    save_state(state)

                    if not marked:
                        await tg(f"❓ ID no reconocido: <code>{arg}</code>\nIDs: {' · '.join(sorted(all_ids))}")
                        continue

                    if newly:
                        await watering_celebration(state, newly, now)
                    if already:
                        await tg(f"ℹ️ Ya regadas hoy: {', '.join(already)}")

                    for ach in new_ach:
                        await tg(f"🏆 <b>¡LOGRO!</b> {ach['name']}\n{ach['desc']}")

                elif cmd == "skip":
                    if arg in all_ids:
                        state = load_state()
                        state.setdefault(arg, {})["skip_until"] = (date.today() + timedelta(days=1)).isoformat()
                        save_state(state)
                        plant = PLANT_MAP[arg]
                        _skip_voice = random.choice(PLANT_VOICES.get(arg, {}).get("voice_happy", ["Ok."]))
                        await tg(f"⏭️ <b>{plant['name']}</b> descansa mañana.\n<i>\"" + _skip_voice + "\"</i>")
                    else:
                        await tg(f"❓ ID no reconocido: <code>{arg}</code>")

                elif cmd == "forzar":
                    if arg in all_ids:
                        state = load_state()
                        state.setdefault(arg, {}).pop("last_watered", None)
                        state[arg].pop("skip_until", None)
                        save_state(state)
                        await tg(f"🔄 <b>{PLANT_MAP[arg]['name']}</b> reseteada — aparecerá esta noche.")
                    else:
                        await tg(f"❓ ID no reconocido: <code>{arg}</code>")

                elif cmd == "status":
                    await send_status()

                elif cmd in ("mañana", "manana", "tomorrow"):
                    await send_tomorrow()

                elif cmd == "historial":
                    await send_historial()

                elif cmd == "logros":
                    await send_logros()

                elif cmd == "viaje":
                    try:
                        days  = int(arg)
                        state = load_state()
                        meta  = get_meta(state)
                        until = (date.today() + timedelta(days=days)).isoformat()
                        meta["travel_until"] = until

                        season = get_season()
                        wx     = await get_weather()
                        temp_c = wx.get("temp_c")
                        et     = et_factor(temp_c, wx.get("humidity"), wx.get("wind_ms", 0))
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

                        msg = (f"✈️ <b>Modo viaje: {days} días</b>\n"
                               f"Pausado hasta <b>{until}</b>\n\n")
                        if stressed:
                            msg += "🚨 <b>Plantas en riesgo al regresar:</b>\n"
                            msg += "\n".join(f"  • {n}: +{d}d atrasada" for n,d in stressed)
                            msg += "\n\n💡 Consigue a alguien que las riegue o riega bien antes de salir."
                        else:
                            msg += "✅ Todas aguantarán sin problemas. ¡Buen viaje!"
                        await tg(msg)
                    except (ValueError, IndexError):
                        await tg("❓ Uso: <code>/viaje 5</code>")

                elif cmd == "viaje_off":
                    state = load_state()
                    get_meta(state).pop("travel_until", None)
                    save_state(state)
                    await tg("🏠 <b>¡De regreso!</b> Notificaciones reactivadas.\nUsa <code>/status</code> para ver cómo están tus plantas.")

                elif cmd == "fertilizar":
                    if arg in all_ids:
                        state = load_state()
                        meta  = get_meta(state)
                        meta.setdefault("fertilize_log", {})[arg] = date.today().isoformat()
                        meta["fertilizations_this_month"] = meta.get("fertilizations_this_month", 0) + 1
                        plant = PLANT_MAP[arg]
                        save_state(state)
                        _fert_voice = happy_voice(plant)
                        await tg(f"🌿 <b>{plant['name']}</b> fertilizada.\n<i>\"" + _fert_voice + "\"</i>")
                    else:
                        await tg(f"❓ ID no reconocido: <code>{arg}</code>")

                elif cmd in ("ayuda", "help", "start"):
                    await tg(
                        "🪴 <b>Plant Watering Bot v5 🎮</b>\n\n"
                        "<b>Riego:</b>\n"
                        "  <code>/regada todo</code> — todas regadas\n"
                        "  <code>/regada [id]</code> — una específica\n"
                        "  <code>/skip [id]</code> — saltar mañana\n"
                        "  <code>/forzar [id]</code> — resetear\n\n"
                        "<b>Info:</b>\n"
                        "  <code>/status</code> — estado del jardín\n"
                        "  <code>/mañana</code> — preview de mañana\n"
                        "  <code>/historial</code> — estadísticas del mes\n"
                        "  <code>/logros</code> — tus logros 🏆\n\n"
                        "<b>Viaje:</b>\n"
                        "  <code>/viaje 5</code> — pausar N días\n"
                        "  <code>/viaje_off</code> — cancelar viaje\n\n"
                        "<b>Cuidado:</b>\n"
                        "  <code>/fertilizar [id]</code> — registrar fertilización\n\n"
                        "<b>IDs:</b>\n" +
                        "  " + "  ".join(f"<code>{p['id']}</code>" for p in PLANTS)
                    )

        except Exception as e:
            logging.warning(f"Poll error: {e}")
            await asyncio.sleep(5)

# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    global VOLUME_OK
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    VOLUME_OK = verify_volume()
    if not VOLUME_OK:
        logging.error("⚠️ /data no disponible. Configura Railway Volume.")

    scheduler = AsyncIOScheduler(timezone=TUCSON_TZ)
    scheduler.add_job(evening_check,  "cron", hour=20, minute=0,  id="evening")
    scheduler.add_job(weekly_summary, "cron", day_of_week="sun", hour=9, minute=0, id="weekly")
    scheduler.start()

    level, _ = get_level(0)
    vol_icon  = "✅" if VOLUME_OK else "⚠️"

    await tg(
        f"🌵 <b>Plant Watering Bot v5 🎮</b>\n"
        f"📍 Tucson, AZ  ·  {len(PLANTS)} plantas\n"
        f"💾 Volume {vol_icon}  ·  ⏰ 8 PM diario\n\n"
        f"<b>¡El jardín está listo para jugar!</b>\n"
        f"Empieza con <code>/status</code> o espera las 8 PM 🌙\n\n"
        f"<code>/ayuda</code> para ver todos los comandos"
    )

    logging.info(f"🌵 v5 arrancado — {len(PLANTS)} plantas, {len(ACHIEVEMENTS)} logros")
    await poll_commands()

if __name__ == "__main__":
    asyncio.run(main())
