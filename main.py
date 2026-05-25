# ═══════════════════════════════════════════════════════════════
#  ☣️  БИО-ВОЙНЫ + РП СИСТЕМА  —  Telegram Bot  v4.0
#  Стек: Python 3.11, aiogram 3.7, aiosqlite
# ═══════════════════════════════════════════════════════════════

import asyncio, logging, os, random, string, datetime, json
from typing import Optional

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatType
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    Message, BotCommand,
)
from aiohttp import web

# ───────────────────────────────────────────────────────────────
#  КОНФИГ
# ───────────────────────────────────────────────────────────────

BOT_TOKEN      = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "866169035"))
PORT           = int(os.getenv("PORT", "8080"))
DB_PATH        = "biowar.db"
RENDER_URL     = os.getenv("RENDER_EXTERNAL_URL", "")

FEVER_HEAL_COST = 50.0
FEVER_DURATION  = 3600
VIP_COST_URAN   = 70

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────────────────────
#  РАНГИ ИГРОКОВ
# ───────────────────────────────────────────────────────────────

PLAYER_RANKS = [
    (0,      "🪖 Курсант"),
    (100,    "🔬 Лаборант"),
    (300,    "🧪 Младший учёный"),
    (700,    "🧫 Учёный"),
    (1500,   "⚗️ Старший учёный"),
    (3000,   "🦠 Вирусолог"),
    (6000,   "☣️ Эпидемиолог"),
    (12000,  "💀 Мастер заражения"),
    (25000,  "🧬 Профессор биологии"),
    (50000,  "🌍 Учёный Всевышнего класса"),
]

def get_rank(exp: int) -> str:
    rank = PLAYER_RANKS[0][1]
    for threshold, name in PLAYER_RANKS:
        if exp >= threshold:
            rank = name
    return rank

def get_next_rank(exp: int):
    for threshold, name in PLAYER_RANKS:
        if exp < threshold:
            return threshold, name
    return None, None

# ───────────────────────────────────────────────────────────────
#  РАНГИ КОРПОРАЦИЙ
# ───────────────────────────────────────────────────────────────

CORP_RANKS = [
    (0,   "🏚 Стартап"),
    (3,   "🏢 Малая корпорация"),
    (7,   "🏬 Корпорация"),
    (15,  "🏛 Крупная корпорация"),
    (30,  "🌐 Мегакорпорация"),
    (60,  "⚡ Элитная корпорация"),
    (100, "🌌 Небесная корпорация"),
]

def get_corp_rank(members: int) -> str:
    rank = CORP_RANKS[0][1]
    for threshold, name in CORP_RANKS:
        if members >= threshold:
            rank = name
    return rank

# ───────────────────────────────────────────────────────────────
#  УРОВНИ АДМИНИСТРАЦИИ
# ───────────────────────────────────────────────────────────────

ADMIN_TITLES = {
    0: "",
    1: "🎓 Стажёр",
    2: "📋 Младший администратор",
    3: "⚙️ Администратор",
    4: "🔱 Старший администратор",
    5: "👑 Со-владелец",
    9: "👨‍💻 Владелец",
}

# ───────────────────────────────────────────────────────────────
#  РП — ТРИГГЕРЫ И ДЕЙСТВИЯ
# ───────────────────────────────────────────────────────────────

RP_TRIGGERS = {
    "кусь":       ["{a} укусил {b} за ушко 🦷", "{a} тихонько куснул {b} 😈", "{a} вцепился в {b}! 🦷"],
    "обнять":     ["{a} крепко обнял {b} 🤗", "{a} нежно обнял {b} 💕", "{a} стиснул {b} в объятиях"],
    "погладить":  ["{a} погладил {b} по голове 🥰", "{a} нежно погладил {b} ✋"],
    "ударить":    ["{a} ударил {b} 👊", "{a} врезал {b} со всей силы! 💥"],
    "поцеловать": ["{a} поцеловал {b} в щёчку 😘", "{a} поцеловал {b} 💋"],
    "укусить":    ["{a} укусил {b}! 🦷😤", "{a} больно укусил {b} за руку 🦷"],
    "шлёпнуть":   ["{a} шлёпнул {b} 👋", "{a} звонко шлёпнул {b}! 😳"],
    "пнуть":      ["{a} пнул {b} 🦵", "{a} пнул {b} под зад 🦵💨"],
    "лизнуть":    ["{a} лизнул {b} 👅😝", "{a} лизнул {b} в нос 😜"],
    "потрепать":  ["{a} потрепал {b} за щёку 😄"],
}

RP_VIP_ACTIONS = {
    "изнасиловать": ["{a} изнасиловал {b} 😈🔞", "{a} надругался над {b} 🔞"],
    "надругаться":  ["{a} надругался над {b} 🔞", "{a} извратился над {b} 🔞"],
    "раздеть":      ["{a} раздел {b} догола 🔞😳", "{a} сорвал одежду с {b} 🔞"],
    "трахнуть":     ["{a} трахнул {b} 🔞🔥", "{a} занялся сексом с {b} 🔞"],
    "связать":      ["{a} связал {b} верёвкой 🪢🔞", "{a} связал {b} и сделал своим рабом 🔞"],
    "доминировать": ["{a} доминирует над {b} 👑🔞", "{a} взял {b} под полный контроль 🔞"],
}

# ───────────────────────────────────────────────────────────────
#  KEEP-ALIVE + АНТИСОН
# ───────────────────────────────────────────────────────────────

async def health(request):
    return web.Response(text="OK")

async def start_web():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Keep-alive на порту {PORT}")

async def self_ping():
    if not RENDER_URL:
        logger.info("RENDER_EXTERNAL_URL не задан — самопинг отключён")
        return
    import aiohttp as _ah
    await asyncio.sleep(30)
    while True:
        try:
            async with _ah.ClientSession() as s:
                async with s.get(f"{RENDER_URL}/health",
                                 timeout=_ah.ClientTimeout(total=10)) as r:
                    logger.info(f"Self-ping: {r.status}")
        except Exception as e:
            logger.warning(f"Self-ping fail: {e}")
        await asyncio.sleep(240)

