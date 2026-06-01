"""
🌵 Tucson Garden Bot v7
════════════════════════════════════════════
UX rediseñada desde cero:
  • Home = plantas de hoy, directo, sin pasos extra
  • Botón ✅ por planta en la lista — sin entrar al detalle
  • Después de regar → se actualiza la misma pantalla, no regresa
  • Detalle de planta accesible pero opcional
  • Monstera agregada (interior → transición exterior)
  • Macetas: intervalo base 4 días (no 3)
  • Navbar fija en todas las pantallas: Hoy | Jardín | ▶️ | Stats
════════════════════════════════════════════
"""

import os, json, random, logging, asyncio, httpx
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ─── CONFIG ───────────────────────────────────────────────────────────────────

TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
OWM_KEY = os.environ["OPENWEATHER_API_KEY"]
API     = f"https://api.telegram.org/bot{TOKEN}"

TUCSON_TZ  = ZoneInfo("America/Phoenix")
TUCSON_LAT = 32.2226
TUCSON_LON = -110.9747

TUCSON_ETO_REF = {
    1:2.1, 2:3.0, 3:4.5, 4:6.2, 5:7.8,
    6:8.9, 7:7.2, 8:6.8, 9:5.5, 10:4.1,
    11:2.6, 12:1.9,
}

# ─── VOICES ───────────────────────────────────────────────────────────────────

VOICES = {
    "cycas_1": {
        "happy":   ["Llevo millones de años en la Tierra y sigo aquí. Gracias al agua.",
                    "Mis antepasados vivieron con los dinosaurios. Yo sobreviví Tucson.",
                    "Estoy en mi mejor momento. No me toques las frondas.",
                    "El agua fluyó. La vida continúa. Soy eterna."],
        "thirsty": ["...Oye. Las raíces ya preguntan por el agua.",
                    "Tengo millones de años de historia y me tienes esperando.",
                    "Soy una cycas. Tengo paciencia infinita. Pero HOY toca. Hoy."],
        "dying":   ["🚨 Estoy usando reservas del Jurásico. Agua. Ya.",
                    "Los dinosaurios me fallaron. Tú también. Decepcionante.",
                    "He sobrevivido extinciones masivas. Pero esto es NEGLIGENCIA."],
        "rained":  ["La lluvia me recuerda tiempos más gloriosos.",
                    "El monzón llegó. Soy antigua. El agua me conoce."],
        "winter":  ["El frío me invita a meditar. Solo silencio y respeto.",
                    "Invierno. Tiempo de contemplación. Deja de molestarme."],
    },
    "cycas_2": {
        "happy":   ["El agua llegó. Como el sol llegará mañana. Todo tiene su tiempo.",
                    "Hidratada. En paz. Lista para otro ciclo de millones de años.",
                    "No necesito mucho. Solo lo justo. Y llegó."],
        "thirsty": ["El suelo habla. Dice que está seco. Yo solo traduzco.",
                    "No es urgencia. Es necesidad. Pronto, por favor.",
                    "¿Puede una cycas sobrevivir la negligencia? Esperemos no averiguarlo."],
        "dying":   ["🚨 La filosofía tiene límites. Agua. Ahora.",
                    "He aceptado el calor, el viento, la caliche. El olvido, no.",
                    "Las hojas internas redistribuyen humedad. Elegante. Y desesperado."],
        "rained":  ["La lluvia es la respuesta que la tierra da cuando nadie pregunta."],
        "winter":  ["El frío reduce mis necesidades. Como la meditación las preocupaciones."],
    },
    "rosal": {
        "happy":   ["Finalmente. Agua en la base. Eres aprendible.",
                    "Mis pétalos están radiantes. ¿Lo notas? Por supuesto.",
                    "Con este riego mañana abro tres botones nuevos. De nada.",
                    "El agua. El único lenguaje que entiendo antes de las 9 PM."],
        "thirsty": ["MIS RAÍCES LLEVAN ESPERANDO TODO EL DÍA.",
                    "Un rosal sin agua es una tragedia. Con espinas. Muévete.",
                    "No soy un cactus. Repite: NO SOY UN CACTUS.",
                    "El mulch solo hace tanto. El resto te toca a ti."],
        "dying":   ["🚨 Mis botones no van a abrir. Esto ES TU CULPA.",
                    "Sin rosas, sin fragancia, sin belleza. ¿Eso quieres?",
                    "🚨 EMERGENCIA FLORAL. Riego INMEDIATO."],
        "rained":  ["¡Llovió! Mis hojas se quedaron secas. Alguien respeta a las rosas."],
        "winter":  ["El invierno me da descanso. Igual necesito atención. Soy un rosal."],
    },
    "toronja": {
        "happy":   ["Agua profunda en el drip line. Buen trabajo.",
                    "Mis raíces están contentas. Eso se traduce en fruta.",
                    "Tus jugos del domingo te lo van a agradecer."],
        "thirsty": ["Las raíces llegaron al límite buscando humedad. Ayúdame.",
                    "No voy a tirar fruta todavía. Pero si esperas más... no prometo nada.",
                    "Soy paciente. Pero no soy un nopal."],
        "dying":   ["🚨 Priorizando frutas sobre ramas. No es buena señal.",
                    "🚨 Aborto de fruto en progreso. Agua ya."],
        "rained":  ["¡Llovió! El monzón hizo su trabajo. Yo hago el mío."],
        "winter":  ["En invierno descanso. Pero no me olvides completamente."],
    },
    "limon": {
        "happy":   ["Agua justa, sitio correcto, sin encharcamiento. ¡PERFECTO!",
                    "Raíces en equilibrio óptimo. Exactamente lo que pedí.",
                    "Sin hojas amarillas. Sin encharcamiento. Todo según el plan."],
        "thirsty": ["Necesito agua. No demasiada. No poca. La cantidad EXACTA.",
                    "Hay una ventana de riego óptima y se está cerrando.",
                    "El nivel subóptimo afecta la calidad del fruto. Detalles."],
        "dying":   ["🚨 Estatus crítico. Protocolo de emergencia activado.",
                    "🚨 Me están sacando de la zona segura de humedad."],
        "rained":  ["Llovió. Calculé el aporte. Estamos en zona segura. Por ahora."],
        "winter":  ["Invierno. Menos agua. Yo monitoreo. Tú ejecutas."],
    },
    "mandarina": {
        "happy":   ["Gracias. Mis mandarinas van a estar dulces. Te lo prometo.",
                    "El agua llegó. Todo bien por aquí.",
                    "De todas las plantas, yo soy la más fácil. Solo no me olvides."],
        "thirsty": ["Sin presión, pero ya llevan unos días las raíces medio secas...",
                    "No soy dramática como el rosal. Pero sí necesito agua.",
                    "Un riego profundo y mañana seguimos como si nada. ¿Trato?"],
        "dying":   ["🚨 Ya no estoy siendo tranquila. AGUA. AHORA.",
                    "🚨 Mis mandarinas van a caer. No es chiste."],
        "rained":  ["¡Gracias monzón! Este es mi momento favorito del año."],
        "winter":  ["Poco riego, mucho descanso. Me parece justo."],
    },
    "lilly_asiatica": {
        "happy":   ["¡Agua! ¡Todo está bien! ¡Por hoy!",
                    "Sustrato perfecto. Húmedo pero no encharcado. ¡Gracias!",
                    "Mis flores van a abrir mañana. ¡Buenas noches!"],
        "thirsty": ["El sustrato está un poquito seco... no quiero alarmar pero...",
                    "En maceta el sol de Tucson es MUCHO. Agua pronto.",
                    "Mis hojas están menos erguidas. Es una señal."],
        "dying":   ["🚨 ¡Estoy doblando las hojas! ¡AGUA AHORA!",
                    "🚨 Mis flores van a caer ESTA NOCHE si no hay agua.",
                    "¡La maceta pesa como papel! ¡Sin agua!"],
        "rained":  ["¡Llovió! Aunque en maceta no siempre entra bien. ¿Puedes revisar?"],
        "winter":  ["Hace frío. Necesito menos agua pero no cero. No me abandones."],
    },
    "geranio": {
        "happy":   ["Agua al sustrato, lejos de las flores. Bien hecho.",
                    "Sin dramas. Un poco de agua y sigo floreciendo.",
                    "No necesito mucho. Solo constancia."],
        "thirsty": ["El sustrato ya está seco. Casi es hora.",
                    "Soy relajado pero no soy inmortal. Agua pronto.",
                    "Las hojas están un poco caídas. Notablemente."],
        "dying":   ["🚨 Sustrato seco hasta el fondo. Agua.",
                    "🚨 Soy el más tranquilo y te pido agua con urgencia. Eso dice algo."],
        "rained":  ["Llovió. Revisé el sustrato. Estamos bien."],
        "winter":  ["Con el frío casi no necesito agua. Solo no me dejes olvidado."],
    },
    "vinca": {
        "happy":   ["¡Mis flores de colores están happy! ¡Viva!",
                    "Sobreviví el verano de Tucson. Soy una leyenda.",
                    "Blanca, rosa, magenta. Agua. La vida es buena."],
        "thirsty": ["Soy resistente al calor pero no soy roca. Agua pronto.",
                    "Tucson + maceta + sin agua = problema. Tú lo sabes.",
                    "Presiona el sustrato. Seco, ¿verdad? Riégame."],
        "dying":   ["🚨 Mis flores están cerrando temprano. AGUA.",
                    "🚨 Soy la más resistente y estoy pidiendo ayuda. ¿Qué más?"],
        "rained":  ["¡Llovió y llegó a mi maceta! ¡Todo es hermoso!"],
        "winter":  ["Con el frío me pongo tranquila. Menos flores, menos agua."],
    },
    "monstera": {
        "happy":   ["Mis hojas fenestradas están brillando. Eso es hidratación.",
                    "El agua llegó. Las nuevas hojas van a abrir bien. Gracias.",
                    "Con buena luz y agua regular, voy a conquistar ese rincón del patio.",
                    "Feliz y bien regada. Mis raíces lo agradecen."],
        "thirsty": ["El sustrato está seco más de la mitad. Ya es hora.",
                    "Mis hojas empiezan a perder turgencia. Señal clara.",
                    "No soy dramática. Pero sí necesito agua antes de que empiece a marcharme.",
                    "Dame agua y en dos semanas te saco una hoja nueva. Trato."],
        "dying":   ["🚨 Mis hojas se están enrollando para conservar agua. Urgente.",
                    "🚨 Sin agua pronto voy a sacrificar las hojas más viejas.",
                    "🚨 Vine de adentro, soy nueva aquí. No me abandones ya."],
        "rained":  ["La lluvia llegó. Mis raíces la sintieron. Gracias, cielo."],
        "winter":  ["En invierno crezco más despacio. Menos agua, más paciencia."],
    },
}