# ───────────────────────────────────────────────────────────────
#  БАЗА ДАННЫХ
# ───────────────────────────────────────────────────────────────

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id             INTEGER PRIMARY KEY,
                username            TEXT,
                full_name           TEXT,
                lab_name            TEXT    DEFAULT 'Лаборатория',
                lab_id              TEXT    UNIQUE,
                pathogen_name       TEXT    DEFAULT 'засекречено',
                infection           INTEGER DEFAULT 1,
                immunity            INTEGER DEFAULT 1,
                lethality           INTEGER DEFAULT 1,
                security            INTEGER DEFAULT 1,
                scientist_level     INTEGER DEFAULT 1,
                pathogens_ready     INTEGER DEFAULT 3,
                pathogens_max       INTEGER DEFAULT 3,
                pathogen_slots      INTEGER DEFAULT 3,
                last_pathogen_at    TIMESTAMP DEFAULT NULL,
                bio_exp             INTEGER DEFAULT 0,
                bio_resource        REAL    DEFAULT 100.0,
                uran                REAL    DEFAULT 0.0,
                is_vip              INTEGER DEFAULT 0,
                vip_until           TIMESTAMP DEFAULT NULL,
                operations_success  INTEGER DEFAULT 0,
                operations_total    INTEGER DEFAULT 0,
                prevented_success   INTEGER DEFAULT 0,
                prevented_total     INTEGER DEFAULT 0,
                infected_count      INTEGER DEFAULT 0,
                diseases_count      INTEGER DEFAULT 1,
                corp_id             INTEGER DEFAULT NULL,
                is_banned           INTEGER DEFAULT 0,
                event_immunity      INTEGER DEFAULT 0,
                is_infected         INTEGER DEFAULT 0,
                fever_until         TIMESTAMP DEFAULT NULL,
                infected_until      TIMESTAMP DEFAULT NULL,
                infected_by         INTEGER DEFAULT NULL,
                admin_level         INTEGER DEFAULT 0,
                admin_title         TEXT    DEFAULT '',
                is_hidden           INTEGER DEFAULT 0,
                created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        migrations = [
            ("uran",           "REAL DEFAULT 0.0"),
            ("is_vip",         "INTEGER DEFAULT 0"),
            ("vip_until",      "TIMESTAMP DEFAULT NULL"),
            ("pathogen_slots",  "INTEGER DEFAULT 3"),
            ("scientist_level","INTEGER DEFAULT 1"),
            ("pathogens_ready","INTEGER DEFAULT 3"),
            ("pathogens_max",  "INTEGER DEFAULT 3"),
            ("last_pathogen_at","TIMESTAMP DEFAULT NULL"),
            ("is_infected",    "INTEGER DEFAULT 0"),
            ("fever_until",    "TIMESTAMP DEFAULT NULL"),
            ("infected_until", "TIMESTAMP DEFAULT NULL"),
            ("infected_by",    "INTEGER DEFAULT NULL"),
            ("admin_level",    "INTEGER DEFAULT 0"),
            ("admin_title",    "TEXT DEFAULT ''"),
            ("is_hidden",      "INTEGER DEFAULT 0"),
            ("corp_id",        "INTEGER DEFAULT NULL"),
        ]
        for col, defn in migrations:
            try:
                await db.execute(f"ALTER TABLE players ADD COLUMN {col} {defn}")
            except Exception:
                pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS corporations (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT UNIQUE,
                tag           TEXT UNIQUE,
                leader_id     INTEGER,
                description   TEXT    DEFAULT '',
                members_count INTEGER DEFAULT 1,
                bio_resource  REAL    DEFAULT 0.0,
                bio_exp       INTEGER DEFAULT 0,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            await db.execute("ALTER TABLE corporations ADD COLUMN bio_exp INTEGER DEFAULT 0")
        except Exception:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                code         TEXT UNIQUE,
                reward_type  TEXT,
                reward_amount REAL,
                max_uses     INTEGER DEFAULT 1,
                uses         INTEGER DEFAULT 0,
                is_active    INTEGER DEFAULT 1,
                created_by   INTEGER,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_uses (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                code       TEXT,
                user_id    INTEGER,
                used_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id     INTEGER PRIMARY KEY,
                admin_level INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT, title TEXT, description TEXT,
                payload TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1,
                ends_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attack_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attacker_id INTEGER, target_id INTEGER,
                success INTEGER, atk_roll INTEGER, def_roll INTEGER,
                reward REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS upgrade_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, skill TEXT, amount INTEGER, cost REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promote_requests (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_id INTEGER,
                target_id    INTEGER,
                target_level INTEGER,
                reason       TEXT,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

# ── Игроки ─────────────────────────────────────────────────────

async def get_player(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM players WHERE user_id=?", (user_id,)) as c:
            r = await c.fetchone()
            return dict(r) if r else None

async def get_player_by_username(username: str) -> Optional[dict]:
    uname = username.lstrip("@").lower()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM players WHERE LOWER(username)=?", (uname,)) as c:
            r = await c.fetchone()
            return dict(r) if r else None

async def create_player(user_id, username, full_name):
    lab_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO players
            (user_id,username,full_name,lab_id,lab_name,pathogen_name)
            VALUES (?,?,?,?,?,?)
        """, (user_id, username, full_name, lab_id,
              f"Лаборатория #{lab_id[:4]}", "засекречено"))
        await db.commit()
    return await get_player(user_id)

async def get_or_create(user_id, username, full_name):
    p = await get_player(user_id)
    return p or await create_player(user_id, username, full_name)

async def update_player(user_id, **kw):
    if not kw: return
    fields = ", ".join(f"{k}=?" for k in kw)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE players SET {fields} WHERE user_id=?",
            [*kw.values(), user_id])
        await db.commit()

async def is_banned(uid):
    p = await get_player(uid)
    return bool(p and p["is_banned"])

async def get_admin_level(uid: int) -> int:
    if uid == SUPER_ADMIN_ID:
        return 9
    p = await get_player(uid)
    return p.get("admin_level", 0) if p else 0

async def is_admin(uid: int, min_level: int = 1) -> bool:
    return await get_admin_level(uid) >= min_level

async def set_admin_level(uid: int, level: int):
    await update_player(uid, admin_level=level)
    async with aiosqlite.connect(DB_PATH) as db:
        if level > 0:
            await db.execute(
                "INSERT OR REPLACE INTO admins(user_id,admin_level) VALUES(?,?)",
                (uid, level))
        else:
            await db.execute("DELETE FROM admins WHERE user_id=?", (uid,))
        await db.commit()

async def get_all_players():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM players") as c:
            return [dict(r) for r in await c.fetchall()]

async def get_top_players(limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM players
            WHERE is_banned=0 AND is_hidden=0
            ORDER BY bio_exp DESC LIMIT ?
        """, (limit,)) as c:
            return [dict(r) for r in await c.fetchall()]

def is_vip_active(p: dict) -> bool:
    if not p.get("is_vip"): return False
    if not p.get("vip_until"): return True
    try:
        return datetime.datetime.utcnow() < datetime.datetime.fromisoformat(str(p["vip_until"]))
    except Exception:
        return False

# ── Корпорации ─────────────────────────────────────────────────

async def get_corp(corp_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM corporations WHERE id=?", (corp_id,)) as c:
            r = await c.fetchone()
            return dict(r) if r else None

async def get_corp_by_tag(tag: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM corporations WHERE LOWER(tag)=?", (tag.lower(),)) as c:
            r = await c.fetchone()
            return dict(r) if r else None

async def get_corp_by_name(name: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM corporations WHERE LOWER(name)=?", (name.lower(),)) as c:
            r = await c.fetchone()
            return dict(r) if r else None

async def create_corp(name: str, tag: str, leader_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO corporations (name,tag,leader_id) VALUES (?,?,?)",
                (name, tag, leader_id))
            await db.commit()
        except Exception:
            return None
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM corporations WHERE leader_id=? ORDER BY id DESC LIMIT 1",
            (leader_id,)) as c:
            r = await c.fetchone()
            return dict(r) if r else None

async def get_top_corps(limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM corporations ORDER BY bio_exp DESC, members_count DESC LIMIT ?",
            (limit,)) as c:
            return [dict(r) for r in await c.fetchall()]

# ── Промокоды ──────────────────────────────────────────────────

async def get_promo(code: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM promocodes WHERE code=? AND is_active=1", (code.upper(),)) as c:
            r = await c.fetchone()
            return dict(r) if r else None

async def promo_already_used(code: str, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM promo_uses WHERE code=? AND user_id=?",
            (code.upper(), user_id)) as c:
            return await c.fetchone() is not None

async def use_promo(code: str, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO promo_uses (code,user_id) VALUES (?,?)",
            (code.upper(), user_id))
        await db.execute(
            "UPDATE promocodes SET uses=uses+1 WHERE code=?", (code.upper(),))
        await db.commit()
    promo = await get_promo(code)
    if promo and promo["max_uses"] > 0 and promo["uses"] >= promo["max_uses"]:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE promocodes SET is_active=0 WHERE code=?", (code.upper(),))
            await db.commit()

async def create_promo(code: str, reward_type: str, reward_amount: float,
                       max_uses: int, created_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO promocodes (code,reward_type,reward_amount,max_uses,created_by)"
                " VALUES (?,?,?,?,?)",
                (code.upper(), reward_type, reward_amount, max_uses, created_by))
            await db.commit()
            return True
        except Exception:
            return False

async def get_all_promos():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM promocodes ORDER BY created_at DESC") as c:
            return [dict(r) for r in await c.fetchall()]

# ── События ────────────────────────────────────────────────────

async def create_event(etype, title, description, payload, hours):
    ends_at = datetime.datetime.utcnow() + datetime.timedelta(hours=hours)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO events (type,title,description,payload,ends_at) VALUES (?,?,?,?,?)",
            (etype, title, description, payload, ends_at))
        await db.commit()

async def deactivate_event(eid):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE events SET is_active=0 WHERE id=?", (eid,))
        await db.commit()

async def get_active_events():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM events WHERE is_active=1") as c:
            return [dict(r) for r in await c.fetchall()]

async def log_attack(attacker_id, target_id, success, atk_roll, def_roll, reward=0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO attack_log (attacker_id,target_id,success,atk_roll,def_roll,reward)"
            " VALUES (?,?,?,?,?,?)",
            (attacker_id, target_id, success, atk_roll, def_roll, reward))
        await db.commit()

# ───────────────────────────────────────────────────────────────
#  ПАТОГЕНЫ
# ───────────────────────────────────────────────────────────────

def pathogen_interval(scientist_level: int) -> int:
    return max(60, 1800 - (scientist_level - 1) * 193)

async def refresh_pathogens(p: dict) -> dict:
    if p["pathogens_ready"] >= p["pathogens_max"]:
        return p
    if not p.get("last_pathogen_at"):
        await update_player(p["user_id"],
                            last_pathogen_at=datetime.datetime.utcnow().isoformat())
        return await get_player(p["user_id"])
    interval = pathogen_interval(p["scientist_level"])
    now      = datetime.datetime.utcnow()
    last     = datetime.datetime.fromisoformat(str(p["last_pathogen_at"]))
    elapsed  = (now - last).total_seconds()
    gained   = int(elapsed // interval)
    if gained > 0:
        new_ready = min(p["pathogens_ready"] + gained, p["pathogens_max"])
        leftover  = elapsed - gained * interval
        new_last  = (now - datetime.timedelta(seconds=leftover)).isoformat()
        await update_player(p["user_id"],
                            pathogens_ready=new_ready,
                            last_pathogen_at=new_last)
        return await get_player(p["user_id"])
    return p

def pathogen_timer_str(p: dict) -> str:
    if p["pathogens_ready"] >= p["pathogens_max"]:
        return "полный запас"
    interval = pathogen_interval(p["scientist_level"])
    if not p.get("last_pathogen_at"):
        return f"{interval//60}м"
    last    = datetime.datetime.fromisoformat(str(p["last_pathogen_at"]))
    elapsed = (datetime.datetime.utcnow() - last).total_seconds()
    rem     = max(0, interval - (elapsed % interval))
    m, s    = divmod(int(rem), 60)
    return f"{m}м {s}с"

# ───────────────────────────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ───────────────────────────────────────────────────────────────

def fever_active(p: dict) -> bool:
    if not p.get("fever_until"): return False
    try:
        return datetime.datetime.utcnow() < datetime.datetime.fromisoformat(str(p["fever_until"]))
    except Exception:
        return False

def infected_active(p: dict) -> bool:
    if not p.get("is_infected") or not p.get("infected_until"): return False
    try:
        return datetime.datetime.utcnow() < datetime.datetime.fromisoformat(str(p["infected_until"]))
    except Exception:
        return False

def infect_chance(attacker: dict, target: dict) -> float:
    if target.get("event_immunity"): return 0.01
    atk   = attacker["infection"]
    def_  = target["immunity"] + target["security"]
    ratio = atk / max(def_, 1)
    if ratio >= 2.0:    return 0.85
    elif ratio >= 1.5:  return 0.65
    elif ratio >= 1.0:  return 0.45
    elif ratio >= 0.75: return 0.25
    elif ratio >= 0.5:  return 0.10
    else:               return 0.03

def fever_seconds(attacker: dict) -> int:
    return min(FEVER_DURATION + attacker.get("lethality", 1) * 1800, 86400)

def infected_seconds(attacker: dict) -> int:
    return min(3600 + attacker.get("lethality", 1) * 3600, 86400)

def player_display_title(p: dict) -> str:
    lvl = p.get("admin_level", 0)
    if lvl >= 1:
        custom = p.get("admin_title", "")
        return custom if custom else ADMIN_TITLES.get(lvl, "")
    return ""

def is_group(msg: Message) -> bool:
    return msg.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)

async def reply_or_dm(msg: Message, bot: Bot, text: str, **kwargs):
    if is_group(msg):
        try:
            return await msg.reply(text, **kwargs)
        except Exception:
            pass
    return await msg.answer(text, **kwargs)

# ───────────────────────────────────────────────────────────────
#  ЦЕНЫ ПРОКАЧКИ
# ───────────────────────────────────────────────────────────────

def upgrade_cost(skill: str, level: int) -> float:
    base = {
        "infection":       80.0,
        "immunity":        120.0,
        "security":        90.0,
        "lethality":       60.0,
        "scientist_level": 50.0,
        "pathogen_slots":  70.0,
    }
    mult = {
        "infection":       2.0,
        "immunity":        2.2,
        "security":        1.9,
        "lethality":       1.7,
        "scientist_level": 1.8,
        "pathogen_slots":  1.8,
    }
    b = base.get(skill, 50.0)
    m = mult.get(skill, 1.8)
    return round(b * (m ** (level - 1)), 1)

UPGRADE_LABELS = {
    "infection":       "🦠 Заразность",
    "immunity":        "🛡 Иммунитет",
    "lethality":       "☠️ Летальность",
    "security":        "🔒 Безопасность",
    "scientist_level": "🔭 Квалификация",
    "pathogen_slots":  "🧫 Слоты патогенов",
}

# ───────────────────────────────────────────────────────────────
#  FSM STATES
# ───────────────────────────────────────────────────────────────

router = Router()

class S(StatesGroup):
    corp_name        = State()
    corp_tag         = State()
    rename_lab       = State()
    rename_pathogen  = State()
    event_hours      = State()
    event_bonus      = State()
    event_count      = State()
    broadcast_text   = State()
    promote_reason   = State()
    # Промокоды
    promo_code_input = State()
    promo_create_code   = State()
    promo_create_type   = State()
    promo_create_amount = State()
    promo_create_uses   = State()
    # Прокачка через команду
    upgrade_confirm  = State()

# ───────────────────────────────────────────────────────────────
#  КЛАВИАТУРЫ
# ───────────────────────────────────────────────────────────────

def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧫 Лаборатория", callback_data="menu_lab"),
            InlineKeyboardButton(text="📋 Профиль",     callback_data="menu_profile"),
        ],
        [
            InlineKeyboardButton(text="☣️ Заразить",    callback_data="menu_infect_help"),
            InlineKeyboardButton(text="🏆 Топ",          callback_data="menu_top"),
        ],
        [
            InlineKeyboardButton(text="🏢 Корпорация",   callback_data="menu_corp"),
            InlineKeyboardButton(text="🎭 РП",           callback_data="menu_rp"),
        ],
        [
            InlineKeyboardButton(text="🎟 Промокод",     callback_data="menu_promo"),
            InlineKeyboardButton(text="ℹ️ Помощь",       callback_data="menu_help"),
        ],
    ])

def kb_cancel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

def kb_lab(p: dict):
    interval   = pathogen_interval(p["scientist_level"])
    timer      = pathogen_timer_str(p)
    vip_badge  = "⭐ " if is_vip_active(p) else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚗️ Прокачка",       callback_data="open_upgrade"),
            InlineKeyboardButton(text="✏️ Переименовать",  callback_data="rename_menu"),
        ],
        [
            InlineKeyboardButton(
                text=f"🧪 {p['pathogens_ready']}/{p['pathogens_max']} (⏱{interval//60}м)",
                callback_data="pathogens_info"),
        ],
        [
            InlineKeyboardButton(text=f"{vip_badge}⭐ ВИП", callback_data="vip_info"),
            InlineKeyboardButton(text="🎟 Промокод",        callback_data="menu_promo"),
        ],
        [InlineKeyboardButton(text="◀️ Меню", callback_data="back_main")],
    ])

def kb_upgrade(p: dict):
    def btn(skill):
        cost = upgrade_cost(skill, p[skill])
        lvl  = p[skill]
        return InlineKeyboardButton(
            text=f"{UPGRADE_LABELS[skill].split()[0]} {lvl}→{lvl+1} | {cost:.0f}🧬",
            callback_data=f"upg:{skill}"
        )
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("infection")],
        [btn("immunity")],
        [btn("security")],
        [btn("lethality")],
        [btn("scientist_level")],
        [btn("pathogen_slots")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_lab")],
    ])

def kb_upgrade_legend(p: dict) -> str:
    lines = []
    for skill, label in UPGRADE_LABELS.items():
        lvl  = p[skill]
        cost = upgrade_cost(skill, lvl)
        extra = ""
        if skill == "scientist_level":
            extra = f" (⏱{pathogen_interval(lvl)//60}м→{pathogen_interval(lvl+1)//60}м)"
        if skill == "pathogen_slots":
            extra = f" (слоты: {lvl}→{lvl+1})"
        lines.append(f"{label} {lvl}ур → <b>{cost:.0f} 🧬</b>{extra}")
    return "\n".join(lines)

def kb_fever():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💊 Вылечить за {FEVER_HEAL_COST:.0f} 🧬",
            callback_data="fever_heal")],
        [InlineKeyboardButton(text="⏳ Подождать", callback_data="fever_wait")],
    ])

def kb_rename():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏭 Имя лаборатории", callback_data="rename_lab")],
        [InlineKeyboardButton(text="🦠 Имя патогена",    callback_data="rename_pathogen")],
        [InlineKeyboardButton(text="◀️ Назад",           callback_data="back_to_lab")],
    ])

def kb_corp_actions(p: dict):
    if p.get("corp_id"):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Инфо",   callback_data="corp_info"),
             InlineKeyboardButton(text="🚪 Выйти",  callback_data="corp_leave")],
            [InlineKeyboardButton(text="◀️ Меню",   callback_data="back_main")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать корпорацию", callback_data="corp_create")],
        [InlineKeyboardButton(text="🔍 Вступить по тегу",   callback_data="corp_search")],
        [InlineKeyboardButton(text="◀️ Меню",               callback_data="back_main")],
    ])

def kb_vip():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⭐ Купить ВИП за {VIP_COST_URAN} ☢️ Уран-223",
            callback_data="vip_buy")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_lab")],
    ])

def kb_admin_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика",      callback_data="adm_stats"),
         InlineKeyboardButton(text="☣️ События",         callback_data="adm_events")],
        [InlineKeyboardButton(text="🧬 Выдать ресурсы",  callback_data="adm_give"),
         InlineKeyboardButton(text="☢️ Выдать уран",     callback_data="adm_give_uran")],
        [InlineKeyboardButton(text="🎟 Промокоды",       callback_data="adm_promos"),
         InlineKeyboardButton(text="🔑 Кастом Lab ID",   callback_data="adm_labid")],
        [InlineKeyboardButton(text="📢 Рассылка",        callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="📋 Все команды",     callback_data="adm_help")],
    ])

def kb_promo_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="promo_create")],
        [InlineKeyboardButton(text="📋 Список промокодов", callback_data="promo_list")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_back")],
    ])

# ───────────────────────────────────────────────────────────────
#  СТАРТ
# ───────────────────────────────────────────────────────────────

@router.message(CommandStart())
@router.message(F.text == ".start")
@router.message(F.text == ".старт")
async def cmd_start(msg: Message):
    if await is_banned(msg.from_user.id):
        return await msg.answer("🚫 Вы заблокированы.")
    p    = await get_or_create(msg.from_user.id, msg.from_user.username, msg.from_user.full_name)
    name = msg.from_user.first_name or p["full_name"]
    vip  = "⭐ " if is_vip_active(p) else ""
    await msg.answer(
        f"☣️ <b>БИО-ВОЙНЫ</b> | <b>Spysh</b>\n\n"
        f"Привет, {vip}<b>{name}</b>! 👋\n\n"
        f"🏭 {p['lab_name']}  |  🆔 <code>{p['lab_id']}</code>\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🦠 Развивай патоген\n"
        f"☣️ Заражай соперников\n"
        f"🎭 РП с другими игроками\n"
        f"🏆 Захватывай мир!\n"
        f"━━━━━━━━━━━━━━━━",
        reply_markup=kb_main()
    )

# ── Меню коллбэки ──────────────────────────────────────────────

@router.callback_query(F.data == "back_main")
async def cb_back_main(cb: CallbackQuery):
    p    = await get_or_create(cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
    name = cb.from_user.first_name or p["full_name"]
    vip  = "⭐ " if is_vip_active(p) else ""
    await cb.message.edit_text(
        f"☣️ <b>БИО-ВОЙНЫ</b> | <b>Spysh</b>\n\n"
        f"Привет, {vip}<b>{name}</b>! 👋\n\n"
        f"🏭 {p['lab_name']}  |  🆔 <code>{p['lab_id']}</code>",
        reply_markup=kb_main()
    )
    await cb.answer()

@router.callback_query(F.data == "menu_infect_help")
async def cb_menu_infect_help(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "☣️ <b>Как заразить?</b>\n\n"
        "• Ответь на сообщение жертвы: .заразить\n"
        "• .заразить @username\n"
        "• .заразить 123456789\n\n"
        "🧪 Тратится 1 патоген на атаку"
    )

@router.callback_query(F.data == "menu_top")
async def cb_menu_top(cb: CallbackQuery):
    await cb.answer()
    top    = await get_top_players(10)
    medals = ["🥇","🥈","🥉"] + ["🔹"] * 7
    lines  = ["🏆 <b>ТОП-10 игроков</b>\n"]
    for i, p in enumerate(top):
        name  = p["full_name"] or p["username"] or str(p["user_id"])
        rank  = get_rank(p["bio_exp"])
        title = player_display_title(p)
        vip   = "⭐ " if is_vip_active(p) else ""
        t_str = f" <i>{title}</i>" if title else ""
        lines.append(
            f"{medals[i]} {vip}{name}{t_str}\n"
            f"   {rank} | ☣️ {p['bio_exp']} | 😤 {p['infected_count']}"
        )
    await cb.message.answer(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏢 Топ корпораций", callback_data="top_corps")],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="back_main")],
        ])
    )

@router.callback_query(F.data == "top_corps")
async def cb_top_corps(cb: CallbackQuery):
    await cb.answer()
    top    = await get_top_corps(10)
    medals = ["🥇","🥈","🥉"] + ["🔹"] * 7
    lines  = ["🏢 <b>ТОП-10 корпораций</b>\n"]
    for i, c in enumerate(top):
        cr = get_corp_rank(c["members_count"])
        lines.append(
            f"{medals[i]} <b>[{c['tag']}] {c['name']}</b>\n"
            f"   {cr} | 👥 {c['members_count']} | ☣️ {c['bio_exp']}"
        )
    await cb.message.edit_text(
        "\n".join(lines) if top else "Топ корпораций пуст.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏆 Топ игроков", callback_data="menu_top")],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="back_main")],
        ])
    )

@router.callback_query(F.data == "menu_help")
async def cb_menu_help(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "ℹ️ <b>БИО-ВОЙНЫ — Помощь</b>\n\n"
        "<b>Команды (с точкой):</b>\n"
        ".старт — начать / главное меню\n"
        ".лаб — лаборатория\n"
        ".профиль — профиль\n"
        ".заразить @user — атака\n"
        ".лечение — вылечить горячку\n"
        ".топ — топ игроков\n"
        ".топкорп — топ корпораций\n"
        ".корп — моя корпорация\n"
        ".создатькорп — создать корп.\n"
        ".вступить ТЕГ — вступить\n"
        ".выйти — выйти из корпорации\n"
        ".промокод КОД — активировать\n"
        ".помощь — справка\n"
        ".помощьрп — РП справка\n\n"
        "<b>Прокачка через чат:</b>\n"
        "+заразность 2 — показать цену\n"
        "++заразность 2 — купить",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎭 РП помощь", callback_data="rp_help")],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="back_main")],
        ])
    )