# ─── PLANTS ───────────────────────────────────────────────────────────────────

PLANTS = [
    # ── TIERRA ────────────────────────────────────────────────────────────────
    {"id":"cycas_1", "name":"Cycas #1 🌴", "location":"tierra",
     "base_days":14, "heat_factor":0.60, "monsoon_bonus":5, "cool_factor":2.0,
     "pot":False, "pot_diameter_cm":None, "drought_tolerance":3,
     "fertilize_weeks":12, "pest_season":[6,7,8],
     "watering_profile":{"flow_lpm":2.5,"duration_min":8,"heat_extra_min":4,"cool_less_min":3,
                         "method":"Manguera lenta en espiral, tronco → afuera",
                         "target":"Zona raíces ~50 cm del tronco — NO mojar frondas"}},

    {"id":"cycas_2", "name":"Cycas #2 🌴", "location":"tierra",
     "base_days":14, "heat_factor":0.60, "monsoon_bonus":5, "cool_factor":2.0,
     "pot":False, "pot_diameter_cm":None, "drought_tolerance":3,
     "fertilize_weeks":12, "pest_season":[6,7,8],
     "watering_profile":{"flow_lpm":2.5,"duration_min":8,"heat_extra_min":4,"cool_less_min":3,
                         "method":"Manguera lenta en espiral, tronco → afuera",
                         "target":"Zona raíces ~50 cm del tronco — NO mojar frondas"}},

    {"id":"rosal", "name":"Rosal 🌹", "location":"tierra",
     "base_days":4, "heat_factor":0.50, "monsoon_bonus":2, "cool_factor":1.6,
     "pot":False, "pot_diameter_cm":None, "drought_tolerance":1,
     "fertilize_weeks":4, "pest_season":[3,4,5],
     "watering_profile":{"flow_lpm":2.5,"duration_min":6,"heat_extra_min":3,"cool_less_min":2,
                         "method":"Manguera muy suave al ras del suelo, circular",
                         "target":"Base del tallo — NUNCA hojas ni pétalos"}},

    {"id":"toronja", "name":"Toronja 🍊", "location":"tierra",
     "base_days":7, "heat_factor":0.65, "monsoon_bonus":3, "cool_factor":1.7,
     "pot":False, "pot_diameter_cm":None, "drought_tolerance":2,
     "fertilize_weeks":6, "pest_season":[3,4,10,11],
     "watering_profile":{"flow_lpm":2.5,"duration_min":10,"heat_extra_min":4,"cool_less_min":3,
                         "method":"Manguera flujo medio, círculo amplio",
                         "target":"Drip line ~80 cm del tronco"}},

    {"id":"limon", "name":"Limón 🍋", "location":"tierra",
     "base_days":7, "heat_factor":0.65, "monsoon_bonus":3, "cool_factor":1.7,
     "pot":False, "pot_diameter_cm":None, "drought_tolerance":2,
     "fertilize_weeks":6, "pest_season":[3,4,10,11],
     "watering_profile":{"flow_lpm":2.5,"duration_min":10,"heat_extra_min":4,"cool_less_min":3,
                         "method":"Manguera flujo medio, círculo amplio",
                         "target":"Drip line ~70 cm del tronco"}},

    {"id":"mandarina", "name":"Mandarina 🍊", "location":"tierra",
     "base_days":7, "heat_factor":0.65, "monsoon_bonus":3, "cool_factor":1.7,
     "pot":False, "pot_diameter_cm":None, "drought_tolerance":2,
     "fertilize_weeks":6, "pest_season":[3,4,10,11],
     "watering_profile":{"flow_lpm":2.5,"duration_min":10,"heat_extra_min":4,"cool_less_min":3,
                         "method":"Manguera flujo medio, círculo amplio",
                         "target":"Drip line ~75 cm del tronco"}},

    # ── MACETAS ───────────────────────────────────────────────────────────────
    # base_days=4 para todas (sustrato dura 3-4 días húmedo en Tucson)
    {"id":"lilly_asiatica", "name":"Lilly Asiática 🌸", "location":"maceta",
     "base_days":4, "heat_factor":0.65, "monsoon_bonus":1, "cool_factor":1.5,
     "pot":True, "pot_diameter_cm":25, "drought_tolerance":1,
     "fertilize_weeks":3, "pest_season":[4,5,9,10],
     "watering_profile":{"flow_lpm":0.8,"duration_min":3,"heat_extra_min":1,"cool_less_min":1,
                         "method":"Regadera o goteo muy suave, uniforme",
                         "target":"Sustrato — hasta que escurra por los drenajes"}},

    {"id":"geranio", "name":"Geranio 🌺", "location":"maceta",
     "base_days":4, "heat_factor":0.65, "monsoon_bonus":1, "cool_factor":1.5,
     "pot":True, "pot_diameter_cm":20, "drought_tolerance":2,
     "fertilize_weeks":4, "pest_season":[4,5],
     "watering_profile":{"flow_lpm":0.8,"duration_min":2,"heat_extra_min":1,"cool_less_min":1,
                         "method":"Regadera suave directo al sustrato",
                         "target":"Base — NO flores ni hojas"}},

    {"id":"vinca", "name":"Vinca 🌼", "location":"maceta",
     "base_days":4, "heat_factor":0.65, "monsoon_bonus":1, "cool_factor":1.5,
     "pot":True, "pot_diameter_cm":45, "drought_tolerance":2,
     "fertilize_weeks":4, "pest_season":[4,5,9],
     "watering_profile":{"flow_lpm":0.8,"duration_min":5,"heat_extra_min":2,"cool_less_min":1,
                         "method":"Regadera suave y uniforme sobre el sustrato",
                         "target":"Sustrato — hasta drenar. NO mojar flores"}},

    # Monstera: recién salida del interior, en transición a exterior con sombra
    {"id":"monstera", "name":"Monstera 🌿", "location":"maceta",
     "base_days":5, "heat_factor":0.70, "monsoon_bonus":2, "cool_factor":1.8,
     "pot":True, "pot_diameter_cm":30, "drought_tolerance":2,
     "fertilize_weeks":6, "pest_season":[4,5,9,10],
     "watering_profile":{"flow_lpm":0.8,"duration_min":4,"heat_extra_min":2,"cool_less_min":2,
                         "method":"Regadera suave y uniforme, saturar bien el sustrato",
                         "target":"Sustrato completo — esperar que drene antes de tapar plato"},
     "note":"⚠️ Recién salida del interior. Mantener en sombra indirecta. "
            "Sin sol directo de Tucson todavía — la quema. Sustrato debe secarse entre riegos."},
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
    {"id":"first_water",       "name":"Primera Gota 💧",       "desc":"Regaste por primera vez",
     "check": lambda m,s: m.get("total_waterings",0)>=1},
    {"id":"week_streak",       "name":"Semana Perfecta 🔥",    "desc":"7 días de racha",
     "check": lambda m,s: m.get("streak",0)>=7},
    {"id":"month_streak",      "name":"Mes de Hierro 💪",      "desc":"30 días de racha",
     "check": lambda m,s: m.get("streak",0)>=30},
    {"id":"hundred_waterings", "name":"Centurión 💯",          "desc":"100 riegos totales",
     "check": lambda m,s: m.get("total_waterings",0)>=100},
    {"id":"all_plants_day",    "name":"Ronda Completa 🎯",     "desc":"Todas las plantas en un día",
     "check": lambda m,s: m.get("all_same_day",False)},
    {"id":"heat_survivor",     "name":"Sobreviviente del Infierno 🌡️","desc":"Jardín vivo con >40°C",
     "check": lambda m,s: m.get("days_over_40c",0)>=1},
    {"id":"rain_saver",        "name":"Ahorrista 🌧️",         "desc":"La lluvia salvó las plantas 5 veces",
     "check": lambda m,s: m.get("rain_saves",0)>=5},
    {"id":"night_owl",         "name":"Jardinero Nocturno 🦉", "desc":"Regaste después de medianoche 3 veces",
     "check": lambda m,s: m.get("midnight_waterings",0)>=3},
    {"id":"fertilizer_pro",    "name":"Nutricionista 🌿",      "desc":"Fertilizaste 3 plantas en un mes",
     "check": lambda m,s: m.get("fertilizations_this_month",0)>=3},
    {"id":"comeback",          "name":"El Gran Regreso 🏆",    "desc":"7 días seguidos tras romper racha",
     "check": lambda m,s: m.get("comeback_streak",0)>=7},
    {"id":"monstera_saved",    "name":"Rescatista 🆘",         "desc":"Salvaste la Monstera del interior",
     "check": lambda m,s: s.get("monstera",{}).get("last_watered") is not None},
    {"id":"year_garden",       "name":"Un Año en el Jardín 🎂","desc":"365 días usando el bot",
     "check": lambda m,s: m.get("days_using_bot",0)>=365},
]