@router.callback_query(F.data == "menu_profile")
async def cb_menu_profile(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    p   = await get_or_create(uid, cb.from_user.username, cb.from_user.full_name)
    p   = await refresh_pathogens(p)
    await _send_profile(cb.message.answer, p)

@router.callback_query(F.data == "menu_lab")
async def cb_menu_lab(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    p   = await get_or_create(uid, cb.from_user.username, cb.from_user.full_name)
    p   = await refresh_pathogens(p)
    await cb.message.answer(_lab_text(p), reply_markup=kb_lab(p))

# ───────────────────────────────────────────────────────────────
#  ЛАБОРАТОРИЯ
# ───────────────────────────────────────────────────────────────

def _lab_text(p: dict) -> str:
    interval = pathogen_interval(p["scientist_level"])
    timer    = pathogen_timer_str(p)
    rank     = get_rank(p["bio_exp"])
    vip_str  = " ⭐ВИП" if is_vip_active(p) else ""
    return (
        f"🏭 <b>{p['lab_name']}</b>{vip_str}\n"
        f"🆔 <code>{p['lab_id']}</code>  |  🔬 <b>{p['pathogen_name']}</b>\n"
        f"🎖 <b>{rank}</b>\n\n"
        f"🔬 <b>НАВЫКИ:</b>\n"
        f"🦠 Заразность: <b>{p['infection']} ур</b>\n"
        f"🛡 Иммунитет: <b>{p['immunity']} ур</b>\n"
        f"☠️ Летальность: <b>{p['lethality']} ур</b>\n"
        f"🔒 Безопасность: <b>{p['security']} ур</b>\n"
        f"🔭 Квалификация учёных: <b>{p['scientist_level']} ур ({interval//60} мин)</b>\n\n"
        f"📊 <b>СТАТИСТИКА:</b>\n"
        f"🧬 Био-Ресурсы: <b>{p['bio_resource']:.1f}</b>\n"
        f"☣️ Био-Опыт: <b>{p['bio_exp']}</b>\n"
        f"☢️ Уран-223: <b>{p['uran']:.1f}</b>\n"
        f"😤 Заражённых: <b>{p['infected_count']}</b>\n\n"
        f"🧪 Патогены: <b>{p['pathogens_ready']}/{p['pathogens_max']}</b>"
        f" (след. через <b>{timer}</b>)"
    )

async def _show_lab(msg: Message, user=None):
    _user = user or msg.from_user
    uid   = _user.id
    if await is_banned(uid): return await msg.answer("🚫 Заблокированы.")
    p = await get_or_create(uid, _user.username, _user.full_name)
    p = await refresh_pathogens(p)
    await msg.answer(_lab_text(p), reply_markup=kb_lab(p))

@router.message(F.text == ".lab")
@router.message(F.text == ".лаб")
@router.message(F.text == ".LAB")
@router.message(F.text == ".ЛАБ")
@router.message(Command("lab"))
async def cmd_lab(msg: Message):
    await _show_lab(msg)

@router.callback_query(F.data == "back_to_lab")
async def cb_back_to_lab(cb: CallbackQuery):
    uid = cb.from_user.id
    p   = await get_or_create(uid, cb.from_user.username, cb.from_user.full_name)
    p   = await refresh_pathogens(p)
    await cb.message.edit_text(_lab_text(p), reply_markup=kb_lab(p))
    await cb.answer()

@router.callback_query(F.data == "pathogens_info")
async def cb_pathogens_info(cb: CallbackQuery):
    p        = await get_or_create(cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
    p        = await refresh_pathogens(p)
    interval = pathogen_interval(p["scientist_level"])
    timer    = pathogen_timer_str(p)
    await cb.answer(
        f"🧪 {p['pathogens_ready']}/{p['pathogens_max']}\n"
        f"⏱ Интервал: {interval//60} мин\n"
        f"🔄 Следующий: {timer}",
        show_alert=True
    )

# ───────────────────────────────────────────────────────────────
#  ПЕРЕИМЕНОВАНИЕ
# ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "rename_menu")
async def cb_rename_menu(cb: CallbackQuery):
    await cb.message.edit_text("✏️ <b>Что переименовать?</b>", reply_markup=kb_rename())
    await cb.answer()

@router.callback_query(F.data == "rename_lab")
async def cb_rename_lab_btn(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("🏭 Введи новое название лаборатории (2–32):", reply_markup=kb_cancel())
    await state.set_state(S.rename_lab)
    await cb.answer()

@router.callback_query(F.data == "rename_pathogen")
async def cb_rename_pathogen_btn(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("🦠 Введи новое название патогена (2–32):", reply_markup=kb_cancel())
    await state.set_state(S.rename_pathogen)
    await cb.answer()

@router.message(S.rename_lab)
async def proc_rename_lab(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if not 2 <= len(name) <= 32:
        return await msg.answer("❌ 2–32 символа.")
    await update_player(msg.from_user.id, lab_name=name)
    await state.clear()
    await msg.answer(f"✅ Лаборатория переименована: <b>{name}</b>")

@router.message(S.rename_pathogen)
async def proc_rename_pathogen(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if not 2 <= len(name) <= 32:
        return await msg.answer("❌ 2–32 символа.")
    await update_player(msg.from_user.id, pathogen_name=name)
    await state.clear()
    await msg.answer(f"✅ Патоген переименован: <b>{name}</b>")

# ───────────────────────────────────────────────────────────────
#  ПРОКАЧКА — inline + текстовые команды (+навык)
# ───────────────────────────────────────────────────────────────

SKILL_ALIASES = {
    "заразность":  "infection",
    "иммунитет":   "immunity",
    "защита":      "security",
    "безопасность":"security",
    "летальность": "lethality",
    "учёные":      "scientist_level",
    "ученые":      "scientist_level",
    "патогены":    "pathogen_slots",
}

@router.callback_query(F.data == "open_upgrade")
async def cb_open_upgrade(cb: CallbackQuery):
    p = await get_or_create(cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
    await cb.message.edit_text(
        f"⚗️ <b>Прокачка</b>\n🧬 Ресурсы: <b>{p['bio_resource']:.1f}</b>\n\n"
        + kb_upgrade_legend(p) +
        "\n\nНажми кнопку навыка:",
        reply_markup=kb_upgrade(p)
    )
    await cb.answer()

@router.callback_query(F.data.startswith("upg:"))
async def cb_upgrade(cb: CallbackQuery):
    uid   = cb.from_user.id
    if await is_banned(uid): return await cb.answer("🚫", show_alert=True)
    skill = cb.data.split(":")[1]
    p     = await get_player(uid)
    level = p[skill]
    cost  = upgrade_cost(skill, level)
    if p["bio_resource"] < cost:
        return await cb.answer(f"❌ Нужно {cost:.0f}🧬, у тебя {p['bio_resource']:.1f}", show_alert=True)
    new_max = p["pathogens_max"]
    if skill == "pathogen_slots":
        new_max = level + 1
    await update_player(uid,
        **{skill: level + 1},
        bio_resource=p["bio_resource"] - cost,
        pathogens_max=new_max if skill == "pathogen_slots" else p["pathogens_max"]
    )
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO upgrade_log (user_id,skill,amount,cost) VALUES (?,?,?,?)",
            (uid, skill, 1, cost))
        await db.commit()
    await cb.answer(f"✅ {UPGRADE_LABELS[skill]} → {level+1} ур!", show_alert=True)
    p2 = await get_player(uid)
    await cb.message.edit_text(
        f"⚗️ <b>Прокачка</b>\n🧬 Ресурсы: <b>{p2['bio_resource']:.1f}</b>\n\n"
        + kb_upgrade_legend(p2) +
        "\n\nНажми кнопку навыка:",
        reply_markup=kb_upgrade(p2)
    )

# Текстовая прокачка: +заразность 1 и ++заразность 1
@router.message(F.text.regexp(r"^\+\+(.+?)\s+(\d+)$"))
async def cmd_upgrade_confirm(msg: Message):
    import re
    m = re.match(r"^\+\+(.+?)\s+(\d+)$", msg.text.strip())
    if not m: return
    skill_name = m.group(1).lower().strip()
    amount     = int(m.group(2))
    skill = SKILL_ALIASES.get(skill_name)
    if not skill:
        return await msg.answer("❌ Неизвестный навык. Напиши .помощь")
    if not 1 <= amount <= 10:
        return await msg.answer("❌ Количество от 1 до 10.")
    uid = msg.from_user.id
    p   = await get_player(uid)
    if not p: return
    total_cost = 0.0
    current    = p[skill]
    for i in range(amount):
        total_cost += upgrade_cost(skill, current + i)
    if p["bio_resource"] < total_cost:
        return await msg.answer(
            f"❌ Нужно <b>{total_cost:.1f} 🧬</b>, у тебя <b>{p['bio_resource']:.1f}</b>"
        )
    new_level = current + amount
    new_max   = p["pathogens_max"]
    if skill == "pathogen_slots":
        new_max = new_level
    await update_player(uid,
        **{skill: new_level},
        bio_resource=p["bio_resource"] - total_cost,
        pathogens_max=new_max if skill == "pathogen_slots" else p["pathogens_max"]
    )
    await msg.answer(
        f"✅ <b>{UPGRADE_LABELS[skill]}</b> прокачана!\n"
        f"{current} → <b>{new_level}</b> ур\n"
        f"Потрачено: <b>{total_cost:.1f} 🧬</b>"
    )

@router.message(F.text.regexp(r"^\+(?!\+)(.+?)\s+(\d+)$"))
async def cmd_upgrade_preview(msg: Message):
    import re
    m = re.match(r"^\+(?!\+)(.+?)\s+(\d+)$", msg.text.strip())
    if not m: return
    skill_name = m.group(1).lower().strip()
    amount     = int(m.group(2))
    skill = SKILL_ALIASES.get(skill_name)
    if not skill:
        return await msg.answer("❌ Неизвестный навык.\nДоступно: заразность, иммунитет, защита, летальность, учёные, патогены")
    if not 1 <= amount <= 10:
        return await msg.answer("❌ Количество от 1 до 10.")
    uid = msg.from_user.id
    p   = await get_player(uid)
    if not p: p = await get_or_create(uid, msg.from_user.username, msg.from_user.full_name)
    current    = p[skill]
    total_cost = sum(upgrade_cost(skill, current + i) for i in range(amount))
    await msg.answer(
        f"⚗️ <b>Подтверждение прокачки</b>\n\n"
        f"Навык: <b>{UPGRADE_LABELS[skill]}</b>\n"
        f"Уровень: <b>{current}</b> → <b>{current+amount}</b>\n"
        f"Стоимость: <b>{total_cost:.1f} 🧬</b>\n"
        f"Твой баланс: <b>{p['bio_resource']:.1f} 🧬</b>\n\n"
        f"Для подтверждения напиши:\n"
        f"<code>++{skill_name} {amount}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ Купить за {total_cost:.0f}🧬",
                callback_data=f"upg_quick:{skill}:{amount}"
            )],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_silent")],
        ])
    )

@router.callback_query(F.data.startswith("upg_quick:"))
async def cb_upg_quick(cb: CallbackQuery):
    _, skill, amt_str = cb.data.split(":")
    amount = int(amt_str)
    uid    = cb.from_user.id
    p      = await get_player(uid)
    if not p: return await cb.answer("❌", show_alert=True)
    current    = p[skill]
    total_cost = sum(upgrade_cost(skill, current + i) for i in range(amount))
    if p["bio_resource"] < total_cost:
        return await cb.answer(f"❌ Нужно {total_cost:.1f}🧬", show_alert=True)
    new_level = current + amount
    new_max   = p["pathogens_max"]
    if skill == "pathogen_slots":
        new_max = new_level
    await update_player(uid,
        **{skill: new_level},
        bio_resource=p["bio_resource"] - total_cost,
        pathogens_max=new_max if skill == "pathogen_slots" else p["pathogens_max"]
    )
    await cb.answer(f"✅ {UPGRADE_LABELS[skill]} → {new_level} ур!", show_alert=True)
    await cb.message.edit_text(
        f"✅ <b>Прокачано!</b>\n"
        f"{UPGRADE_LABELS[skill]}: <b>{current}</b> → <b>{new_level}</b>\n"
        f"Потрачено: <b>{total_cost:.1f} 🧬</b>"
    )

@router.callback_query(F.data == "cancel_silent")
async def cb_cancel_silent(cb: CallbackQuery):
    await cb.message.delete()
    await cb.answer()

# ───────────────────────────────────────────────────────────────
#  ПРОФИЛЬ
# ───────────────────────────────────────────────────────────────

async def _send_profile(answer_func, p: dict):
    rank           = get_rank(p["bio_exp"])
    next_t, next_r = get_next_rank(p["bio_exp"])
    next_str       = f"\n📈 До <b>{next_r}</b>: <b>{next_t - p['bio_exp']}</b> оп." if next_r else ""
    has_fever      = fever_active(p)
    is_inf         = infected_active(p)
    fever_str      = infected_str = ""
    if has_fever:
        fu  = datetime.datetime.fromisoformat(str(p["fever_until"]))
        rem = int((fu - datetime.datetime.utcnow()).total_seconds())
        h, m = divmod(rem // 60, 60)
        fever_str = f"\n🤒 <b>Горячка:</b> {h}ч {m}мин (.лечение)"
    if is_inf:
        iu  = datetime.datetime.fromisoformat(str(p["infected_until"]))
        rem = int((iu - datetime.datetime.utcnow()).total_seconds())
        h, m = divmod(rem // 60, 60)
        infected_str = f"\n☣️ <b>Заражён:</b> {h}ч {m}мин"
    corp_str  = ""
    if p.get("corp_id"):
        corp = await get_corp(p["corp_id"])
        if corp: corp_str = f"\n🏢 <b>[{corp['tag']}] {corp['name']}</b>"
    title_str = ""
    t = player_display_title(p)
    if t: title_str = f"\n{t}"
    vip_str   = "\n⭐ <b>ВИП активен</b>" if is_vip_active(p) else ""
    ops_pct   = 0 if not p["operations_total"]  else round(p["operations_success"]/p["operations_total"]*100,1)
    prev_pct  = 0 if not p["prevented_total"]   else round(p["prevented_success"]/p["prevented_total"]*100,1)
    await answer_func(
        f"👤 <b>{p['full_name']}</b> (@{p['username'] or '—'}){title_str}{corp_str}{vip_str}\n"
        f"🏭 <b>{p['lab_name']}</b>  |  🆔 <code>{p['lab_id']}</code>\n"
        f"🔬 Патоген: <b>{p['pathogen_name']}</b>\n"
        f"🎖 Ранг: <b>{rank}</b>{next_str}\n\n"
        f"🔬 <b>НАВЫКИ:</b>\n"
        f"🦠 Заразность: <b>{p['infection']} ур</b>\n"
        f"🛡 Иммунитет: <b>{p['immunity']} ур</b>\n"
        f"☠️ Летальность: <b>{p['lethality']} ур</b>\n"
        f"🔒 Безопасность: <b>{p['security']} ур</b>\n\n"
        f"📊 <b>СТАТИСТИКА:</b>\n"
        f"☣️ Био-Опыт: <b>{p['bio_exp']}</b>\n"
        f"🧬 Био-Ресурсы: <b>{p['bio_resource']:.1f}</b>\n"
        f"☢️ Уран-223: <b>{p['uran']:.1f}</b>\n"
        f"😷 Операций: <b>{p['operations_success']}/{p['operations_total']} ({ops_pct}%)</b>\n"
        f"🥷 Отражено: <b>{p['prevented_success']}/{p['prevented_total']} ({prev_pct}%)</b>\n"
        f"😤 Заражённых: <b>{p['infected_count']}</b>\n"
        f"🧪 Патогены: <b>{p['pathogens_ready']}/{p['pathogens_max']}</b>"
        f"{fever_str}{infected_str}"
    )

@router.message(F.text == ".profile")
@router.message(F.text == ".профиль")
@router.message(Command("profile"))
async def cmd_profile(msg: Message):
    if await is_banned(msg.from_user.id): return await msg.answer("🚫")
    p = await get_or_create(msg.from_user.id, msg.from_user.username, msg.from_user.full_name)
    p = await refresh_pathogens(p)
    await _send_profile(msg.answer, p)

# ───────────────────────────────────────────────────────────────
#  ВИП
# ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "vip_info")
async def cb_vip_info(cb: CallbackQuery):
    uid = cb.from_user.id
    p   = await get_player(uid)
    vip = is_vip_active(p)
    text = (
        f"⭐ <b>ВИП статус</b>\n\n"
        f"{'✅ У тебя активен ВИП!' if vip else '❌ ВИП не активен'}\n\n"
        f"<b>Преимущества ВИП:</b>\n"
        f"🎭 Доступ к 18+ РП командам\n"
        f"⭐ Значок ВИП в профиле и топе\n"
        f"🔓 Специальные РП триггеры\n\n"
        f"<b>Стоимость:</b> {VIP_COST_URAN} ☢️ Уран-223\n"
        f"<b>Твой Уран-223:</b> {p['uran']:.1f} ☢️"
    )
    await cb.message.edit_text(text, reply_markup=kb_vip() if not vip else
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_lab")]
        ])
    )
    await cb.answer()

@router.callback_query(F.data == "vip_buy")
async def cb_vip_buy(cb: CallbackQuery):
    uid = cb.from_user.id
    p   = await get_player(uid)
    if is_vip_active(p):
        return await cb.answer("✅ ВИП уже активен!", show_alert=True)
    if p["uran"] < VIP_COST_URAN:
        return await cb.answer(
            f"❌ Нужно {VIP_COST_URAN} ☢️ Уран-223\nУ тебя: {p['uran']:.1f}",
            show_alert=True
        )
    await update_player(uid, uran=p["uran"] - VIP_COST_URAN, is_vip=1)
    await cb.answer("⭐ ВИП активирован!", show_alert=True)
    await cb.message.edit_text(
        f"⭐ <b>ВИП активирован!</b>\n\n"
        f"Потрачено: <b>{VIP_COST_URAN} ☢️ Уран-223</b>\n"
        f"Доступны все 18+ РП команды 🔞\n\n"
        f"Напиши .помощьрп чтобы увидеть все команды",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_lab")]
        ])
    )

# ───────────────────────────────────────────────────────────────
#  РП СИСТЕМА
# ───────────────────────────────────────────────────────────────

def rp_name(user) -> str:
    return f"@{user.username}" if user.username else user.full_name

@router.callback_query(F.data == "menu_rp")
async def cb_menu_rp(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "🎭 <b>РП система</b>\n\n"
        "Все РП команды работают через реплай на сообщение жертвы!\n\n"
        "<b>Бесплатные действия:</b>\n"
        ".кусь — укусить\n"
        ".обнять — обнять\n"
        ".погладить — погладить\n"
        ".ударить — ударить\n"
        ".поцеловать — поцеловать\n"
        ".укусить — укусить\n"
        ".шлёпнуть — шлёпнуть\n"
        ".пнуть — пнуть\n"
        ".лизнуть — лизнуть\n"
        ".потрепать — потрепать\n\n"
        "🔞 <b>ВИП 18+ действия</b> — .помощьрп",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔞 ВИП команды", callback_data="rp_help")],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="back_main")],
        ])
    )

@router.callback_query(F.data == "rp_help")
@router.message(F.text == ".helprp")
@router.message(F.text == ".помощьрп")
async def cb_rp_help(event):
    msg = event if isinstance(event, Message) else event.message
    if isinstance(event, CallbackQuery): await event.answer()
    await msg.answer(
        "🎭 <b>РП — Все команды</b>\n\n"
        "<b>Бесплатные (реплай на сообщение):</b>\n"
        ".кусь .укусить .обнять .погладить\n"
        ".ударить .поцеловать .шлёпнуть\n"
        ".пнуть .лизнуть .потрепать\n\n"
        "🔞 <b>ВИП команды (только для ВИП):</b>\n"
        ".изнасиловать .надругаться\n"
        ".раздеть .трахнуть\n"
        ".связать .доминировать\n\n"
        "💡 Триггеры — напиши слово <b>кусь</b> в чате\n"
        "и бот автоматически среагирует если есть реплай!\n\n"
        f"⭐ ВИП стоит <b>{VIP_COST_URAN} ☢️ Уран-223</b>"
    )