def get_level(total:int)->tuple:
    cur,nxt = LEVELS[0][1],None
    for i,(thr,name) in enumerate(LEVELS):
        if total>=thr: cur,nxt=name,(LEVELS[i+1][1] if i+1<len(LEVELS) else None)
        else: break
    return cur,nxt

def xp_bar(total:int)->str:
    for i,(thr,_) in enumerate(LEVELS):
        if i+1<len(LEVELS) and total<LEVELS[i+1][0]:
            prog=total-thr; needed=LEVELS[i+1][0]-thr; filled=int((prog/needed)*10)
            return f"[{'█'*filled}{'░'*(10-filled)}] {prog}/{needed} XP"
    return "[██████████] MAX 👑"

def check_achievements(state,meta)->list:
    unlocked=meta.setdefault("unlocked_achievements",[])
    new=[]
    for a in ACHIEVEMENTS:
        if a["id"] not in unlocked:
            try:
                if a["check"](meta,state): unlocked.append(a["id"]); new.append(a)
            except: pass
    return new

# ─── STATE ────────────────────────────────────────────────────────────────────

STATE_FILE="/data/watering_state.json"
VOLUME_OK=False
TIMER_SESSIONS:dict={}

def load_state()->dict:
    try:
        with open(STATE_FILE) as f: raw=json.load(f)
        return raw if isinstance(raw,dict) else {}
    except: return {}

def save_state(state:dict):
    try:
        os.makedirs("/data",exist_ok=True)
        tmp=STATE_FILE+".tmp"
        with open(tmp,"w") as f: json.dump(state,f,indent=2,default=str)
        os.replace(tmp,STATE_FILE)
    except Exception as e: logging.error(f"Save: {e}")

def verify_volume()->bool:
    try:
        os.makedirs("/data",exist_ok=True)
        with open("/data/.chk","w") as f: f.write("ok")
        os.remove("/data/.chk"); return True
    except: return False

def get_meta(state:dict)->dict:
    return state.setdefault("_meta",{
        "streak":0,"streak_no_skip":0,"comeback_streak":0,
        "last_streak_date":None,"last_activity":None,
        "total_waterings":0,"rain_saves":0,"early_waterings":0,
        "midnight_waterings":0,"fertilizations_this_month":0,
        "fert_reset_month":None,"days_over_40c":0,"days_using_bot":0,
        "all_same_day":False,"rain_log":[],"travel_until":None,
        "fertilize_log":{},"watering_history":[],"unlocked_achievements":[],
        "bot_start_date":date.today().isoformat(),
    })

# ─── SEASON / ET / RAIN ───────────────────────────────────────────────────────

def get_season()->str:
    m=date.today().month
    if m in(7,8,9): return"monsoon"
    if m in(6,10): return"hot"
    if m in(11,12,1,2): return"cool"
    return"spring"

SEASON_LABEL={"monsoon":"🌧️ Monzón","hot":"🔥 Calor Extremo","cool":"❄️ Invierno","spring":"🌱 Primavera"}

def et_factor(temp_c,humidity,wind_ms)->float:
    if temp_c is None: return 1.0
    eto_ref=TUCSON_ETO_REF.get(date.today().month,5.0)
    hum=humidity or 25
    vpd=max(0,1-hum/100)*0.6108*(2.71828**(17.27*temp_c/(temp_c+237.3)))
    return max(0.5,min(1.8,vpd*(1+(wind_ms or 0)*0.04)*3.5/eto_ref))

def log_rain(state,mm):
    if mm<=0: return
    meta=get_meta(state); today=date.today().isoformat()
    log=meta.setdefault("rain_log",[])
    if not any(r["date"]==today for r in log): log.append({"date":today,"mm":round(mm,1)})
    cutoff=(date.today()-timedelta(days=14)).isoformat()
    meta["rain_log"]=[r for r in log if r["date"]>=cutoff]

def recent_rain(state,days=3)->float:
    meta=get_meta(state); cutoff=(date.today()-timedelta(days=days)).isoformat()
    return sum(r["mm"] for r in meta.get("rain_log",[]) if r["date"]>=cutoff)

# ─── INTERVALS ────────────────────────────────────────────────────────────────

def pot_adj_i(d): return 0 if not d else(-1 if d<18 else(0 if d<=35 else(1 if d<=50 else 2)))
def pot_adj_d(d): return 0 if not d else(-1 if d<18 else(0 if d<=35 else(1 if d<=50 else 2)))

def get_adaptive(state,pid)->float:
    hist=[h for h in get_meta(state).get("watering_history",[]) if h["pid"]==pid]
    if len(hist)<3: return 1.0
    ratios=[h["actual"]/h["suggested"] for h in hist[-5:] if h["suggested"]>0]
    return max(0.75,min(1.25,sum(ratios)/len(ratios))) if ratios else 1.0