async def _do_rp_action(msg: Message, action_key: str, vip_required: bool = False):
    if not msg.reply_to_message:
        return await msg.answer(
            f"❌ Ответь на сообщение жертвы командой .{action_key}"
        )
    if vip_required:
        p = await get_or_create(msg.from_user.id, msg.from_user.username, msg.from_user.full_name)
        if not is_vip_active(p):
            return await msg.answer(
                f"🔞 Это действие только для ВИП!\n"
                f"⭐ Купи ВИП за <b>{VIP_COST_URAN} ☢️ Уран-223</b>\n"
                f"Открой .лаб → ⭐ ВИП",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⭐ Купить ВИП", callback_data="vip_info")]
                ])
            )
    a = rp_name(msg.from_user)
    b = rp_name(msg.reply_to_message.from_user)
    actions_dict = {**RP_TRIGGERS, **RP_VIP_ACTIONS}
    phrases = actions_dict.get(action_key, [f"{action_key}: {{a}} → {{b}}"])
    phrase  = random.choice(phrases)
    await msg.answer(phrase.format(a=a, b=b))

# Бесплатные РП команды
for _action in RP_TRIGGERS:
    exec(f"""
@router.message(F.text == ".{_action}")
async def _rp_{_action}(msg: Message):
    await _do_rp_action(msg, "{_action}", False)
""")

# ВИП РП команды
for _action in RP_VIP_ACTIONS:
    exec(f"""
@router.message(F.text == ".{_action}")
async def _rp_vip_{_action}(msg: Message):
    await _do_rp_action(msg, "{_action}", True)
""")

# Триггеры на слова в чате
@router.message(F.text.func(lambda t: t and "кусь" in t.lower()))
async def trigger_kus(msg: Message):
    if not msg.reply_to_message: return
    a = rp_name(msg.from_user)
    b = rp_name(msg.reply_to_message.from_user)
    phrase = random.choice(RP_TRIGGERS["кусь"])
    await msg.answer(phrase.format(a=a, b=b))

# ───────────────────────────────────────────────────────────────
#  ЗАРАЖЕНИЕ
# ───────────────────────────────────────────────────────────────

async def _resolve_target(msg: Message) -> Optional[dict]:
    if msg.reply_to_message:
        return await get_player(msg.reply_to_message.from_user.id)
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2: return None
    arg = parts[1].strip()
    if arg.startswith("@"): return await get_player_by_username(arg)
    if arg.isdigit():       return await get_player(int(arg))
    return None

@router.message(F.text.startswith(".заразить"))
@router.message(Command("infect"))
async def cmd_infect(msg: Message):
    uid = msg.from_user.id
    if await is_banned(uid): return await reply_or_dm(msg, msg.bot, "🚫 Заблокированы.")
    attacker = await get_or_create(uid, msg.from_user.username, msg.from_user.full_name)
    attacker = await refresh_pathogens(attacker)
    if fever_active(attacker):
        fu  = datetime.datetime.fromisoformat(str(attacker["fever_until"]))
        rem = int((fu - datetime.datetime.utcnow()).total_seconds())
        h, m = divmod(rem // 60, 60)
        return await msg.answer(
            f"🤒 <b>Горячка!</b> Нельзя атаковать.\nОсталось: <b>{h}ч {m}мин</b>",
            reply_markup=kb_fever()
        )
    if attacker["pathogens_ready"] < 1:
        timer = pathogen_timer_str(attacker)
        return await msg.answer(
            f"🧪 <b>Нет патогенов!</b>\nСледующий через: <b>{timer}</b>"
        )
    if msg.text.strip() in (".заразить", "/заразить") and not msg.reply_to_message:
        return await msg.answer(
            "☣️ Ответь на сообщение жертвы командой .заразить\n"
            "Или: .заразить @username / .заразить 123456789"
        )
    target = await _resolve_target(msg)
    if not target:
        return await msg.answer("❌ Цель не найдена!\n.заразить @username или реплай")
    if target["user_id"] == uid:
        return await msg.answer("🤦 Нельзя заражать себя!")
    if target["is_banned"]:
        return await msg.answer("❌ Игрок недоступен.")
    if target.get("event_immunity"):
        return await msg.answer("🛡 У цели иммунитет события!")
    if infected_active(target):
        iu  = datetime.datetime.fromisoformat(str(target["infected_until"]))
        rem = int((iu - datetime.datetime.utcnow()).total_seconds())
        h, m = divmod(rem // 60, 60)
        return await msg.answer(f"☣️ Цель уже заражена! Спадёт через <b>{h}ч {m}мин</b>.")
    chance   = infect_chance(attacker, target)
    atk_roll = random.random()
    success  = atk_roll < chance
    reward   = 0.0
    now      = datetime.datetime.utcnow()
    await update_player(uid,
        pathogens_ready=attacker["pathogens_ready"] - 1,
        last_pathogen_at=now.isoformat(),
        operations_total=attacker["operations_total"] + 1
    )
    if success:
        inf_secs    = infected_seconds(attacker)
        fever_secs  = fever_seconds(attacker)
        inf_until   = now + datetime.timedelta(seconds=inf_secs)
        fever_until = now + datetime.timedelta(seconds=fever_secs)
        reward      = round(random.uniform(10, 30) + attacker["infection"] * 2, 2)
        await update_player(uid,
            bio_resource       = attacker["bio_resource"] + reward,
            bio_exp            = attacker["bio_exp"] + 10,
            infected_count     = attacker["infected_count"] + 1,
            operations_success = attacker["operations_success"] + 1,
        )
        await update_player(target["user_id"],
            is_infected    = 1,
            infected_until = inf_until.isoformat(),
            fever_until    = fever_until.isoformat(),
            infected_by    = uid,
        )
        if attacker.get("corp_id"):
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE corporations SET bio_exp=bio_exp+10 WHERE id=?",
                    (attacker["corp_id"],))
                await db.commit()
        inf_h, inf_m  = divmod(inf_secs // 60, 60)
        fev_h, fev_m  = divmod(fever_secs // 60, 60)
        attacker2     = await get_player(uid)
        timer         = pathogen_timer_str(attacker2)
        await msg.answer(
            f"☣️ <b>ЗАРАЖЕНИЕ УСПЕШНО!</b>\n\n"
            f"🎯 Жертва: <b>{target['full_name']}</b>\n"
            f"🦠 {attacker['infection']} vs 🛡{target['immunity']}+🔒{target['security']}\n"
            f"🎲 Шанс: {chance*100:.0f}%\n\n"
            f"⏳ Заражение: <b>{inf_h}ч {inf_m}мин</b>\n"
            f"🤒 Горячка жертвы: <b>{fev_h}ч {fev_m}мин</b>\n"
            f"💰 +<b>{reward}</b> 🧬\n\n"
            f"🧪 Патогены: <b>{attacker2['pathogens_ready']}/{attacker2['pathogens_max']}</b>"
            f" (след. {timer})"
        )
        try:
            await msg.bot.send_message(
                target["user_id"],
                f"☣️ <b>ВАС ЗАРАЗИЛИ!</b>\n"
                f"Атаковал: <b>{attacker['full_name']}</b>\n"
                f"🤒 Горячка: <b>{fev_h}ч {fev_m}мин</b>\n"
                f"⏳ Заражение: <b>{inf_h}ч {inf_m}мин</b>\n"
                f"💊 Лечение: .лечение",
                reply_markup=kb_fever()
            )
        except Exception:
            pass
    else:
        await update_player(target["user_id"],
            prevented_success=target["prevented_success"] + 1,
            prevented_total  =target["prevented_total"] + 1,
        )
        attacker2 = await get_player(uid)
        await msg.answer(
            f"🛡 <b>Атака отражена!</b>\n\n"
            f"🎯 {target['full_name']}\n"
            f"🦠 {attacker['infection']} vs 🛡{target['immunity']}+🔒{target['security']}\n"
            f"🎲 Шанс: {chance*100:.0f}%\n\n"
            f"🧪 Патогены: <b>{attacker2['pathogens_ready']}/{attacker2['pathogens_max']}</b>"
            f" (след. {pathogen_timer_str(attacker2)})"
        )
    await log_attack(uid, target["user_id"], int(success),
                     int(atk_roll*100), int(chance*100), reward)

# ───────────────────────────────────────────────────────────────
#  ГОРЯЧКА
# ───────────────────────────────────────────────────────────────

@router.message(F.text == ".heal")
@router.message(F.text == ".лечение")
@router.message(Command("heal"))
async def cmd_fever(msg: Message):
    p = await get_or_create(msg.from_user.id, msg.from_user.username, msg.from_user.full_name)
    if not fever_active(p):
        return await msg.answer("✅ Горячки нет!")
    fu  = datetime.datetime.fromisoformat(str(p["fever_until"]))
    rem = int((fu - datetime.datetime.utcnow()).total_seconds())
    h, m = divmod(rem // 60, 60)
    await msg.answer(
        f"🤒 <b>Горячка!</b> {h}ч {m}мин\n💊 Вылечить за <b>{FEVER_HEAL_COST:.0f} 🧬</b>",
        reply_markup=kb_fever()
    )

@router.callback_query(F.data == "fever_heal")
async def cb_fever_heal(cb: CallbackQuery):
    p = await get_player(cb.from_user.id)
    if not fever_active(p):
        return await cb.answer("✅ Горячки нет!", show_alert=True)
    if p["bio_resource"] < FEVER_HEAL_COST:
        return await cb.answer(f"❌ Нужно {FEVER_HEAL_COST:.0f}🧬", show_alert=True)
    await update_player(cb.from_user.id,
        bio_resource=p["bio_resource"] - FEVER_HEAL_COST, fever_until=None)
    await cb.answer("💊 Вылечен!", show_alert=True)
    await cb.message.edit_text(f"✅ <b>Горячка вылечена!</b> Потрачено {FEVER_HEAL_COST:.0f}🧬")

@router.callback_query(F.data == "fever_wait")
async def cb_fever_wait(cb: CallbackQuery):
    p = await get_player(cb.from_user.id)
    if not fever_active(p):
        return await cb.answer("✅ Горячки нет!", show_alert=True)
    fu  = datetime.datetime.fromisoformat(str(p["fever_until"]))
    rem = int((fu - datetime.datetime.utcnow()).total_seconds())
    h, m = divmod(rem // 60, 60)
    await cb.answer(f"⏳ {h}ч {m}мин", show_alert=True)

# ───────────────────────────────────────────────────────────────
#  ТОПЫ
# ───────────────────────────────────────────────────────────────

@router.message(F.text == ".top")
@router.message(F.text == ".топ")
@router.message(Command("top"))
async def cmd_top(msg: Message):
    top    = await get_top_players(10)
    medals = ["🥇","🥈","🥉"] + ["🔹"] * 7
    lines  = ["🏆 <b>ТОП-10 игроков</b>\n"]
    for i, p in enumerate(top):
        name  = p["full_name"] or p["username"] or str(p["user_id"])
        rank  = get_rank(p["bio_exp"])
        title = player_display_title(p)
        vip   = "⭐ " if is_vip_active(p) else ""
        t_str = f" <i>{title}</i>" if title else ""
        lines.append(f"{medals[i]} {vip}{name}{t_str}\n   {rank} | ☣️ {p['bio_exp']} | 😤 {p['infected_count']}")
    await msg.answer("\n".join(lines) if top else "Топ пуст.")

@router.message(F.text == ".topcorp")
@router.message(F.text == ".топкорп")
@router.message(Command("topclans"))
async def cmd_top_corps(msg: Message):
    top    = await get_top_corps(10)
    medals = ["🥇","🥈","🥉"] + ["🔹"] * 7
    lines  = ["🏢 <b>ТОП-10 корпораций</b>\n"]
    for i, c in enumerate(top):
        cr = get_corp_rank(c["members_count"])
        lines.append(f"{medals[i]} <b>[{c['tag']}] {c['name']}</b>\n   {cr} | 👥 {c['members_count']} | ☣️ {c['bio_exp']}")
    await msg.answer("\n".join(lines) if top else "Топ пуст.")

# ───────────────────────────────────────────────────────────────
#  КОРПОРАЦИИ
# ───────────────────────────────────────────────────────────────

@router.message(F.text == ".createcorp")
@router.message(F.text == ".создатькорп")
@router.message(Command("createcorp"))
@router.callback_query(F.data == "corp_create")
async def cmd_create_corp(event, state: FSMContext):
    msg = event if isinstance(event, Message) else event.message
    uid = event.from_user.id
    if await is_banned(uid):
        if isinstance(event, CallbackQuery): return await event.answer("🚫", show_alert=True)
        return await msg.answer("🚫")
    p = await get_player(uid)
    if p and p.get("corp_id"):
        txt = "❌ Ты уже в корпорации!"
        if isinstance(event, CallbackQuery): return await event.answer(txt, show_alert=True)
        return await msg.answer(txt)
    await msg.answer("🏗 <b>Создание корпорации</b>\n\nВведи название (2–32):", reply_markup=kb_cancel())
    await state.set_state(S.corp_name)
    if isinstance(event, CallbackQuery): await event.answer()

@router.message(S.corp_name)
async def proc_corp_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if not 2 <= len(name) <= 32: return await msg.answer("❌ 2–32 символа.")
    if await get_corp_by_name(name): return await msg.answer("❌ Название занято!")
    await state.update_data(corp_name=name)
    await msg.answer(f"✅ Название: <b>{name}</b>\n\nВведи тег (2–6 символов):", reply_markup=kb_cancel())
    await state.set_state(S.corp_tag)

@router.message(S.corp_tag)
async def proc_corp_tag(msg: Message, state: FSMContext):
    tag = msg.text.strip().upper()
    if not 2 <= len(tag) <= 6: return await msg.answer("❌ 2–6 символов.")
    if await get_corp_by_tag(tag): return await msg.answer("❌ Тег занят!")
    data = await state.get_data()
    uid  = msg.from_user.id
    corp = await create_corp(data["corp_name"], tag, uid)
    if not corp:
        await state.clear()
        return await msg.answer("❌ Ошибка. Попробуй другое название/тег.")
    await update_player(uid, corp_id=corp["id"])
    await state.clear()
    await msg.answer(
        f"🎉 <b>Корпорация создана!</b>\n\n"
        f"🏢 <b>[{tag}] {data['corp_name']}</b>\n"
        f"Тег для вступления: <code>{tag}</code>"
    )

@router.message(F.text.startswith(".вступить"))
@router.message(Command("joincorp"))
async def cmd_join_corp(msg: Message):
    uid  = msg.from_user.id
    p    = await get_or_create(uid, msg.from_user.username, msg.from_user.full_name)
    if p.get("corp_id"): return await msg.answer("❌ Уже в корпорации! (.выйти)")
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2: return await msg.answer("❌ .вступить ТЕГ")
    corp = await get_corp_by_tag(parts[1].strip())
    if not corp: return await msg.answer(f"❌ Корпорация не найдена.")
    await update_player(uid, corp_id=corp["id"])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE corporations SET members_count=members_count+1 WHERE id=?", (corp["id"],))
        await db.commit()
    await msg.answer(f"✅ Вступил в <b>[{corp['tag']}] {corp['name']}</b>!")

@router.message(F.text == ".leave")
@router.message(F.text == ".выйти")
@router.message(Command("leavecorp"))
@router.callback_query(F.data == "corp_leave")
async def cmd_leave_corp(event):
    uid = event.from_user.id
    p   = await get_player(uid)
    msg = event if isinstance(event, Message) else event.message
    if not p or not p.get("corp_id"):
        if isinstance(event, CallbackQuery): return await event.answer("❌ Не в корпорации", show_alert=True)
        return await msg.answer("❌ Не в корпорации.")
    corp = await get_corp(p["corp_id"])
    await update_player(uid, corp_id=None)
    if corp:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE corporations SET members_count=MAX(0,members_count-1) WHERE id=?", (corp["id"],))
            await db.commit()
    if isinstance(event, CallbackQuery):
        await event.answer("✅ Вышел", show_alert=True)
        await event.message.edit_text("🚪 Вышел из корпорации.")
    else:
        await msg.answer("🚪 Вышел из корпорации.")

@router.callback_query(F.data == "corp_info")
async def cb_corp_info(cb: CallbackQuery):
    p = await get_player(cb.from_user.id)
    if not p or not p.get("corp_id"): return await cb.answer("❌", show_alert=True)
    corp = await get_corp(p["corp_id"])
    if not corp: return await cb.answer("❌", show_alert=True)
    await cb.message.edit_text(
        f"🏢 <b>[{corp['tag']}] {corp['name']}</b>\n"
        f"{get_corp_rank(corp['members_count'])}\n\n"
        f"👥 {corp['members_count']} | 🧬 {corp['bio_resource']:.1f} | ☣️ {corp['bio_exp']}",
        reply_markup=kb_corp_actions(p)
    )
    await cb.answer()

@router.callback_query(F.data == "corp_search")
async def cb_corp_search(cb: CallbackQuery):
    await cb.message.answer("🔍 Напиши: .вступить ТЕГ")
    await cb.answer()

@router.message(F.text == ".corp")
@router.message(F.text == ".корп")
@router.message(Command("corp"))
async def cmd_corp_menu(msg: Message):
    uid = msg.from_user.id
    p   = await get_or_create(uid, msg.from_user.username, msg.from_user.full_name)
    if p.get("corp_id"):
        corp = await get_corp(p["corp_id"])
        if corp:
            return await msg.answer(
                f"🏢 <b>[{corp['tag']}] {corp['name']}</b>\n"
                f"{get_corp_rank(corp['members_count'])}\n\n"
                f"👥 {corp['members_count']} | 🧬 {corp['bio_resource']:.1f} | ☣️ {corp['bio_exp']}",
                reply_markup=kb_corp_actions(p)
            )
    await msg.answer("🏢 Ты не в корпорации.", reply_markup=kb_corp_actions(p))

# ───────────────────────────────────────────────────────────────
#  ПРОМОКОДЫ
# ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu_promo")
async def cb_menu_promo(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "🎟 <b>Промокоды</b>\n\n"
        "Введи промокод командой:\n"
        "<code>.промокод КОД</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Меню", callback_data="back_main")]
        ])
    )

@router.message(F.text.startswith(".промокод"))
@router.message(Command("promo"))
async def cmd_use_promo(msg: Message):
    uid   = msg.from_user.id
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await msg.answer("❌ Формат: .промокод КОД")
    code  = parts[1].strip().upper()
    promo = await get_promo(code)
    if not promo:
        return await msg.answer("❌ Промокод не найден или неактивен.")
    if promo["max_uses"] > 0 and promo["uses"] >= promo["max_uses"]:
        return await msg.answer("❌ Промокод исчерпан.")
    if await promo_already_used(code, uid):
        return await msg.answer("❌ Ты уже использовал этот промокод.")
    p = await get_or_create(uid, msg.from_user.username, msg.from_user.full_name)
    reward_type   = promo["reward_type"]
    reward_amount = promo["reward_amount"]
    await use_promo(code, uid)
    reward_str = ""
    if reward_type == "bio":
        await update_player(uid, bio_resource=p["bio_resource"] + reward_amount)
        reward_str = f"+<b>{reward_amount:.0f} 🧬 Био-Ресурсов</b>"
    elif reward_type == "exp":
        await update_player(uid, bio_exp=p["bio_exp"] + int(reward_amount))
        reward_str = f"+<b>{reward_amount:.0f} ☣️ Био-Опыта</b>"
    elif reward_type == "uran":
        await update_player(uid, uran=p["uran"] + reward_amount)
        reward_str = f"+<b>{reward_amount:.0f} ☢️ Уран-223</b>"
    elif reward_type == "vip":
        await update_player(uid, is_vip=1)
        reward_str = "<b>⭐ ВИП статус активирован!</b>"
    await msg.answer(
        f"✅ <b>Промокод активирован!</b>\n\n"
        f"🎟 Код: <code>{code}</code>\n"
        f"🎁 Награда: {reward_str}"
    )

# ───────────────────────────────────────────────────────────────
#  ПОМОЩЬ
# ───────────────────────────────────────────────────────────────

@router.message(F.text == ".help")
@router.message(F.text == ".помощь")
@router.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "ℹ️ <b>БИО-ВОЙНЫ — Помощь</b>\n\n"
        "<b>Команды (с точкой):</b>\n"
        ".старт — начать / главное меню\n"
        ".лаб — лаборатория\n"
        ".профиль — профиль\n"
        ".заразить @user — атака\n"
        ".лечение — вылечить горячку\n"
        ".топ — топ игроков\n"
        ".топкорп — топ корпораций\n"
        ".корп — моя корпорация\n"
        ".создатькорп — создать корп.\n"
        ".вступить ТЕГ — вступить\n"
        ".выйти — выйти из корпорации\n"
        ".промокод КОД — активировать\n"
        ".помощь — справка\n"
        ".помощьрп — РП справка\n\n"
        "<b>Прокачка через чат:</b>\n"
        "+заразность 2 — показать цену\n"
        "++заразность 2 — купить"
    )

# ───────────────────────────────────────────────────────────────
#  СИСТЕМА АДМИНИСТРАЦИИ
# ───────────────────────────────────────────────────────────────

async def _resolve_target_arg(arg: str) -> Optional[dict]:
    if arg.startswith("@"): return await get_player_by_username(arg)
    if arg.isdigit():       return await get_player(int(arg))
    return None

@router.message(F.text == ".admin")
@router.message(F.text == ".админ")
@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    uid = msg.from_user.id
    if not await is_admin(uid):
        if is_group(msg): return
        return await msg.answer("❌ Нет доступа.")
    level = await get_admin_level(uid)
    title = ADMIN_TITLES.get(level, "")
    text  = (
        f"🔧 <b>Админ-панель</b>\n"
        f"Уровень: <b>{title}</b>\n\n"
        f"📌 Команды:\n"
        f".выдать @user 500 — 🧬 Ресурсы\n"
        f".выдатьуран @user 100 — ☢️ Уран (только себе ур.9)\n"
        f".выдатьопыт @user 100 — ☣️ Опыт\n"
        f".выдатьопыткорп ТЕГ 100 — ☣️ Опыт корп.\n"
        f".бан @user причина — 🚫 (ур.4+)\n"
        f".разбан @user — ✅ (ур.4+)\n"
        f".повысить @user 1-5 причина (ур.5+)\n"
        f".разжаловать @user причина (ур.4+)\n"
        f".спрятать — 👻 из топа (ур.2+)\n"
        f".пометка текст — ✏️ (ур.1+)\n"
        f".лабид @user NEWID — кастомный Lab ID\n"
        f".создатьпромо — создать промокод (ур.3+)"
    )
    if is_group(msg):
        try:
            await msg.bot.send_message(uid, text, reply_markup=kb_admin_main())
            await msg.reply("📩 Панель отправлена в личку.")
        except Exception:
            await msg.reply("❌ Напиши боту в лс сначала!")
    else:
        await msg.answer(text, reply_markup=kb_admin_main())