def calc_interval(plant,temp_c,season,et=1.0,soil_rain=0.0,adaptive=1.0)->int:
    base=plant["base_days"]
    if season=="cool":      iv=int(base*plant["cool_factor"])
    elif season=="monsoon": iv=base+plant["monsoon_bonus"]
    elif season=="hot":     iv=max(1,int(base*plant["heat_factor"]))
    else:                   iv=base
    if temp_c is not None:
        if temp_c>=41:   iv=max(1,int(iv*0.65))
        elif temp_c>=38: iv=max(1,int(iv*0.80))
        elif temp_c<=8:  iv=int(iv*1.60)
    iv=max(1,int(iv/et))
    if not plant["pot"] and soil_rain>0: iv+=min(base//2,int(soil_rain/5))
    if plant["pot"]:
        iv+=pot_adj_i(plant.get("pot_diameter_cm"))
        # Only reduce interval in extreme Tucson heat, not always
        # This prevents macetas showing every 1-2 days in spring/normal temps
        if temp_c is not None and temp_c>=40:
            iv=max(1,iv-1)
    return max(1,round(iv*adaptive))

def calc_duration(plant,temp_c,season,et=1.0)->int:
    wp=plant["watering_profile"]; mins=wp["duration_min"]
    if season=="cool":                       mins=max(1,mins-wp["cool_less_min"])
    elif temp_c is not None and temp_c>=38:  mins+=wp["heat_extra_min"]
    if et>1.4: mins+=1
    if plant["pot"]: mins+=pot_adj_d(plant.get("pot_diameter_cm"))
    return max(1,mins)

def plant_status(plant,state,temp_c,season,et,soil_r)->dict:
    pid=plant["id"]; adaptive=get_adaptive(state,pid)
    interval=calc_interval(plant,temp_c,season,et,soil_r,adaptive)
    mins=calc_duration(plant,temp_c,season,et)
    last=state.get(pid,{}).get("last_watered"); today=date.today().isoformat()
    if last is None:
        days_since=0; overdue=0; label="🆕 Nueva"
    else:
        days_since=(date.today()-date.fromisoformat(last)).days; overdue=days_since-interval
        if overdue>1:            label=f"🚨 +{overdue}d"
        elif overdue==1:         label="🔶 +1d"
        elif overdue==0:         label="⏰ Hoy"
        elif interval-days_since==1: label="🟡 Mañana"
        else:                    label=f"✅ {interval-days_since}d"
    skip_until=state.get(pid,{}).get("skip_until","")
    skipped_today = skip_until>=today if skip_until else False
    return {"interval":interval,"mins":mins,"overdue":overdue,
            "days_since":days_since,"label":label,
            "watered_today":last==today,"skipped":skipped_today,"last":last}

# ─── WEATHER ──────────────────────────────────────────────────────────────────

async def get_weather()->dict:
    icons={"01":"☀️","02":"⛅","03":"🌥️","04":"☁️","09":"🌧️","10":"🌦️","11":"⛈️","13":"🌨️","50":"🌫️"}
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            cr,fr=await asyncio.gather(
                cl.get(f"https://api.openweathermap.org/data/2.5/weather?lat={TUCSON_LAT}&lon={TUCSON_LON}&appid={OWM_KEY}&units=metric&lang=es"),
                cl.get(f"https://api.openweathermap.org/data/2.5/forecast?lat={TUCSON_LAT}&lon={TUCSON_LON}&appid={OWM_KEY}&units=metric&cnt=16"),
            )
        c,f=cr.json(),fr.json()
        tom=(date.today()+timedelta(days=1)).isoformat()
        rain_tom=sum(s.get("rain",{}).get("3h",0) for s in f.get("list",[])
                     if datetime.fromtimestamp(s["dt"],tz=TUCSON_TZ).date().isoformat()==tom)
        min_tom=min((s["main"]["temp_min"] for s in f.get("list",[])
                     if datetime.fromtimestamp(s["dt"],tz=TUCSON_TZ).date().isoformat()==tom),default=None)
        return {"ok":True,"temp_c":c["main"]["temp"],"feels_like":c["main"]["feels_like"],
                "humidity":c["main"]["humidity"],"wind_ms":c.get("wind",{}).get("speed",0),
                "rain_mm":c.get("rain",{}).get("3h",0.0),"rain_tomorrow":rain_tom,
                "min_temp_tomorrow":min_tom,
                "description":c["weather"][0]["description"].capitalize(),
                "icon":icons.get(c["weather"][0]["icon"][:2],"🌡️")}
    except Exception as e:
        logging.warning(f"WX: {e}")
        return{"ok":False,"temp_c":None,"rain_mm":0.0,"rain_tomorrow":0.0,
               "min_temp_tomorrow":None,"humidity":None,"wind_ms":0}

# ─── TELEGRAM HELPERS ─────────────────────────────────────────────────────────

async def tg_call(method:str,payload:dict)->dict:
    async with httpx.AsyncClient(timeout=15) as cl:
        r=await cl.post(f"{API}/{method}",json=payload)
        return r.json()

async def send(text:str,kb:dict|None=None,chat:str|None=None)->dict:
    p={"chat_id":chat or CHAT_ID,"text":text[:4096],"parse_mode":"HTML"}
    if kb: p["reply_markup"]=kb
    return await tg_call("sendMessage",p)

async def edit(chat:str,mid:int,text:str,kb:dict|None=None):
    p={"chat_id":chat,"message_id":mid,"text":text[:4096],"parse_mode":"HTML"}
    if kb: p["reply_markup"]=kb
    try: await tg_call("editMessageText",p)
    except: pass  # ignore "message not modified"

async def answer(cbid:str,text:str="",alert:bool=False):
    await tg_call("answerCallbackQuery",{"callback_query_id":cbid,"text":text[:200],"show_alert":alert})

# ─── REGISTER WATERING ────────────────────────────────────────────────────────

def register_watering(state,pids,temp_c,season,et,soil_r,now)->list:
    meta=get_meta(state); today=date.today().isoformat(); newly=[]
    for pid in pids:
        plant=PLANT_MAP.get(pid)
        if not plant: continue
        pstate=state.setdefault(pid,{}); last=pstate.get("last_watered")
        if last==today: continue
        adaptive=get_adaptive(state,pid)
        interval=calc_interval(plant,temp_c,season,et,soil_r,adaptive)
        if last:
            actual=(date.today()-date.fromisoformat(last)).days
            meta.setdefault("watering_history",[]).append(
                {"date":today,"pid":pid,"suggested":interval,"actual":actual})
        pstate["last_watered"]=today; pstate.pop("skip_until",None); newly.append(pid)
    if not newly: return newly
    meta["total_waterings"]=meta.get("total_waterings",0)+len(newly)
    meta["last_activity"]=today
    if meta.get("fert_reset_month")!=date.today().month:
        meta["fertilizations_this_month"]=0; meta["fert_reset_month"]=date.today().month
    hist=meta.get("watering_history",[])
    if len(hist)>90: meta["watering_history"]=hist[-90:]
    if all(state.get(p["id"],{}).get("last_watered")==today for p in PLANTS):
        meta["all_same_day"]=True
    last_s=meta.get("last_streak_date"); yesterday=(date.today()-timedelta(days=1)).isoformat()
    if last_s==yesterday:
        meta["streak"]=meta.get("streak",0)+1
        meta["streak_no_skip"]=meta.get("streak_no_skip",0)+1
    elif last_s!=today:
        if meta.get("streak",0)>0: meta["comeback_streak"]=0
        meta["streak"]=1; meta["streak_no_skip"]=1
        meta["comeback_streak"]=meta.get("comeback_streak",0)+1
    meta["last_streak_date"]=today
    if now.hour<=20: meta["early_waterings"]=meta.get("early_waterings",0)+1
    if 0<=now.hour<4: meta["midnight_waterings"]=meta.get("midnight_waterings",0)+1
    return newly

# ─── NAVBAR ───────────────────────────────────────────────────────────────────
# Barra de navegación fija al fondo de TODAS las pantallas

def navbar(active:str="")->dict:
    """
    active: "today" | "garden" | "timer" | "stats"
    El botón activo se muestra con bullet para orientación.
    """
    def btn(label,cb,is_active):
        return {"text":f"· {label} ·" if is_active else label,"callback_data":cb}
    return {"inline_keyboard":[[
        btn("🌿 Hoy",    "nav_today",  active=="today"),
        btn("🌱 Jardín", "nav_garden", active=="garden"),
        btn("▶️ Regar",  "nav_timer",  active=="timer"),
        btn("📊 Stats",  "nav_stats",  active=="stats"),
    ]]}

def navbar_with(rows:list,active:str="")->dict:
    """Combina botones propios de la pantalla + navbar."""
    return {"inline_keyboard": rows+navbar(active)["inline_keyboard"]}

# ─── SCREENS ──────────────────────────────────────────────────────────────────

def screen_today(state,temp_c,season,et,soil_r,wx)->tuple:
    """
    Pantalla principal: qué tocan hoy.
    Retorna (texto, keyboard).
    Cada planta que toca tiene su botón ✅ directo.
    """
    today   = date.today().isoformat()
    now     = datetime.now(TUCSON_TZ)
    meta    = get_meta(state)
    streak  = meta.get("streak",0)
    total   = meta.get("total_waterings",0)
    level,_ = get_level(total)

    due, ok, skip = [], [], []
    for plant in PLANTS:
        pid    = plant["id"]
        st     = plant_status(plant,state,temp_c,season,et,soil_r)
        skip_u = state.get(pid,{}).get("skip_until","")
        if st["watered_today"]:
            ok.append((plant,st))
        elif skip_u >= today:
            skip.append((plant,st))
        elif st["overdue"]>=0:
            due.append((plant,st))

    # Header
    wx_line = (f"{wx['icon']} <b>{wx['temp_c']:.0f}°C</b> · {wx['humidity']}% hum"
               if wx.get("ok") else "🌡️ Sin datos de clima")

    if not due:
        header = (
            f"✅ <b>Todo al día</b> · {now.strftime('%d %b')}\n"
            f"{wx_line}\n"
            f"{'━'*22}\n"
            f"🔥 Racha: <b>{streak}d</b>  ·  💧 {total} riegos\n"
            f"<i>No toca regar ninguna planta hoy.</i>"
        )
    else:
        if streak>=7:
            intro=f"🔥 <b>{streak} días de racha.</b> Sigue así."
        elif temp_c and temp_c>=40:
            intro=f"🌡️ <b>{wx['temp_c']:.0f}°C afuera.</b> Tus plantas lo sienten."
        else:
            intro=random.choice([
                "🌙 Hora de regar.",
                "💧 El jardín espera.",
                "🌵 Tucson no perdona. Riega.",
            ])
        header=(
            f"<b>{intro}</b>\n"
            f"{wx_line}  ·  {SEASON_LABEL[season]}\n"
            f"{'━'*22}\n"
            f"🔥 {streak}d  ·  {level}  ·  💧{total}"
        )

    # Lista de plantas que tocan — con botón directo
    rows=[]
    body_lines=[]

    if due:
        body_lines.append(f"\n<b>💧 Regar hoy ({len(due)}):</b>")
        for plant,st in sorted(due, key=lambda x:-x[1]["overdue"]):
            wp   = plant["watering_profile"]
            mins = st["mins"]
            liters=round(wp["flow_lpm"]*mins,1)
            voice=random.choice(VOICES.get(plant["id"],{}).get(
                "dying" if st["overdue"]>1 else "thirsty",["Agua, por favor."]))
            body_lines.append(
                f"\n{st['label']} <b>{plant['name']}</b>"
                f"  ⏱{mins}m · ~{liters}L"
                f"\n<i>\"{voice}\"</i>"
            )
            rows.append([
                {"text":f"✅ {plant['name']}","callback_data":f"w:{plant['id']}:today"},
                {"text":"🖐 Húmedo","callback_data":f"moist:{plant['id']}:today"}
                if plant["pot"] else
                {"text":"ℹ️ Cómo","callback_data":f"detail:{plant['id']}:today"},
            ])

        if len(due)>1:
            rows.append([{"text":f"✅ Regar todas ({len(due)})","callback_data":"water_all_today"}])

    if ok:
        body_lines.append(f"\n<b>✅ Listas ({len(ok)}):</b>  " +
                          "  ".join(p["name"] for p,_ in ok))
    if skip:
        body_lines.append(f"<b>⏭ Saltadas:</b>  " +
                          "  ".join(p["name"] for p,_ in skip))

    txt = header+"\n"+"".join(body_lines)
    kb  = navbar_with(rows, "today")
    return txt, kb


def screen_garden(state,temp_c,season,et,soil_r)->tuple:
    """Vista completa de todas las plantas con estado."""
    now=datetime.now(TUCSON_TZ)
    lines=[f"🌱 <b>Jardín completo</b> · {now.strftime('%d %b')}","━"*22,""]
    rows=[]
    for plant in PLANTS:
        st=plant_status(plant,state,temp_c,season,et,soil_r)
        loc="🪣" if plant["pot"] else "🌍"
        lines.append(f"{st['label']} {loc} <b>{plant['name']}</b>  "
                     f"<i>cada {st['interval']}d · {st['mins']}min</i>")
        action_cb=(f"w:{plant['id']}:garden" if not st["watered_today"] and st["overdue"]>=0
                   else f"detail:{plant['id']}:garden")
        action_lbl=("✅ Regar" if not st["watered_today"] and st["overdue"]>=0 else "ℹ️")
        rows.append([
            {"text":action_lbl,"callback_data":action_cb},
            {"text":plant["name"],"callback_data":f"detail:{plant['id']}:garden"},
        ])
    kb=navbar_with(rows,"garden")
    return "\n".join(lines),kb


def screen_detail(plant,state,temp_c,season,et,soil_r,back)->tuple:
    """Tarjeta detallada de una planta."""
    st=plant_status(plant,state,temp_c,season,et,soil_r)
    wp=plant["watering_profile"]; pid=plant["id"]
    v=VOICES.get(pid,{})
    if st["watered_today"]:  pool=v.get("happy",["Gracias."])
    elif st["overdue"]>1:    pool=v.get("dying",["Agua urgente."])
    elif st["overdue"]>=0:   pool=v.get("thirsty",["Necesito agua."])
    else:                    pool=v.get("happy",["Estoy bien."])
    voice=random.choice(pool)
    loc="🪣 Maceta" if plant["pot"] else "🌍 Tierra"
    liters=round(wp["flow_lpm"]*st["mins"],1)
    lines=[
        f"<b>{plant['name']}</b>  ·  {loc}",
        "━"*22,"",
        f"<i>\"{voice}\"</i>","",
        f"📊 {st['label']}",
        f"🗓 Último riego: hace <b>{st['days_since']}d</b>" if st["last"] else "",
        f"📆 Intervalo: cada <b>{st['interval']} días</b>","",
        "<b>Instrucciones de riego:</b>",
        f"⏱ <b>{st['mins']} min</b>  ·  💧 <b>{wp['flow_lpm']} L/min</b>  →  ~<b>{liters} L</b>",
        f"🔧 {wp['method']}",
        f"🎯 {wp['target']}",
    ]
    # Nota especial (ej. Monstera en transición)
    if plant.get("note"):
        lines+=["",f"<i>{plant['note']}</i>"]
    # Fertilización
    if plant.get("fertilize_weeks") and get_season()!="cool":
        flog=get_meta(state).get("fertilize_log",{}); last_f=flog.get(pid)
        if last_f:
            df=(date.today()-date.fromisoformat(last_f)).days
            if df>=plant["fertilize_weeks"]*7: lines+=["",f"🌿 <b>¡Fertilización pendiente!</b> ({df}d)"]
        else: lines+=["",f"🌿 Fertiliza cada {plant['fertilize_weeks']} semanas"]
    # Plagas
    if date.today().month in plant.get("pest_season",[]):
        pest={"cycas_1":"🐛 Revisa cochinilla en base de frondas",
              "cycas_2":"🐛 Revisa cochinilla en base de frondas",
              "rosal":"🐛 Revisa pulgón en brotes nuevos",
              "toronja":"🐛 Revisa minador de hoja y escama",
              "limon":"🐛 Revisa minador de hoja y escama",
              "mandarina":"🐛 Revisa escama y trips",
              "lilly_asiatica":"🐛 Revisa ácaros debajo de hojas",
              "geranio":"🐛 Revisa mosca blanca debajo de hojas",
              "vinca":"🐛 Revisa ácaros y trips",
              "monstera":"🐛 Revisa araña roja y escama en tallos"}.get(pid)
        if pest: lines+=["",pest]

    rows=[]
    if not st["watered_today"]:
        rows.append([{"text":f"✅ Ya la regué","callback_data":f"w:{pid}:{back}"}])
        if plant["pot"]:
            rows.append([{"text":"🖐 Sustrato húmedo — esperar 2 días",
                          "callback_data":f"moist:{pid}:{back}"}])
    rows.append([{"text":"⏭ Saltar hoy","callback_data":f"skip:{pid}:{back}"},
                 {"text":"💊 Fertilicé","callback_data":f"fert:{pid}:{back}"}])
    rows.append([{"text":f"⬅️ Regresar","callback_data":f"nav:{back}"}])
    kb=navbar_with(rows,"today" if back=="today" else "garden")
    return "\n".join(l for l in lines if l is not None),kb


def screen_stats(state)->tuple:
    meta=get_meta(state)
    total=meta.get("total_waterings",0); streak=meta.get("streak",0)
    level,nxt=get_level(total)
    unlocked=len(meta.get("unlocked_achievements",[]))
    start=meta.get("bot_start_date",date.today().isoformat())
    days=(date.today()-date.fromisoformat(start)).days
    rain30=sum(r["mm"] for r in meta.get("rain_log",[])
               if r["date"]>=(date.today()-timedelta(days=30)).isoformat())
    lines=[
        "📊 <b>Mi progreso</b>","━"*22,"",
        f"👤 <b>{level}</b>",
        f"⬆️ {xp_bar(total)}","",
        f"💧 Riegos totales: <b>{total}</b>",
        f"🔥 Racha actual: <b>{streak} días</b>",
        f"📅 Días usando el bot: <b>{days}</b>",
        f"🌧️ Lluvia este mes: <b>{rain30:.0f} mm</b>",
        f"🏆 Logros: <b>{unlocked}/{len(ACHIEVEMENTS)}</b>","",
    ]
    if nxt: lines.append(f"<i>Próximo nivel: {nxt}</i>")
    lines+=["","<b>Todos los logros:</b>"]
    for a in ACHIEVEMENTS:
        done=a["id"] in meta.get("unlocked_achievements",[])
        lines.append(f"{'✅' if done else '🔒'} {a['name']}")
    kb=navbar(active="stats")
    return "\n".join(lines),kb


def screen_timer_prepare(state,temp_c,season,et,soil_r)->tuple:
    """Pantalla previa al timer: muestra la cola."""
    today=date.today().isoformat()
    due_pids=[]
    for plant in PLANTS:
        pid=plant["id"]; st=plant_status(plant,state,temp_c,season,et,soil_r)
        skip_u=state.get(pid,{}).get("skip_until","")
        if not st["watered_today"] and st["overdue"]>=0 and skip_u<today:
            due_pids.append(pid)
    if not due_pids:
        return ("✅ <b>No hay plantas que regar ahora.</b>\n\nTodas al día.",
                navbar(active="timer"))
    total_min=sum(calc_duration(PLANT_MAP[pid],temp_c,season,et) for pid in due_pids)
    lines=[f"▶️ <b>Riego guiado</b> · {len(due_pids)} plantas · ~{total_min} min","━"*22,""]
    for i,pid in enumerate(due_pids):
        p=PLANT_MAP[pid]; mins=calc_duration(p,temp_c,season,et)
        loc="🪣" if p["pot"] else "🌍"
        lines.append(f"  {i+1}. {p['name']} {loc} — {mins} min")
    lines+=["","<i>El bot te avisa cuando termina cada planta.</i>"]
    rows=[[{"text":f"▶️ Iniciar riego","callback_data":"timer_start"}]]
    kb=navbar_with(rows,"timer")
    return "\n".join(lines),(kb,due_pids)


def screen_timer_plant(pid,mins,step,total,started_at)->tuple:
    plant=PLANT_MAP[pid]; wp=plant["watering_profile"]
    elapsed=(datetime.now(TUCSON_TZ)-started_at).seconds//60
    pct=min(1.0,elapsed/max(1,mins)); filled=int(pct*12)
    bar="█"*filled+"░"*(12-filled)
    liters=round(wp["flow_lpm"]*mins,1)
    voice=random.choice(VOICES.get(pid,{}).get("thirsty",["Agua, por favor."]))
    loc="🪣 Maceta" if plant["pot"] else "🌍 Tierra"
    lines=[
        f"⏱ <b>Riego en curso</b>  [{step}/{total}]","━"*22,"",
        f"<b>{plant['name']}</b>  ·  {loc}",
        f"<i>\"{voice}\"</i>","",
        f"⏳ <b>{mins} min</b>  ·  💧 {wp['flow_lpm']} L/min  →  ~{liters} L",
        f"🔧 {wp['method']}",
        f"🎯 {wp['target']}","",
        f"[{bar}]  {int(pct*100)}%","",
        "<i>Toca ⏭ cuando termines esta planta.</i>",
    ]
    rows=[]
    if plant["pot"]:
        rows.append([{"text":"🖐 Sustrato húmedo — saltar","callback_data":f"tmoist:{pid}"}])
    rows.append([{"text":f"⏭ Siguiente  ({step}/{total})","callback_data":f"tnext:{pid}"}])
    rows.append([{"text":"✅ Terminé todo","callback_data":"tdone"},
                 {"text":"❌ Cancelar","callback_data":"tcancel"}])
    return "\n".join(lines),{"inline_keyboard":rows}


def screen_timer_summary(completed,skipped_moist)->tuple:
    total_min=sum(PLANT_MAP[pid]["watering_profile"]["duration_min"]
                  for pid in completed if pid in PLANT_MAP)
    total_L=sum(PLANT_MAP[pid]["watering_profile"]["flow_lpm"]*
                PLANT_MAP[pid]["watering_profile"]["duration_min"]
                for pid in completed if pid in PLANT_MAP)
    lines=["🎉 <b>Riego completado</b>","━"*22,""]
    for pid in completed:
        if pid in PLANT_MAP: lines.append(f"  ✅ {PLANT_MAP[pid]['name']}")
    for pid in skipped_moist:
        if pid in PLANT_MAP:
            lines.append(f"  🖐 {PLANT_MAP[pid]['name']} — húmedo, revisión en 2d")
    lines+=["","━"*22,
            f"⏱ ~<b>{total_min} min</b>  ·  💧 ~<b>{total_L:.0f} L</b>","",
            "<i>Toca para registrar.</i>"]
    kb={"inline_keyboard":[
        [{"text":"✅ Registrar riegos","callback_data":"tconfirm"}],
        [{"text":"⬅️ Inicio","callback_data":"nav_today"}],
    ]}
    return "\n".join(lines),kb

# ─── EVENING PUSH ─────────────────────────────────────────────────────────────

async def evening_check():
    season=get_season(); wx=await get_weather(); state=load_state()
    today=date.today().isoformat(); meta=get_meta(state)
    temp_c=wx.get("temp_c"); rain_mm=wx.get("rain_mm",0.0)
    et=et_factor(temp_c,wx.get("humidity"),wx.get("wind_ms",0))
    if rain_mm>0: log_rain(state,rain_mm)
    soil_r=recent_rain(state,days=3)
    travel_until=meta.get("travel_until")
    if travel_until and travel_until>=today: save_state(state); return
    if temp_c and temp_c>=40: meta["days_over_40c"]=meta.get("days_over_40c",0)+1
    start=date.fromisoformat(meta.get("bot_start_date",today))
    meta["days_using_bot"]=(date.today()-start).days

    due,skipped=[],[]
    for plant in PLANTS:
        pid=plant["id"]; pstate=state.setdefault(pid,{})
        last=pstate.get("last_watered")
        adaptive=get_adaptive(state,pid)
        interval=calc_interval(plant,temp_c,season,et,soil_r,adaptive)
        mins=calc_duration(plant,temp_c,season,et)
        pstate.update({"interval_days":interval,"duration_min":mins})
        if last is None: pstate["last_watered"]=today; due.append((plant,mins,0)); continue
        days_since=(date.today()-date.fromisoformat(last)).days
        skip_until=pstate.get("skip_until","")
        if skip_until>=today: skipped.append(plant); continue
        if days_since>=interval:
            if not plant["pot"] and rain_mm>=8.0:
                meta["rain_saves"]=meta.get("rain_saves",0)+1; skipped.append(plant)
            else:
                due.append((plant,mins,days_since-interval))

    new_ach=check_achievements(state,meta); save_state(state)
    for a in new_ach:
        await send(f"🏆 <b>¡LOGRO!</b> {a['name']}\n{a['desc']}")

    if not due: logging.info("8PM: nada."); return

    # Usar screen_today para el push (botones directos incluidos)
    txt,kb=screen_today(state,temp_c,season,et,soil_r,wx)
    # Agregar aviso de helada si aplica
    min_tom=wx.get("min_temp_tomorrow")
    await send(txt,kb)
    if min_tom and min_tom<2:
        pots=[p["name"] for p in PLANTS if p["pot"]]
        await send(f"🥶 <b>ALERTA HELADA</b>\n\nMañana mínima <b>{min_tom:.0f}°C</b>\n\n"
                   f"Mete o cubre:\n"+"\n".join(f"  • {n}" for n in pots))
    logging.info(f"8PM push: {len(due)} plantas.")

async def weekly_summary():
    state=load_state(); meta=get_meta(state)
    txt,kb=screen_stats(state)
    await send(txt,kb)
    tips={"monsoon":"🌧️ Monzón: revisa drenaje de macetas.",
          "hot":"🔥 Calor: mulch en cítricos. Macetas pueden necesitar revisión diaria.",
          "cool":"❄️ Invierno: Monstera adentro si baja de 5°C.",
          "spring":"🌱 Primavera: fertiliza cítricos. Revisa pulgón en el rosal."}
    season=get_season()
    if season in tips: await send(tips[season],navbar())

# ─── CALLBACK HANDLER ─────────────────────────────────────────────────────────

async def handle_cb(update:dict):
    cb=update["callback_query"]
    data=cb["data"]; cbid=cb["id"]
    chat=str(cb["message"]["chat"]["id"]); mid=cb["message"]["message_id"]
    # NOTE: answer(cbid) called per-handler with meaningful text, not blanket here

    wx=await get_weather(); state=load_state(); meta=get_meta(state)
    season=get_season(); temp_c=wx.get("temp_c")
    et=et_factor(temp_c,wx.get("humidity"),wx.get("wind_ms",0))
    soil_r=recent_rain(state,days=3); now=datetime.now(TUCSON_TZ)

    async def refresh_today():
        txt,kb=screen_today(state,temp_c,season,et,soil_r,wx)
        await edit(chat,mid,txt,kb)

    async def refresh_garden():
        txt,kb=screen_garden(state,temp_c,season,et,soil_r)
        await edit(chat,mid,txt,kb)

    async def ack(text:str="✓",alert:bool=False):
        """Answer callback with toast."""
        await answer(cbid,text,alert)

    # ── Navbar ────────────────────────────────────────────────────────────
    if data=="nav_today" or data=="nav:today":
        await ack("🌿 Hoy")
        await refresh_today()

    elif data=="nav_garden" or data=="nav:garden":
        await ack("🌱 Jardín")
        txt,kb=screen_garden(state,temp_c,season,et,soil_r)
        await edit(chat,mid,txt,kb)

    elif data=="nav_timer" or data=="nav:timer":
        await ack("▶️ Riego guiado")
        result=screen_timer_prepare(state,temp_c,season,et,soil_r)
        txt,kb_or_tuple=result
        # BUG3 FIX: do NOT create session here — only on timer_start
        if isinstance(kb_or_tuple,tuple):
            kb,_=kb_or_tuple
            await edit(chat,mid,txt,kb)
        else:
            await edit(chat,mid,txt,kb_or_tuple)

    elif data=="nav_stats" or data=="nav:stats":
        await ack("📊 Stats")
        txt,kb=screen_stats(state)
        await edit(chat,mid,txt,kb)

    # ── Regar planta individual ────────────────────────────────────────────
    elif data.startswith("w:"):
        rest=data[2:].split(":",1); pid=rest[0]; back=rest[1] if len(rest)>1 else "today"
        newly=register_watering(state,[pid],temp_c,season,et,soil_r,now)
        new_ach=check_achievements(state,meta); save_state(state)
        plant_name=PLANT_MAP.get(pid,{}).get("name",pid)
        if newly:
            await ack(f"✅ {plant_name} regada 💧",alert=False)
            for a in new_ach: await send(f"🏆 <b>¡LOGRO!</b> {a['name']}\n{a['desc']}")
        else:
            await ack(f"Ya estaba regada hoy ✅")
        if back=="garden": await refresh_garden()
        else: await refresh_today()

    # ── Regar todo (solo las que tocan) ───────────────────────────────────
    elif data=="water_all_today":
        # BUG2 FIX: only mark plants that are actually due, not all 10
        today_str=date.today().isoformat()
        due_pids=[]
        for plant in PLANTS:
            pid=plant["id"]; st=plant_status(plant,state,temp_c,season,et,soil_r)
            skip_u=state.get(pid,{}).get("skip_until","")
            if not st["watered_today"] and st["overdue"]>=0 and skip_u<today_str:
                due_pids.append(pid)
        newly=register_watering(state,due_pids,temp_c,season,et,soil_r,now)
        new_ach=check_achievements(state,meta); save_state(state)
        await ack(f"✅ {len(newly)} plantas regadas 🎉",alert=True)
        for a in new_ach: await send(f"🏆 <b>¡LOGRO!</b> {a['name']}\n{a['desc']}")
        await refresh_today()

    # ── Detalle de planta ──────────────────────────────────────────────────
    elif data.startswith("detail:"):
        rest=data[7:].split(":",1); pid=rest[0]; back=rest[1] if len(rest)>1 else "today"
        plant=PLANT_MAP.get(pid)
        if plant:
            await ack()
            txt,kb=screen_detail(plant,state,temp_c,season,et,soil_r,back)
            await edit(chat,mid,txt,kb)
        else:
            await ack("❓ Planta no encontrada")

    # ── Sustrato húmedo ───────────────────────────────────────────────────
    elif data.startswith("moist:"):
        rest=data[6:].split(":",1); pid=rest[0]; back=rest[1] if len(rest)>1 else "today"
        plant=PLANT_MAP.get(pid)
        if plant and plant["pot"]:
            until=(date.today()+timedelta(days=2)).isoformat()
            state.setdefault(pid,{})["skip_until"]=until; save_state(state)
            await ack("🖐 Ok, revisamos en 2 días",alert=True)
            if back=="garden": await refresh_garden()
            else: await refresh_today()
        else:
            await ack()

    # ── Skip ──────────────────────────────────────────────────────────────
    elif data.startswith("skip:"):
        rest=data[5:].split(":",1); pid=rest[0]; back=rest[1] if len(rest)>1 else "today"
        until=(date.today()+timedelta(days=1)).isoformat()
        state.setdefault(pid,{})["skip_until"]=until; save_state(state)
        plant_name=PLANT_MAP.get(pid,{}).get("name",pid)
        await ack(f"⏭ {plant_name} saltada hasta mañana",alert=True)
        if back=="garden": await refresh_garden()
        else: await refresh_today()

    # ── Fertilizar ────────────────────────────────────────────────────────
    elif data.startswith("fert:"):
        rest=data[5:].split(":",1); pid=rest[0]; back=rest[1] if len(rest)>1 else "today"
        plant=PLANT_MAP.get(pid)
        if plant:
            meta.setdefault("fertilize_log",{})[pid]=date.today().isoformat()
            meta["fertilizations_this_month"]=meta.get("fertilizations_this_month",0)+1
            new_ach=check_achievements(state,meta); save_state(state)
            await ack(f"🌿 {plant['name']} fertilizada",alert=True)
            for a in new_ach: await send(f"🏆 <b>¡LOGRO!</b> {a['name']}\n{a['desc']}")
            if back=="garden": await refresh_garden()
            else: await refresh_today()
        else:
            await ack()

    # ── Timer: iniciar ────────────────────────────────────────────────────
    elif data=="timer_start":
        result=screen_timer_prepare(state,temp_c,season,et,soil_r)
        _,kb_or_tuple=result
        if not isinstance(kb_or_tuple,tuple):
            await ack("No hay plantas que regar"); return
        _,due_pids=kb_or_tuple
        # BUG3 FIX: create session HERE (on Iniciar), not on nav_timer
        sess={"queue":due_pids[1:],"current":due_pids[0],"started_at":now,
              "mins":calc_duration(PLANT_MAP[due_pids[0]],temp_c,season,et),
              "completed":[],"skipped_moist":[],"step":1,"total":len(due_pids)}
        TIMER_SESSIONS[chat]=sess
        await ack(f"▶️ Iniciando — {len(due_pids)} plantas")
        txt,kb=screen_timer_plant(due_pids[0],sess["mins"],1,sess["total"],now)
        await edit(chat,mid,txt,kb)
        async def remind(cid,pid,mins,step,total):
            await asyncio.sleep(mins*60)
            sess=TIMER_SESSIONS.get(cid)
            if sess and sess.get("current")==pid:
                p=PLANT_MAP[pid]
                _,kb=screen_timer_plant(pid,mins,step,total,sess["started_at"])
                await send(f"⏰ <b>¡Tiempo!</b> {p['name']} — {mins} min\n"
                           f"Toca <b>⏭ Siguiente</b> cuando estés listo.",kb,chat=cid)
        asyncio.create_task(remind(chat,due_pids[0],sess["mins"],1,sess["total"]))

    # ── Timer: siguiente ──────────────────────────────────────────────────
    elif data.startswith("tnext:"):
        pid_done=data[6:]; sess=TIMER_SESSIONS.get(chat)
        if not sess: await ack("Sesión expirada — regresa al inicio"); return
        sess["completed"].append(pid_done)
        await ack(f"✅ {PLANT_MAP.get(pid_done,{}).get('name',pid_done)} lista")
        if not sess["queue"]:
            txt,kb=screen_timer_summary(sess["completed"],sess["skipped_moist"])
            await edit(chat,mid,txt,kb)
        else:
            nxt=sess["queue"].pop(0); nmins=calc_duration(PLANT_MAP[nxt],temp_c,season,et)
            sess.update({"current":nxt,"mins":nmins,"step":sess["step"]+1,"started_at":now})
            txt,kb=screen_timer_plant(nxt,nmins,sess["step"],sess["total"],now)
            await edit(chat,mid,txt,kb)
            async def remind2(cid,pid,mins,step,total):
                await asyncio.sleep(mins*60)
                s=TIMER_SESSIONS.get(cid)
                if s and s.get("current")==pid:
                    p=PLANT_MAP[pid]; _,kb=screen_timer_plant(pid,mins,step,total,s["started_at"])
                    await send(f"⏰ <b>¡Tiempo!</b> {p['name']}\nToca <b>⏭ Siguiente</b>.",kb,chat=cid)
            asyncio.create_task(remind2(chat,nxt,nmins,sess["step"],sess["total"]))

    # ── Timer: sustrato húmedo ────────────────────────────────────────────
    elif data.startswith("tmoist:"):
        pid_m=data[7:]; sess=TIMER_SESSIONS.get(chat)
        if not sess: await ack("Sesión expirada"); return
        until=(date.today()+timedelta(days=2)).isoformat()
        state.setdefault(pid_m,{})["skip_until"]=until; save_state(state)
        sess.setdefault("skipped_moist",[]).append(pid_m)
        await ack("🖐 Sustrato húmedo — saltando")
        if not sess["queue"]:
            txt,kb=screen_timer_summary(sess["completed"],sess["skipped_moist"])
            await edit(chat,mid,txt,kb)
        else:
            nxt=sess["queue"].pop(0); nmins=calc_duration(PLANT_MAP[nxt],temp_c,season,et)
            sess.update({"current":nxt,"mins":nmins,"step":sess["step"]+1,"started_at":now})
            txt,kb=screen_timer_plant(nxt,nmins,sess["step"],sess["total"],now)
            await edit(chat,mid,txt,kb)

    # ── Timer: terminé todo / cancelar ────────────────────────────────────
    elif data=="tdone":
        sess=TIMER_SESSIONS.get(chat)
        if sess:
            if sess.get("current") and sess["current"] not in sess["completed"]:
                sess["completed"].append(sess["current"])
            await ack("✅ Resumen de riego")
            txt,kb=screen_timer_summary(sess["completed"],sess.get("skipped_moist",[]))
            await edit(chat,mid,txt,kb)
        else:
            await ack()

    elif data=="tcancel":
        TIMER_SESSIONS.pop(chat,None)
        await ack("❌ Riego cancelado")
        txt,kb=screen_today(state,temp_c,season,et,soil_r,wx)
        await edit(chat,mid,txt,kb)

    # ── Timer: confirmar riegos ───────────────────────────────────────────
    elif data=="tconfirm":
        sess=TIMER_SESSIONS.pop(chat,{})
        pids=sess.get("completed",[])
        if pids:
            newly=register_watering(state,pids,temp_c,season,et,soil_r,now)
            new_ach=check_achievements(state,meta); save_state(state)
            for a in new_ach: await send(f"🏆 <b>¡LOGRO!</b> {a['name']}\n{a['desc']}")
            await ack(f"✅ {len(newly)} plantas registradas 🎉",alert=True)
        else:
            await ack("Sin riegos que registrar")
        txt,kb=screen_today(state,temp_c,season,et,soil_r,wx)
        await edit(chat,mid,txt,kb)

    else:
        await ack()  # unknown callback — dismiss spinner

# ─── MESSAGE HANDLER ──────────────────────────────────────────────────────────

async def handle_msg(update:dict):
    msg=update.get("message",{}); text=msg.get("text","").strip()
    chat=str(msg.get("chat",{}).get("id",""))
    if not any(text.startswith(c) for c in ["/start","/menu","/hoy"]): return
    wx=await get_weather(); state=load_state()
    get_meta(state); save_state(state)  # ensure meta exists
    txt,kb=screen_today(state,wx.get("temp_c"),get_season(),
                        et_factor(wx.get("temp_c"),wx.get("humidity"),wx.get("wind_ms",0)),
                        recent_rain(state),wx)
    await send(txt,kb,chat=chat)

# ─── POLL ─────────────────────────────────────────────────────────────────────

async def poll():
    offset=None; logging.info("Polling v7")
    while True:
        try:
            params={"timeout":20,"allowed_updates":["message","callback_query"]}
            if offset: params["offset"]=offset
            async with httpx.AsyncClient(timeout=30) as cl:
                data=(await cl.get(f"{API}/getUpdates",params=params)).json()
            for upd in data.get("result",[]):
                offset=upd["update_id"]+1
                try:
                    if "callback_query" in upd: await handle_cb(upd)
                    elif "message" in upd: await handle_msg(upd)
                except Exception as e: logging.error(f"Handler: {e}")
        except Exception as e:
            logging.warning(f"Poll: {e}"); await asyncio.sleep(5)

# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    global VOLUME_OK
    logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s")
    VOLUME_OK=verify_volume()
    if not VOLUME_OK: logging.error("⚠️ /data no disponible.")

    sched=AsyncIOScheduler(timezone=TUCSON_TZ)
    sched.add_job(evening_check,"cron",hour=20,minute=0,id="evening")
    sched.add_job(weekly_summary,"cron",day_of_week="sun",hour=9,minute=0,id="weekly")
    sched.start()

    wx=await get_weather(); state=load_state(); get_meta(state); save_state(state)
    txt,kb=screen_today(state,wx.get("temp_c"),get_season(),
                        et_factor(wx.get("temp_c"),wx.get("humidity"),wx.get("wind_ms",0)),
                        recent_rain(state),wx)
    await send(f"🌵 <b>Tucson Garden v7</b> · {len(PLANTS)} plantas · Volume {'✅' if VOLUME_OK else '⚠️'}\n\n"+txt,kb)
    logging.info(f"v7 arrancado — {len(PLANTS)} plantas")
    await poll()

if __name__=="__main__":
    asyncio.run(main())