@router.callback_query(F.data == "adm_back")
async def cb_adm_back(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    await cb.message.edit_text("🔧 <b>Админ-панель</b>", reply_markup=kb_admin_main())
    await cb.answer()

@router.callback_query(F.data == "adm_stats")
async def cb_adm_stats(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    players = await get_all_players()
    total   = len(players)
    banned  = sum(1 for p in players if p["is_banned"])
    vips    = sum(1 for p in players if is_vip_active(p))
    await cb.message.edit_text(
        f"🔧 <b>Админ-панель</b>\n\n"
        f"📊 Игроков: <b>{total}</b>\n"
        f"🚫 Заблокировано: <b>{banned}</b>\n"
        f"⭐ ВИП: <b>{vips}</b>",
        reply_markup=kb_admin_main()
    )
    await cb.answer()

@router.callback_query(F.data == "adm_give")
async def cb_adm_give(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id, min_level=3): return await cb.answer("❌ Нужен ур.3+", show_alert=True)
    await cb.message.edit_text(
        "🔧 <b>Выдача ресурсов</b>\n\n.выдать @username 500",
        reply_markup=kb_admin_main()
    )
    await cb.answer()

@router.callback_query(F.data == "adm_give_uran")
async def cb_adm_give_uran(cb: CallbackQuery):
    uid = cb.from_user.id
    if await get_admin_level(uid) < 9: return await cb.answer("❌ Только Владелец!", show_alert=True)
    await cb.message.edit_text(
        "☢️ <b>Выдача Уран-223</b>\n\n.выдатьуран @username 100",
        reply_markup=kb_admin_main()
    )
    await cb.answer()

@router.callback_query(F.data == "adm_labid")
async def cb_adm_labid(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    await cb.message.edit_text(
        "🔑 <b>Кастомный Lab ID</b>\n\n.лабид @username НОВЫЙ_ID",
        reply_markup=kb_admin_main()
    )
    await cb.answer()

@router.callback_query(F.data == "adm_help")
async def cb_adm_help(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    await cb.message.edit_text(
        "📋 <b>Все команды администратора</b>\n\n"
        ".выдать @user 500\n.выдатьуран @user 100 (ур.9)\n"
        ".выдатьопыт @user 100\n.выдатьопыткорп ТЕГ 100\n"
        ".бан @user причина (ур.4+)\n.разбан @user (ур.4+)\n"
        ".повысить @user 1-5 причина (ур.5+)\n"
        ".разжаловать @user причина (ур.4+)\n"
        ".спрятать (ур.2+)\n.пометка текст (ур.1+)\n"
        ".лабид @user ID\n.создатьпромо (ур.3+)",
        reply_markup=kb_admin_main()
    )
    await cb.answer()

# ── Выдача ресурсов ──────────────────────────────────────────

@router.message(F.text.startswith(".выдать"))
async def cmd_give(msg: Message):
    uid   = msg.from_user.id
    level = await get_admin_level(uid)
    if level < 3: return
    parts = msg.text.strip().split()
    if len(parts) < 3: return await msg.answer("❌ .выдать @user 500")
    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Игрок не найден.")
    if level in (3, 4) and target["user_id"] != uid:
        return await msg.answer("❌ Можешь выдавать только себе.")
    try:
        amount = float(parts[2])
        if amount <= 0: raise ValueError
    except ValueError:
        return await msg.answer("❌ Положительное число.")
    new_bal = target["bio_resource"] + amount
    await update_player(target["user_id"], bio_resource=new_bal)
    await reply_or_dm(msg, msg.bot, f"✅ +{amount:.0f}🧬 → {target['full_name']}\nБаланс: {new_bal:.1f}")
    if target["user_id"] != uid:
        try:
            await msg.bot.send_message(target["user_id"], f"🎁 +{amount:.0f}🧬\nБаланс: {new_bal:.1f}")
        except Exception: pass

@router.message(F.text.startswith(".выдатьуран"))
async def cmd_give_uran(msg: Message):
    uid = msg.from_user.id
    if await get_admin_level(uid) < 9:
        return await msg.answer("❌ Только Владелец!")
    parts = msg.text.strip().split()
    if len(parts) < 3: return await msg.answer("❌ .выдатьуран @user 100")
    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Не найден.")
    try:
        amount = float(parts[2])
        if amount <= 0: raise ValueError
    except ValueError:
        return await msg.answer("❌ Положительное число.")
    new_uran = target["uran"] + amount
    await update_player(target["user_id"], uran=new_uran)
    await msg.answer(f"✅ +{amount:.0f}☢️ → {target['full_name']}\nУран: {new_uran:.1f}")
    if target["user_id"] != uid:
        try:
            await msg.bot.send_message(target["user_id"],
                f"🎁 +{amount:.0f} ☢️ Уран-223!\nБаланс: {new_uran:.1f}")
        except Exception: pass

@router.message(F.text.startswith(".выдатьопыт"))
async def cmd_give_exp(msg: Message):
    if not await is_admin(msg.from_user.id, min_level=3): return
    parts = msg.text.strip().split()
    if len(parts) < 3: return await msg.answer("❌ .выдатьопыт @user 100")
    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Не найден.")
    try:
        amount = int(parts[2])
        if amount <= 0: raise ValueError
    except ValueError:
        return await msg.answer("❌ Положительное число.")
    new_exp = target["bio_exp"] + amount
    await update_player(target["user_id"], bio_exp=new_exp)
    await reply_or_dm(msg, msg.bot,
        f"✅ +{amount}☣️ → {target['full_name']}\nОпыт: {new_exp} | {get_rank(new_exp)}")
    if target["user_id"] != msg.from_user.id:
        try:
            await msg.bot.send_message(target["user_id"],
                f"🎁 +{amount}☣️ Био-Опыта!\nОпыт: {new_exp} | {get_rank(new_exp)}")
        except Exception: pass

@router.message(F.text.startswith(".выдатьопыткорп"))
async def cmd_give_corp_exp(msg: Message):
    if not await is_admin(msg.from_user.id, min_level=3): return
    parts = msg.text.strip().split()
    if len(parts) < 3: return await msg.answer("❌ .выдатьопыткорп ТЕГ 100")
    corp = await get_corp_by_tag(parts[1].strip())
    if not corp: return await msg.answer("❌ Корпорация не найдена.")
    try:
        amount = int(parts[2])
        if amount <= 0: raise ValueError
    except ValueError:
        return await msg.answer("❌ Положительное число.")
    new_exp = corp["bio_exp"] + amount
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE corporations SET bio_exp=? WHERE id=?", (new_exp, corp["id"]))
        await db.commit()
    await reply_or_dm(msg, msg.bot,
        f"✅ +{amount}☣️ корпорации [{corp['tag']}] {corp['name']}\nОпыт: {new_exp}")

# ── Бан/Разбан ─────────────────────────────────────────────

@router.message(F.text.startswith(".бан"))
async def cmd_ban(msg: Message):
    uid = msg.from_user.id
    if not await is_admin(uid, min_level=4): return
    parts = msg.text.strip().split(maxsplit=2)
    if len(parts) < 2: return await msg.answer("❌ .бан @user причина")
    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Не найден.")
    if target["user_id"] == SUPER_ADMIN_ID:
        return await msg.answer("❌ Владельца нельзя банить!")
    if target["user_id"] == uid:
        return await msg.answer("❌ Себя нельзя банить!")
    reason = parts[2] if len(parts) > 2 else "Не указана"
    await update_player(target["user_id"], is_banned=1)
    await reply_or_dm(msg, msg.bot,
        f"🚫 Забанен: <b>{target['full_name']}</b>\n📝 {reason}")
    try:
        await msg.bot.send_message(target["user_id"], f"🚫 Вы заблокированы\n📝 {reason}")
    except Exception: pass

@router.message(F.text.startswith(".разбан"))
async def cmd_unban(msg: Message):
    if not await is_admin(msg.from_user.id, min_level=4): return
    parts = msg.text.strip().split()
    if len(parts) < 2: return await msg.answer("❌ .разбан @user")
    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Не найден.")
    await update_player(target["user_id"], is_banned=0)
    await reply_or_dm(msg, msg.bot, f"✅ Разбанен: <b>{target['full_name']}</b>")
    try:
        await msg.bot.send_message(target["user_id"], "✅ Вы разблокированы!")
    except Exception: pass

# ── Повышение/Разжалование ──────────────────────────────────

@router.message(F.text.startswith(".повысить"))
async def cmd_promote(msg: Message):
    uid   = msg.from_user.id
    level = await get_admin_level(uid)
    if level < 5 and uid != SUPER_ADMIN_ID: return
    parts = msg.text.strip().split(maxsplit=3)
    if len(parts) < 3:
        return await msg.answer("❌ .повысить @user 1-5 причина\n1=Стажёр 2=Мл.адм 3=Адм 4=Ст.адм 5=Со-владелец")
    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Не найден.")
    try:
        new_level = int(parts[2])
        if not 1 <= new_level <= 5: raise ValueError
    except ValueError:
        return await msg.answer("❌ Уровень 1–5.")
    if target["user_id"] == SUPER_ADMIN_ID:
        return await msg.answer("❌ Владельца нельзя трогать!")
    reason   = parts[3] if len(parts) > 3 else "Не указана"
    old_level = target.get("admin_level", 0)
    if uid != SUPER_ADMIN_ID and level == 5 and new_level > 2:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO promote_requests (requester_id,target_id,target_level,reason) VALUES (?,?,?,?)",
                (uid, target["user_id"], new_level, reason))
            await db.commit()
        try:
            req = await get_player(uid)
            await msg.bot.send_message(SUPER_ADMIN_ID,
                f"📨 <b>Запрос на повышение</b>\n"
                f"От: {req['full_name']}\n"
                f"Кого: {target['full_name']}\n"
                f"На: {ADMIN_TITLES.get(new_level,'')}\n"
                f"Причина: {reason}\n\n"
                f"Подтвердить: .повысить @{target['username']} {new_level} {reason}")
        except Exception: pass
        return await msg.answer("📨 Запрос отправлен владельцу.")
    await set_admin_level(target["user_id"], new_level)
    await reply_or_dm(msg, msg.bot,
        f"✅ Повышен: {target['full_name']}\n"
        f"{ADMIN_TITLES.get(old_level,'Игрок')} → <b>{ADMIN_TITLES.get(new_level,'')}</b>")
    try:
        await msg.bot.send_message(target["user_id"],
            f"🎉 Вы повышены!\n{ADMIN_TITLES.get(new_level,'')}\nПричина: {reason}")
    except Exception: pass

@router.message(F.text.startswith(".разжаловать"))
async def cmd_demote(msg: Message):
    uid   = msg.from_user.id
    level = await get_admin_level(uid)
    if level < 4 and uid != SUPER_ADMIN_ID: return
    parts = msg.text.strip().split(maxsplit=2)
    if len(parts) < 2: return await msg.answer("❌ .разжаловать @user причина")
    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Не найден.")
    if target["user_id"] == SUPER_ADMIN_ID: return await msg.answer("❌ Нельзя!")
    if target["user_id"] == uid: return await msg.answer("❌ Нельзя разжаловать себя!")
    target_level = target.get("admin_level", 0)
    if level == 5 and uid != SUPER_ADMIN_ID and target_level > 2:
        return await msg.answer("❌ Со-владелец может разжаловать только до ур.2.")
    reason = parts[2] if len(parts) > 2 else "Не указана"
    await set_admin_level(target["user_id"], 0)
    await reply_or_dm(msg, msg.bot,
        f"✅ Разжалован: {target['full_name']}\n{ADMIN_TITLES.get(target_level,'Игрок')} → Игрок")
    try:
        await msg.bot.send_message(target["user_id"],
            f"⚠️ Вы разжалованы\n📝 {reason}")
    except Exception: pass

@router.message(F.text == ".hide")
@router.message(F.text == ".спрятать")
async def cmd_hide(msg: Message):
    uid = msg.from_user.id
    if not await is_admin(uid, min_level=2): return
    p = await get_player(uid)
    new_val = 0 if p.get("is_hidden") else 1
    await update_player(uid, is_hidden=new_val)
    await msg.answer("👻 Скрыт из топов." if new_val else "👁 Снова виден.")

@router.message(F.text.startswith(".пометка"))
async def cmd_change_title(msg: Message):
    uid = msg.from_user.id
    if not await is_admin(uid, min_level=1): return
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2: return await msg.answer("❌ .пометка Моя пометка")
    title = parts[1].strip()
    if len(title) > 32: return await msg.answer("❌ До 32 символов.")
    await update_player(uid, admin_title=title)
    await msg.answer(f"✅ Пометка: <b>{title}</b>")

@router.message(F.text.startswith(".лабид"))
async def cmd_setlabid(msg: Message):
    if not await is_admin(msg.from_user.id): return
    parts = msg.text.strip().split()
    if len(parts) < 3: return await msg.answer("❌ .лабид @user НОВЫЙ_ID")
    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Не найден.")
    new_id = parts[2].upper()
    if not 2 <= len(new_id) <= 16: return await msg.answer("❌ ID: 2–16 символов.")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM players WHERE lab_id=? AND user_id!=?",
            (new_id, target["user_id"])) as c:
            if await c.fetchone(): return await msg.answer(f"❌ ID <code>{new_id}</code> занят!")
    old_id = target["lab_id"]
    await update_player(target["user_id"], lab_id=new_id)
    await msg.answer(f"✅ Lab ID: <code>{old_id}</code> → <code>{new_id}</code>")
    try:
        await msg.bot.send_message(target["user_id"],
            f"🔑 Твой Lab ID изменён: <code>{new_id}</code>")
    except Exception: pass

# ── Промокоды — админ ────────────────────────────────────────

@router.callback_query(F.data == "adm_promos")
async def cb_adm_promos(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id, min_level=3): return await cb.answer("❌ Нужен ур.3+", show_alert=True)
    await cb.message.edit_text("🎟 <b>Промокоды</b>", reply_markup=kb_promo_admin())
    await cb.answer()

@router.callback_query(F.data == "promo_list")
async def cb_promo_list(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id, min_level=3): return await cb.answer("❌", show_alert=True)
    promos = await get_all_promos()
    if not promos:
        return await cb.message.edit_text("🎟 Промокодов нет.", reply_markup=kb_promo_admin())
    lines = ["🎟 <b>Все промокоды</b>\n"]
    for p in promos[:20]:
        status = "✅" if p["is_active"] else "❌"
        lines.append(
            f"{status} <code>{p['code']}</code> | {p['reward_type']} +{p['reward_amount']:.0f}"
            f" | {p['uses']}/{p['max_uses'] if p['max_uses'] > 0 else '∞'}"
        )
    await cb.message.edit_text("\n".join(lines), reply_markup=kb_promo_admin())
    await cb.answer()

@router.callback_query(F.data == "promo_create")
async def cb_promo_create(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id, min_level=3): return await cb.answer("❌", show_alert=True)
    await cb.message.answer(
        "🎟 <b>Создание промокода</b>\n\nВведи код (например: SPYSH2025):",
        reply_markup=kb_cancel()
    )
    await state.set_state(S.promo_create_code)
    await cb.answer()

@router.message(S.promo_create_code)
async def proc_promo_code(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id, min_level=3): return
    code = msg.text.strip().upper()
    if len(code) < 2 or len(code) > 20:
        return await msg.answer("❌ Код 2–20 символов.")
    existing = await get_promo(code)
    if existing:
        return await msg.answer("❌ Такой код уже существует!")
    await state.update_data(promo_code=code)
    await msg.answer(
        f"✅ Код: <code>{code}</code>\n\n"
        f"Тип награды (напиши одно):\n"
        f"<b>bio</b> — Био-Ресурсы\n"
        f"<b>exp</b> — Био-Опыт\n"
        f"<b>uran</b> — Уран-223\n"
        f"<b>vip</b> — ВИП статус",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧬 Bio",   callback_data="pt:bio"),
             InlineKeyboardButton(text="☣️ Exp",   callback_data="pt:exp")],
            [InlineKeyboardButton(text="☢️ Uran",  callback_data="pt:uran"),
             InlineKeyboardButton(text="⭐ VIP",   callback_data="pt:vip")],
        ])
    )
    await state.set_state(S.promo_create_type)

@router.callback_query(F.data.startswith("pt:"), S.promo_create_type)
async def cb_promo_type(cb: CallbackQuery, state: FSMContext):
    ptype = cb.data.split(":")[1]
    await state.update_data(promo_type=ptype)
    if ptype == "vip":
        await state.update_data(promo_amount=1)
        await cb.message.answer("🔢 Сколько активаций? (0 = безлимит):")
        await state.set_state(S.promo_create_uses)
    else:
        await cb.message.answer(f"💰 Количество {ptype} для награды:")
        await state.set_state(S.promo_create_amount)
    await cb.answer()

@router.message(S.promo_create_amount)
async def proc_promo_amount(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id, min_level=3): return
    try:
        amount = float(msg.text.strip())
        if amount <= 0: raise ValueError
    except ValueError:
        return await msg.answer("❌ Положительное число.")
    await state.update_data(promo_amount=amount)
    await msg.answer("🔢 Сколько активаций? (0 = безлимит):")
    await state.set_state(S.promo_create_uses)

@router.message(S.promo_create_uses)
async def proc_promo_uses(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id, min_level=3): return
    try:
        uses = int(msg.text.strip())
        if uses < 0: raise ValueError
    except ValueError:
        return await msg.answer("❌ 0 или больше.")
    data = await state.get_data()
    ok   = await create_promo(
        data["promo_code"],
        data["promo_type"],
        data.get("promo_amount", 1),
        uses,
        msg.from_user.id
    )
    await state.clear()
    if ok:
        await msg.answer(
            f"✅ <b>Промокод создан!</b>\n\n"
            f"🎟 Код: <code>{data['promo_code']}</code>\n"
            f"🎁 Тип: {data['promo_type']}\n"
            f"💰 Количество: {data.get('promo_amount', 1)}\n"
            f"🔢 Активаций: {'∞' if uses == 0 else uses}"
        )
    else:
        await msg.answer("❌ Ошибка создания промокода.")

# ── Рассылка ────────────────────────────────────────────────

@router.callback_query(F.data == "adm_broadcast")
async def cb_adm_broadcast(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    await cb.message.answer(
        "📢 <b>Рассылка</b>\n\nВведи текст (HTML поддерживается).\n"
        "⚠️ Работает только для игроков которые писали боту в лс.",
        reply_markup=kb_cancel()
    )
    await state.set_state(S.broadcast_text)
    await cb.answer()

@router.message(S.broadcast_text)
async def proc_broadcast(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id): return
    if is_group(msg):
        await msg.reply("📩 Напиши текст рассылки боту в личку!")
        await state.clear()
        return
    text    = msg.text.strip()
    players = await get_all_players()
    active  = [p for p in players if not p["is_banned"]]
    sent = failed = 0
    status = await msg.answer(f"📢 0/{len(active)}")
    for i, p in enumerate(active):
        try:
            await msg.bot.send_message(p["user_id"], text)
            sent += 1
        except Exception:
            failed += 1
        if (i+1) % 25 == 0:
            try: await status.edit_text(f"📢 {i+1}/{len(active)}")
            except Exception: pass
        await asyncio.sleep(0.05)
    await status.edit_text(
        f"✅ <b>Рассылка завершена</b>\n📨 {sent} | ❌ {failed}"
    )
    await state.clear()

# ── События ─────────────────────────────────────────────────

EVENT_INFO = {
    "mutation":   {"title": "🦠 Мутация",   "broadcast": "🦠 <b>МУТАЦИЯ!</b> Заразность +{bonus} на {hours}ч!"},
    "epidemic":   {"title": "💀 Эпидемия",   "broadcast": "💀 <b>ЭПИДЕМИЯ!</b> +{bonus}🧬 каждому! ({hours}ч)"},
    "quarantine": {"title": "🛡 Карантин",   "broadcast": "🛡 <b>КАРАНТИН!</b> Атаки заблокированы на {hours}ч!"},
    "biowar":     {"title": "⚔️ Биовойна",   "broadcast": "⚔️ <b>БИОВОЙНА!</b> Бонус опыта +{bonus}% на {hours}ч!"},
    "loot":       {"title": "🎁 Трофеи",     "broadcast": "🎁 <b>ТРОФЕИ!</b> {count} игроков получат по {bonus}🧬!"},
}

@router.callback_query(F.data == "adm_events")
async def cb_adm_events(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    btns = [[InlineKeyboardButton(text=v["title"], callback_data=f"ev_start:{k}")]
            for k, v in EVENT_INFO.items()]
    active = await get_active_events()
    for ev in active:
        btns.append([InlineKeyboardButton(
            text=f"🛑 Стоп: {ev['title']}",
            callback_data=f"ev_stop:{ev['id']}"
        )])
    btns.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm_back")])
    await cb.message.edit_text("☣️ <b>События</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    await cb.answer()

@router.callback_query(F.data.startswith("ev_stop:"))
async def cb_ev_stop(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    eid = int(cb.data.split(":")[1])
    await deactivate_event(eid)
    players = await get_all_players()
    for p in players:
        if p["is_banned"]: continue
        try:
            await cb.bot.send_message(p["user_id"], "☣️ <b>Событие завершено!</b>")
        except Exception: pass
        await asyncio.sleep(0.05)
    await cb.message.edit_text("✅ Событие остановлено.", reply_markup=kb_admin_main())
    await cb.answer()

@router.callback_query(F.data.startswith("ev_start:"))
async def cb_ev_start(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    etype = cb.data.split(":")[1]
    await state.update_data(etype=etype)
    await cb.message.answer(
        f"☣️ <b>{EVENT_INFO[etype]['title']}</b>\n⏱ На сколько часов? (1–72):",
        reply_markup=kb_cancel()
    )
    await state.set_state(S.event_hours)
    await cb.answer()

@router.message(S.event_hours)
async def proc_event_hours(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id): return
    try:
        hours = int(msg.text.strip())
        if not 1 <= hours <= 72: raise ValueError
    except ValueError:
        return await msg.answer("❌ 1–72")
    await state.update_data(hours=hours)
    data  = await state.get_data()
    etype = data["etype"]
    prompts = {
        "mutation":   "🦠 На сколько ур. повысить заразность?",
        "epidemic":   "💰 Сколько 🧬 выдать каждому?",
        "quarantine": "🛡 Иммунитет всем? (да/нет)",
        "biowar":     "⚔️ Бонус опыта в %?",
        "loot":       "🎁 Сколько игроков получат награду?",
    }
    await msg.answer(prompts.get(etype, "Введи параметр:"))
    await state.set_state(S.event_bonus)

@router.message(S.event_bonus)
async def proc_event_bonus(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id): return
    data  = await state.get_data()
    etype = data["etype"]
    txt   = msg.text.strip().lower()
    if etype == "quarantine":
        bonus = 1 if txt in ("да","yes","1","+") else 0
        await state.update_data(bonus=bonus)
        await _launch_event(msg, state)
    elif etype == "loot":
        try:
            count = int(txt)
            if count < 1: raise ValueError
        except ValueError:
            return await msg.answer("❌ Положительное число")
        await state.update_data(bonus=0, loot_count=count)
        await msg.answer("💰 Сколько 🧬 получит каждый?")
        await state.set_state(S.event_count)
    else:
        try:
            bonus = int(txt)
            if bonus < 0: raise ValueError
        except ValueError:
            return await msg.answer("❌ Положительное число")
        await state.update_data(bonus=bonus)
        await _launch_event(msg, state)

@router.message(S.event_count)
async def proc_event_count(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id): return
    try:
        amount = int(msg.text.strip())
        if amount < 1: raise ValueError
    except ValueError:
        return await msg.answer("❌ Положительное число")
    await state.update_data(loot_amount=amount)
    await _launch_event(msg, state)

async def _remove_immunity_after(delay: int):
    await asyncio.sleep(delay)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE players SET event_immunity=0")
        await db.commit()

async def _launch_event(msg: Message, state: FSMContext):
    data   = await state.get_data()
    etype  = data["etype"]
    hours  = data["hours"]
    bonus  = data.get("bonus", 0)
    info   = EVENT_INFO[etype]
    players        = await get_all_players()
    active_players = [p for p in players if not p["is_banned"]]
    winners        = []
    broadcast_text = ""
    if etype == "mutation":
        broadcast_text = info["broadcast"].format(bonus=bonus, hours=hours)
        for p in active_players:
            fp = await get_player(p["user_id"])
            if fp: await update_player(p["user_id"], infection=fp["infection"] + bonus)
    elif etype == "epidemic":
        broadcast_text = info["broadcast"].format(bonus=bonus, hours=hours)
        for p in active_players:
            fp = await get_player(p["user_id"])
            if fp: await update_player(p["user_id"], bio_resource=fp["bio_resource"] + bonus)
    elif etype == "quarantine":
        broadcast_text = info["broadcast"].format(hours=hours)
        if bonus:
            for p in active_players:
                await update_player(p["user_id"], event_immunity=1)
            asyncio.create_task(_remove_immunity_after(hours * 3600))
    elif etype == "biowar":
        broadcast_text = info["broadcast"].format(bonus=bonus, hours=hours)
        exp_b = max(1, bonus // 10)
        for p in active_players:
            fp = await get_player(p["user_id"])
            if fp: await update_player(p["user_id"], bio_exp=fp["bio_exp"] + exp_b * 10)
    elif etype == "loot":
        count       = data.get("loot_count", 5)
        loot_amount = data.get("loot_amount", 100)
        winners     = random.sample(active_players, min(count, len(active_players)))
        winner_ids  = {w["user_id"] for w in winners}
        broadcast_text = info["broadcast"].format(count=len(winners), bonus=loot_amount)
        for p in active_players:
            fp = await get_player(p["user_id"])
            if fp and p["user_id"] in winner_ids:
                await update_player(p["user_id"], bio_resource=fp["bio_resource"] + loot_amount)
    await create_event(etype, info["title"], "", "{}", hours)
    winner_ids_set = {w["user_id"] for w in winners}
    sent   = 0
    status = await msg.answer(f"📢 0/{len(active_players)}")
    for i, p in enumerate(active_players):
        try:
            await msg.bot.send_message(p["user_id"], broadcast_text)
            if etype == "loot" and p["user_id"] in winner_ids_set:
                la = data.get("loot_amount", 100)
                await msg.bot.send_message(p["user_id"], f"🎉 <b>ПОВЕЗЛО!</b> +{la}🧬!")
            sent += 1
        except Exception: pass
        if (i+1) % 25 == 0:
            try: await status.edit_text(f"📢 {i+1}/{len(active_players)}")
            except Exception: pass
        await asyncio.sleep(0.05)
    await status.edit_text(
        f"✅ <b>'{info['title']}' запущено!</b>\n⏱ {hours}ч | 📢 {sent}")
    await state.clear()

# ───────────────────────────────────────────────────────────────
#  АВТОРЕГИСТРАЦИЯ + ОТМЕНА
# ───────────────────────────────────────────────────────────────

@router.message(F.chat.type.in_({"group", "supergroup"}))
async def group_auto_register(msg: Message):
    if msg.from_user and not msg.from_user.is_bot:
        await get_or_create(msg.from_user.id, msg.from_user.username, msg.from_user.full_name)

@router.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Отменено.")
    await cb.answer()

# ───────────────────────────────────────────────────────────────
#  ЗАПУСК
# ───────────────────────────────────────────────────────────────

async def main():
    await init_db()
    logger.info("БД инициализирована ✅")
    await set_admin_level(SUPER_ADMIN_ID, 9)
    logger.info(f"Владелец: {SUPER_ADMIN_ID}")
    await start_web()
    asyncio.create_task(self_ping())
    logger.info("Антисон запущен ✅")
    bot = Bot(token=BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp  = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.set_my_commands([
        BotCommand(command="start",   description="🚀 Начать"),
        BotCommand(command="lab",     description="🧫 Лаборатория"),
        BotCommand(command="profile", description="📋 Профиль"),
        BotCommand(command="top",     description="🏆 Топ игроков"),
        BotCommand(command="topclans",description="🏢 Топ корпораций"),
        BotCommand(command="heal", description="💊 Горячка"),
        BotCommand(command="help",    description="ℹ️ Помощь"),
    ])
    logger.info("Бот запущен ✅")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
