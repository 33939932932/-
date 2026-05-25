# ═══════════════════════════════════════════════════════════════
#  ☣️  БИО-ВОЙНЫ  —  Telegram Bot  v3.0
#  Стек: Python 3.11, aiogram 3.7, aiosqlite
# ═══════════════════════════════════════════════════════════════

import asyncio, logging, os, random, string, datetime, json
from typing import Optional

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    Message,
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

FEVER_HEAL_COST  = 50.0
FEVER_DURATION   = 3600

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────────────────────
#  РАНГИ ИГРОКОВ (по bio_exp)
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
    for i, (threshold, name) in enumerate(PLAYER_RANKS):
        if exp < threshold:
            return threshold, name
    return None, None

# ───────────────────────────────────────────────────────────────
#  РАНГИ КОРПОРАЦИЙ (по members_count + bio_resource)
# ───────────────────────────────────────────────────────────────

CORP_RANKS = [
    (0,    "🏚 Стартап"),
    (3,    "🏢 Малая корпорация"),
    (7,    "🏬 Корпорация"),
    (15,   "🏛 Крупная корпорация"),
    (30,   "🌐 Мегакорпорация"),
    (60,   "⚡ Элитная корпорация"),
    (100,  "🌌 Небесная корпорация"),
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
# 0 = обычный игрок
# 1 = Стажёр        — может менять свою пометку
# 2 = Младший адм   — может прятаться в топе
# 3 = Администратор — может выдавать себе ресурсы
# 4 = Старший адм   — может банить
# 5 = Со-владелец   — может повышать до уровня 2, выше — запрос владельцу
# 9 = Владелец (SUPER_ADMIN_ID) — всё

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
                last_pathogen_at    TIMESTAMP DEFAULT NULL,
                bio_exp             INTEGER DEFAULT 0,
                bio_resource        REAL    DEFAULT 100.0,
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
        # Миграции
        migrations = [
            ("scientist_level",  "INTEGER DEFAULT 1"),
            ("pathogens_ready",  "INTEGER DEFAULT 3"),
            ("pathogens_max",    "INTEGER DEFAULT 3"),
            ("last_pathogen_at", "TIMESTAMP DEFAULT NULL"),
            ("is_infected",      "INTEGER DEFAULT 0"),
            ("fever_until",      "TIMESTAMP DEFAULT NULL"),
            ("infected_until",   "TIMESTAMP DEFAULT NULL"),
            ("infected_by",      "INTEGER DEFAULT NULL"),
            ("admin_level",      "INTEGER DEFAULT 0"),
            ("admin_title",      "TEXT DEFAULT ''"),
            ("is_hidden",        "INTEGER DEFAULT 0"),
            ("corp_id",          "INTEGER DEFAULT NULL"),
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
            CREATE TABLE IF NOT EXISTS upgrade_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, skill TEXT, amount INTEGER, cost REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id    INTEGER PRIMARY KEY,
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
            CREATE TABLE IF NOT EXISTS promote_requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
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
              f"Корпорация #{lab_id[:4]}", "засекречено"))
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
    if p:
        return p.get("admin_level", 0)
    return 0

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
        async with db.execute("""
            SELECT * FROM corporations ORDER BY bio_exp DESC, members_count DESC LIMIT ?
        """, (limit,)) as c:
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
#  ПАТОГЕНЫ — производство
# ───────────────────────────────────────────────────────────────

def pathogen_interval(scientist_level: int) -> int:
    """Интервал производства одного патогена в секундах.
    scientist_level 1 → 1800 сек (30 мин)
    scientist_level 10 → 60 сек (1 мин)
    """
    secs = max(60, 1800 - (scientist_level - 1) * 193)
    return secs

async def refresh_pathogens(p: dict) -> dict:
    """Пересчитывает патогены игрока исходя из времени."""
    if p["pathogens_ready"] >= p["pathogens_max"]:
        return p
    if not p.get("last_pathogen_at"):
        await update_player(p["user_id"], last_pathogen_at=datetime.datetime.utcnow().isoformat())
        return await get_player(p["user_id"])

    interval = pathogen_interval(p["scientist_level"])
    now = datetime.datetime.utcnow()
    last = datetime.datetime.fromisoformat(str(p["last_pathogen_at"]))
    elapsed = (now - last).total_seconds()
    gained = int(elapsed // interval)

    if gained > 0:
        new_ready = min(p["pathogens_ready"] + gained, p["pathogens_max"])
        leftover = elapsed - gained * interval
        new_last = (now - datetime.timedelta(seconds=leftover)).isoformat()
        await update_player(p["user_id"],
                            pathogens_ready=new_ready,
                            last_pathogen_at=new_last)
        return await get_player(p["user_id"])
    return p

def pathogen_timer_str(p: dict) -> str:
    """Строка до следующего патогена."""
    if p["pathogens_ready"] >= p["pathogens_max"]:
        return "полный запас"
    interval = pathogen_interval(p["scientist_level"])
    if not p.get("last_pathogen_at"):
        return f"{interval//60} мин"
    last = datetime.datetime.fromisoformat(str(p["last_pathogen_at"]))
    elapsed = (datetime.datetime.utcnow() - last).total_seconds()
    rem = max(0, interval - (elapsed % interval))
    m, s = divmod(int(rem), 60)
    return f"{m}м {s}с"

# ───────────────────────────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ───────────────────────────────────────────────────────────────

def fever_active(p: dict) -> bool:
    if not p.get("fever_until"):
        return False
    try:
        fu = datetime.datetime.fromisoformat(str(p["fever_until"]))
        return datetime.datetime.utcnow() < fu
    except Exception:
        return False

def infected_active(p: dict) -> bool:
    if not p.get("is_infected"):
        return False
    if not p.get("infected_until"):
        return False
    try:
        iu = datetime.datetime.fromisoformat(str(p["infected_until"]))
        return datetime.datetime.utcnow() < iu
    except Exception:
        return False

def infect_chance(attacker: dict, target: dict) -> float:
    if target.get("event_immunity"):
        return 0.01
    atk = attacker["infection"]
    def_ = target["immunity"] + target["security"]
    ratio = atk / max(def_, 1)
    if ratio >= 2.0:   return 0.85
    elif ratio >= 1.5: return 0.65
    elif ratio >= 1.0: return 0.45
    elif ratio >= 0.75: return 0.25
    elif ratio >= 0.5:  return 0.10
    else:               return 0.03

def fever_seconds(attacker: dict) -> int:
    return min(FEVER_DURATION + attacker.get("lethality", 1) * 1800, 86400)

def infected_seconds(attacker: dict) -> int:
    return min(3600 + attacker.get("lethality", 1) * 3600, 86400)

def player_display_title(p: dict) -> str:
    """Пометка игрока для топов."""
    lvl = p.get("admin_level", 0)
    if lvl == 9:
        t = p.get("admin_title", "") or "👨‍💻 Создатель"
        return t
    if lvl >= 1:
        custom = p.get("admin_title", "")
        return custom if custom else ADMIN_TITLES.get(lvl, "")
    return ""

# ───────────────────────────────────────────────────────────────
#  FSM STATES
# ───────────────────────────────────────────────────────────────

router = Router()

class S(StatesGroup):
    # Корпорация
    corp_name       = State()
    corp_tag        = State()
    # Переименование
    rename_lab      = State()
    rename_pathogen = State()
    # Админ события
    event_hours     = State()
    event_bonus     = State()
    event_count     = State()
    # Рассылка
    broadcast_text  = State()
    # Повышение
    promote_reason  = State()

# ───────────────────────────────────────────────────────────────
#  АПГРЕЙДЫ
# ───────────────────────────────────────────────────────────────

UPGRADE_COST_BASE = 30.0
UPGRADE_COST_MULT = 1.5

def upgrade_cost(level: int) -> float:
    return round(UPGRADE_COST_BASE * (UPGRADE_COST_MULT ** (level - 1)), 1)

UPGRADE_FIELDS = {
    "infection":       "🦠 Заразность",
    "immunity":        "🛡 Иммунитет",
    "lethality":       "☠️ Летальность",
    "security":        "🔒 Безопасность",
    "scientist_level": "🔭 Квалификация учёных",
}

def scientist_cost(level: int) -> float:
    return round(50.0 * (2.0 ** (level - 1)), 1)

# ───────────────────────────────────────────────────────────────
#  КЛАВИАТУРЫ
# ───────────────────────────────────────────────────────────────

def kb_main():
    """Главное inline-меню под сообщением."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧫 Лаборатория", callback_data="menu_lab"),
            InlineKeyboardButton(text="📋 Профиль",     callback_data="menu_profile"),
        ],
        [
            InlineKeyboardButton(text="☣️ Заразить",   callback_data="menu_infect"),
            InlineKeyboardButton(text="🏆 Топ",         callback_data="menu_top"),
        ],
        [
            InlineKeyboardButton(text="🏢 Корпорация",  callback_data="menu_corp"),
            InlineKeyboardButton(text="ℹ️ Помощь",      callback_data="menu_help"),
        ],
    ])

def kb_cancel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

def kb_lab(p: dict):
    """Inline кнопки под лабораторией."""
    interval_secs = pathogen_interval(p["scientist_level"])
    interval_str = f"{interval_secs//60}м"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚗️ Прокачка",        callback_data="open_upgrade"),
            InlineKeyboardButton(text="✏️ Переименовать",   callback_data="rename_menu"),
        ],
        [
            InlineKeyboardButton(
                text=f"🧪 Патогены: {p['pathogens_ready']}/{p['pathogens_max']} (⏱{interval_str})",
                callback_data="pathogens_info"
            ),
        ],
    ])

def kb_upgrade(p: dict):
    ci = upgrade_cost(p["infection"])
    cm = upgrade_cost(p["immunity"])
    cl = upgrade_cost(p["lethality"])
    cs = upgrade_cost(p["security"])
    csc = scientist_cost(p["scientist_level"])
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🦠 {ci:.0f}",  callback_data="upgrade:infection"),
            InlineKeyboardButton(text=f"🛡 {cm:.0f}",  callback_data="upgrade:immunity"),
            InlineKeyboardButton(text=f"☠️ {cl:.0f}",  callback_data="upgrade:lethality"),
        ],
        [
            InlineKeyboardButton(text=f"🔒 {cs:.0f}",  callback_data="upgrade:security"),
            InlineKeyboardButton(text=f"🔭 {csc:.0f}", callback_data="upgrade:scientist_level"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_lab")],
    ])

def kb_upgrade_legend(p: dict) -> str:
    ci  = upgrade_cost(p["infection"])
    cm  = upgrade_cost(p["immunity"])
    cl  = upgrade_cost(p["lethality"])
    cs  = upgrade_cost(p["security"])
    csc = scientist_cost(p["scientist_level"])
    interval = pathogen_interval(p["scientist_level"])
    next_interval = pathogen_interval(p["scientist_level"] + 1)
    return (
        f"🦠 Заразность ({p['infection']} ур) → <b>{ci:.0f} 🧬</b>\n"
        f"🛡 Иммунитет ({p['immunity']} ур) → <b>{cm:.0f} 🧬</b>\n"
        f"☠️ Летальность ({p['lethality']} ур) → <b>{cl:.0f} 🧬</b>\n"
        f"🔒 Безопасность ({p['security']} ур) → <b>{cs:.0f} 🧬</b>\n"
        f"🔭 Квалификация ({p['scientist_level']} ур) → <b>{csc:.0f} 🧬</b>\n"
        f"   ⏱ сейчас: {interval//60}м → после: {next_interval//60}м"
    )

def kb_fever():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💊 Вылечить за {FEVER_HEAL_COST:.0f} 🧬",
            callback_data="fever_heal")],
        [InlineKeyboardButton(text="⏳ Подождать", callback_data="fever_wait")],
    ])

def kb_rename():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏭 Имя лаборатории",  callback_data="rename_lab")],
        [InlineKeyboardButton(text="🦠 Имя патогена",     callback_data="rename_pathogen")],
        [InlineKeyboardButton(text="◀️ Назад",            callback_data="back_to_lab")],
    ])

def kb_corp_actions(p: dict):
    if p.get("corp_id"):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Инфо",          callback_data="corp_info"),
             InlineKeyboardButton(text="🚪 Выйти",         callback_data="corp_leave")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать корпорацию", callback_data="corp_create")],
        [InlineKeyboardButton(text="🔍 Вступить по тегу",  callback_data="corp_search")],
    ])

def kb_admin_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика",       callback_data="adm_stats"),
         InlineKeyboardButton(text="☣️ События",          callback_data="adm_events")],
        [InlineKeyboardButton(text="🧬 Выдать ресурсы",   callback_data="adm_give"),
         InlineKeyboardButton(text="🔑 Кастом Lab ID",    callback_data="adm_labid")],
        [InlineKeyboardButton(text="📢 Рассылка",         callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="📋 Все команды",      callback_data="adm_help")],
    ])

# ───────────────────────────────────────────────────────────────
#  СТАРТ
# ───────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(msg: Message):
    if await is_banned(msg.from_user.id):
        return await msg.answer("🚫 Вы заблокированы.")
    p = await get_or_create(msg.from_user.id, msg.from_user.username,
                             msg.from_user.full_name)
    name = msg.from_user.first_name or p["full_name"]
    await msg.answer(
        f"☣️ <b>БИО-ВОЙНЫ</b> | <b>Spysh</b>\n\n"
        f"Привет, <b>{name}</b>! 👋\n\n"
        f"🏭 Лаборатория: <b>{p['lab_name']}</b>\n"
        f"🆔 Лаб ID: <code>{p['lab_id']}</code>\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🦠 Развивай патоген\n"
        f"☣️ Заражай соперников\n"
        f"🏆 Захватывай мир!\n"
        f"━━━━━━━━━━━━━━━━",
        reply_markup=kb_main()
    )

# ───────────────────────────────────────────────────────────────
#  ЛАБОРАТОРИЯ
# ───────────────────────────────────────────────────────────────

async def _show_lab(msg: Message, user=None):
    _user = user or msg.from_user
    uid = _user.id
    if await is_banned(uid): return await msg.answer("🚫 Заблокированы.")
    p = await get_or_create(uid, _user.username, _user.full_name)
    p = await refresh_pathogens(p)

    interval = pathogen_interval(p["scientist_level"])
    timer    = pathogen_timer_str(p)
    rank     = get_rank(p["bio_exp"])

    await msg.answer(
        f"🏭 <b>{p['lab_name']}</b>\n"
        f"🆔 Лаб ID: <code>{p['lab_id']}</code>\n"
        f"🔬 Патоген: <b>{p['pathogen_name']}</b>\n"
        f"🎖 Ранг: <b>{rank}</b>\n\n"
        f"🔬 <b>НАВЫКИ:</b>\n"
        f"🦠 Заразность: <b>{p['infection']} ур</b>\n"
        f"🛡 Иммунитет: <b>{p['immunity']} ур</b>\n"
        f"☠️ Летальность: <b>{p['lethality']} ур</b>\n"
        f"🔒 Безопасность: <b>{p['security']} ур</b>\n"
        f"🔭 Квалификация учёных: <b>{p['scientist_level']} ур ({interval//60} мин)</b>\n\n"
        f"📊 <b>СТАТИСТИКА:</b>\n"
        f"🧬 Био-Ресурсы: <b>{p['bio_resource']:.1f}</b>\n"
        f"☣️ Био-Опыт: <b>{p['bio_exp']}</b>\n"
        f"😤 Заражённых: <b>{p['infected_count']}</b>\n\n"
        f"🧪 Патогены: <b>{p['pathogens_ready']}/{p['pathogens_max']}</b> "
        f"(следующий через <b>{timer}</b>)",
        reply_markup=kb_lab(p)
    )

@router.message(F.text == "🧫 Лаборатория")
async def cmd_lab(msg: Message):
    await _show_lab(msg)

@router.message(Command("лаб"))
async def cmd_lаb_slash(msg: Message):
    await _show_lab(msg)

@router.message(F.text == ".лаб")
async def cmd_lab_dot(msg: Message):
    await _show_lab(msg)

@router.message(F.text == ".ЛАБ")
async def cmd_lab_dot_upper(msg: Message):
    await _show_lab(msg)

@router.callback_query(F.data == "back_to_lab")
async def cb_back_to_lab(cb: CallbackQuery):
    uid = cb.from_user.id
    p   = await get_or_create(uid, cb.from_user.username, cb.from_user.full_name)
    p   = await refresh_pathogens(p)
    interval = pathogen_interval(p["scientist_level"])
    timer    = pathogen_timer_str(p)
    rank     = get_rank(p["bio_exp"])
    await cb.message.edit_text(
        f"🏭 <b>{p['lab_name']}</b>\n"
        f"🆔 Лаб ID: <code>{p['lab_id']}</code>\n"
        f"🔬 Патоген: <b>{p['pathogen_name']}</b>\n"
        f"🎖 Ранг: <b>{rank}</b>\n\n"
        f"🔬 <b>НАВЫКИ:</b>\n"
        f"🦠 Заразность: <b>{p['infection']} ур</b>\n"
        f"🛡 Иммунитет: <b>{p['immunity']} ур</b>\n"
        f"☠️ Летальность: <b>{p['lethality']} ур</b>\n"
        f"🔒 Безопасность: <b>{p['security']} ур</b>\n"
        f"🔭 Квалификация учёных: <b>{p['scientist_level']} ур ({interval//60} мин)</b>\n\n"
        f"📊 <b>СТАТИСТИКА:</b>\n"
        f"🧬 Био-Ресурсы: <b>{p['bio_resource']:.1f}</b>\n"
        f"☣️ Био-Опыт: <b>{p['bio_exp']}</b>\n"
        f"😤 Заражённых: <b>{p['infected_count']}</b>\n\n"
        f"🧪 Патогены: <b>{p['pathogens_ready']}/{p['pathogens_max']}</b> "
        f"(следующий через <b>{timer}</b>)",
        reply_markup=kb_lab(p)
    )
    await cb.answer()

@router.callback_query(F.data == "pathogens_info")
async def cb_pathogens_info(cb: CallbackQuery):
    p = await get_or_create(cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
    p = await refresh_pathogens(p)
    interval = pathogen_interval(p["scientist_level"])
    timer    = pathogen_timer_str(p)
    await cb.answer(
        f"🧪 Патогены: {p['pathogens_ready']}/{p['pathogens_max']}\n"
        f"⏱ Интервал: {interval//60} мин\n"
        f"🔄 Следующий: {timer}",
        show_alert=True
    )

# ───────────────────────────────────────────────────────────────
#  ПЕРЕИМЕНОВАНИЕ
# ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "rename_menu")
async def cb_rename_menu(cb: CallbackQuery):
    await cb.message.edit_text(
        "✏️ <b>Что хочешь переименовать?</b>",
        reply_markup=kb_rename()
    )
    await cb.answer()

@router.callback_query(F.data == "rename_lab")
async def cb_rename_lab(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(
        "🏭 Введи новое название лаборатории (2–32 символа):",
        reply_markup=kb_cancel()
    )
    await state.set_state(S.rename_lab)
    await cb.answer()

@router.callback_query(F.data == "rename_pathogen")
async def cb_rename_pathogen(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(
        "🦠 Введи новое название патогена (2–32 символа):",
        reply_markup=kb_cancel()
    )
    await state.set_state(S.rename_pathogen)
    await cb.answer()

@router.message(S.rename_lab)
async def proc_rename_lab(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 2 or len(name) > 32:
        return await msg.answer("❌ Название 2–32 символа.")
    await update_player(msg.from_user.id, lab_name=name)
    await state.clear()
    await msg.answer(f"✅ Название лаборатории изменено на <b>{name}</b>! Открой /лаб")

@router.message(S.rename_pathogen)
async def proc_rename_pathogen(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 2 or len(name) > 32:
        return await msg.answer("❌ Название 2–32 символа.")
    await update_player(msg.from_user.id, pathogen_name=name)
    await state.clear()
    await msg.answer(f"✅ Патоген переименован в <b>{name}</b>! Открой /лаб")

# ───────────────────────────────────────────────────────────────
#  ПРОКАЧКА
# ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "open_upgrade")
async def cb_open_upgrade(cb: CallbackQuery):
    p = await get_or_create(cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
    await cb.message.edit_text(
        f"⚗️ <b>Прокачка лаборатории</b>\n"
        f"🧬 Био-Ресурсы: <b>{p['bio_resource']:.1f}</b>\n\n"
        + kb_upgrade_legend(p) +
        "\n\nНажми на кнопку (цена указана на кнопке):",
        reply_markup=kb_upgrade(p)
    )
    await cb.answer()

@router.callback_query(F.data.startswith("upgrade:"))
async def cb_upgrade(cb: CallbackQuery):
    uid   = cb.from_user.id
    if await is_banned(uid): return await cb.answer("🚫", show_alert=True)
    p     = await get_player(uid)
    skill = cb.data.split(":")[1]
    if skill not in UPGRADE_FIELDS:
        return await cb.answer("❌ Неизвестный навык", show_alert=True)

    current = p[skill]
    if skill == "scientist_level":
        cost = scientist_cost(current)
    else:
        cost = upgrade_cost(current)

    if p["bio_resource"] < cost:
        return await cb.answer(f"❌ Нужно {cost:.0f} 🧬, у тебя {p['bio_resource']:.1f}", show_alert=True)

    new_max = p["pathogens_max"]
    if skill == "scientist_level":
        new_max = min(p["pathogens_max"] + 1, 10)

    await update_player(uid,
        **{skill: current + 1},
        bio_resource=p["bio_resource"] - cost,
        pathogens_max=new_max
    )
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO upgrade_log (user_id,skill,amount,cost) VALUES (?,?,?,?)",
            (uid, skill, 1, cost))
        await db.commit()

    await cb.answer(f"✅ {UPGRADE_FIELDS[skill]} → {current+1} ур!", show_alert=True)
    p2 = await get_player(uid)
    await cb.message.edit_text(
        f"⚗️ <b>Прокачка лаборатории</b>\n"
        f"🧬 Био-Ресурсы: <b>{p2['bio_resource']:.1f}</b>\n\n"
        + kb_upgrade_legend(p2) +
        "\n\nНажми на кнопку (цена указана на кнопке):",
        reply_markup=kb_upgrade(p2)
    )

# ───────────────────────────────────────────────────────────────
#  ПРОФИЛЬ
# ───────────────────────────────────────────────────────────────

@router.message(F.text == "📋 Профиль")
async def cmd_profile(msg: Message):
    p = await get_or_create(msg.from_user.id, msg.from_user.username, msg.from_user.full_name)
    if await is_banned(msg.from_user.id): return await msg.answer("🚫 Заблокированы.")
    p = await refresh_pathogens(p)

    rank = get_rank(p["bio_exp"])
    next_thresh, next_rank = get_next_rank(p["bio_exp"])
    next_str = f"\n📈 До <b>{next_rank}</b>: <b>{next_thresh - p['bio_exp']}</b> опыта" if next_rank else ""

    has_fever = fever_active(p)
    is_inf    = infected_active(p)
    fever_str = infected_str = ""

    if has_fever:
        fu = datetime.datetime.fromisoformat(str(p["fever_until"]))
        rem = int((fu - datetime.datetime.utcnow()).total_seconds())
        h, m = divmod(rem // 60, 60)
        fever_str = f"\n🤒 <b>Горячка:</b> {h}ч {m}мин (/лечение)"

    if is_inf:
        iu = datetime.datetime.fromisoformat(str(p["infected_until"]))
        rem = int((iu - datetime.datetime.utcnow()).total_seconds())
        h, m = divmod(rem // 60, 60)
        infected_str = f"\n☣️ <b>Заражён:</b> {h}ч {m}мин"

    corp_str = ""
    if p.get("corp_id"):
        corp = await get_corp(p["corp_id"])
        if corp:
            corp_str = f"\n🏢 Корпорация: <b>[{corp['tag']}] {corp['name']}</b>"

    title_str = ""
    t = player_display_title(p)
    if t: title_str = f"\n{t}"

    ops_pct  = 0 if not p["operations_total"]  else round(p["operations_success"]/p["operations_total"]*100,1)
    prev_pct = 0 if not p["prevented_total"]   else round(p["prevented_success"]/p["prevented_total"]*100,1)

    await msg.answer(
        f"👤 <b>{p['full_name']}</b>  (@{p['username'] or '—'}){title_str}{corp_str}\n"
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
        f"😷 Спецопераций: <b>{p['operations_success']} из {p['operations_total']} ({ops_pct}%)</b>\n"
        f"🥷 Предотвращены: <b>{p['prevented_success']} из {p['prevented_total']} ({prev_pct}%)</b>\n"
        f"😤 Заражённых: <b>{p['infected_count']}</b>\n"
        f"🦠 Болезней: <b>{p['diseases_count']}</b>\n"
        f"🧪 Патогены: <b>{p['pathogens_ready']}/{p['pathogens_max']}</b>"
        f"{fever_str}{infected_str}"
    )


# ───────────────────────────────────────────────────────────────
#  ОБРАБОТЧИКИ ГЛАВНОГО МЕНЮ (inline кнопки)
# ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu_lab")
async def cb_menu_lab(cb: CallbackQuery):
    await cb.answer()
    await _show_lab(cb.message, user=cb.from_user)

@router.callback_query(F.data == "menu_profile")
async def cb_menu_profile(cb: CallbackQuery):
    await cb.answer()
    # создаём фейк msg-like объект через send_message
    uid = cb.from_user.id
    p = await get_or_create(uid, cb.from_user.username, cb.from_user.full_name)
    if await is_banned(uid): return await cb.message.answer("🚫 Заблокированы.")
    p = await refresh_pathogens(p)
    rank = get_rank(p["bio_exp"])
    next_thresh, next_rank = get_next_rank(p["bio_exp"])
    next_str = f"\n📈 До <b>{next_rank}</b>: <b>{next_thresh - p['bio_exp']}</b> опыта" if next_rank else ""
    has_fever = fever_active(p)
    is_inf    = infected_active(p)
    fever_str = infected_str = ""
    if has_fever:
        fu = datetime.datetime.fromisoformat(str(p["fever_until"]))
        rem = int((fu - datetime.datetime.utcnow()).total_seconds())
        h, m = divmod(rem // 60, 60)
        fever_str = f"\n🤒 <b>Горячка:</b> {h}ч {m}мин (/лечение)"
    if is_inf:
        iu = datetime.datetime.fromisoformat(str(p["infected_until"]))
        rem = int((iu - datetime.datetime.utcnow()).total_seconds())
        h, m = divmod(rem // 60, 60)
        infected_str = f"\n☣️ <b>Заражён:</b> {h}ч {m}мин"
    corp_str = ""
    if p.get("corp_id"):
        corp = await get_corp(p["corp_id"])
        if corp: corp_str = f"\n🏢 <b>[{corp['tag']}] {corp['name']}</b>"
    title_str = ""
    t = player_display_title(p)
    if t: title_str = f"\n{t}"
    ops_pct  = 0 if not p["operations_total"]  else round(p["operations_success"]/p["operations_total"]*100,1)
    prev_pct = 0 if not p["prevented_total"]   else round(p["prevented_success"]/p["prevented_total"]*100,1)
    await cb.message.answer(
        f"👤 <b>{p['full_name']}</b>  (@{p['username'] or '—'}){title_str}{corp_str}\n"
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
        f"😷 Спецопераций: <b>{p['operations_success']} из {p['operations_total']} ({ops_pct}%)</b>\n"
        f"🥷 Предотвращены: <b>{p['prevented_success']} из {p['prevented_total']} ({prev_pct}%)</b>\n"
        f"😤 Заражённых: <b>{p['infected_count']}</b>\n"
        f"🧪 Патогены: <b>{p['pathogens_ready']}/{p['pathogens_max']}</b>"
        f"{fever_str}{infected_str}",
        reply_markup=kb_main()
    )

@router.callback_query(F.data == "menu_infect")
async def cb_menu_infect(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "☣️ <b>Как заразить?</b>\n\n"
        "• Ответь на сообщение жертвы и напиши /заразить\n"
        "• /заразить @username\n"
        "• /заразить 123456789"
    )

@router.callback_query(F.data == "menu_top")
async def cb_menu_top(cb: CallbackQuery):
    await cb.answer()
    top = await get_top_players(10)
    if not top:
        return await cb.message.answer("Топ пуст.")
    medals = ["🥇","🥈","🥉"] + ["🔹"] * 7
    lines  = ["🏆 <b>ТОП-10 игроков</b> (по Био-Опыту)\n"]
    for i, p in enumerate(top):
        name  = p["full_name"] or p["username"] or str(p["user_id"])
        rank  = get_rank(p["bio_exp"])
        title = player_display_title(p)
        t_str = f" <i>{title}</i>" if title else ""
        lines.append(
            f"{medals[i]} {name}{t_str}\n"
            f"   {rank} | ☣️ {p['bio_exp']} | 😤 {p['infected_count']}"
        )
    await cb.message.answer("\n".join(lines), reply_markup=kb_main())

@router.callback_query(F.data == "menu_corp")
async def cb_menu_corp(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    p = await get_or_create(uid, cb.from_user.username, cb.from_user.full_name)
    if p.get("corp_id"):
        corp = await get_corp(p["corp_id"])
        if corp:
            corp_rank = get_corp_rank(corp["members_count"])
            return await cb.message.answer(
                f"🏢 <b>[{corp['tag']}] {corp['name']}</b>\n"
                f"{corp_rank}\n\n"
                f"👥 Участников: <b>{corp['members_count']}</b>\n"
                f"🧬 Био-Ресурсы: <b>{corp['bio_resource']:.1f}</b>\n"
                f"☣️ Био-Опыт: <b>{corp['bio_exp']}</b>\n"
                f"📝 {corp['description'] or '—'}",
                reply_markup=kb_corp_actions(p)
            )
    await cb.message.answer(
        "🏢 <b>Корпорации</b>\n\nТы не в корпорации.",
        reply_markup=kb_corp_actions(p)
    )

@router.callback_query(F.data == "menu_help")
async def cb_menu_help(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "☣️ <b>БИО-ВОЙНЫ — Помощь</b>\n\n"
        "<b>Атаки:</b>\n"
        "/заразить @user — по юзернейму\n"
        "/заразить 123456789 — по ID\n"
        "Ответь на сообщение + /заразить\n\n"
        "<b>Лаборатория:</b>\n"
        "/лаб или .лаб — открыть лабу\n"
        "/лечение — вылечить горячку\n\n"
        "<b>Корпорации:</b>\n"
        "/создатькорпорацию — создать\n"
        "/вступить ТЕГ — вступить\n"
        "/выйтиизкорп — выйти\n"
        "/топкланы — топ корпораций\n\n"
        "<b>Механика:</b>\n"
        "🦠 Заразность vs 🛡Иммунитет+🔒Безопасность\n"
        "☠️ Летальность → длительность заражения (до 24ч)\n"
        "🧪 Патогены тратятся на атаку\n"
        "🔭 Квалификация учёных → скорость патогенов (30мин→1мин)\n"
        "🤒 Горячка — нельзя атаковать, лечится за 🧬 или ждать"
    )

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

@router.message(Command("заразить"))
@router.message(F.text == "☣️ Заразить")
async def cmd_infect(msg: Message):
    uid = msg.from_user.id
    if await is_banned(uid): return await msg.answer("🚫 Заблокированы.")

    attacker = await get_or_create(uid, msg.from_user.username, msg.from_user.full_name)
    attacker = await refresh_pathogens(attacker)

    # Горячка
    if fever_active(attacker):
        fu  = datetime.datetime.fromisoformat(str(attacker["fever_until"]))
        rem = int((fu - datetime.datetime.utcnow()).total_seconds())
        h, m = divmod(rem // 60, 60)
        return await msg.answer(
            f"🤒 <b>У тебя горячка!</b> Ты не можешь атаковать.\n"
            f"Осталось: <b>{h}ч {m}мин</b>",
            reply_markup=kb_fever()
        )

    # Патогены
    if attacker["pathogens_ready"] < 1:
        timer = pathogen_timer_str(attacker)
        return await msg.answer(
            f"🧪 <b>Нет патогенов!</b>\n"
            f"Следующий патоген через: <b>{timer}</b>\n"
            f"Прокачай 🔭 Квалификацию учёных чтобы производить быстрее."
        )

    # Кнопка без цели
    if msg.text.strip() == "☣️ Заразить" and not msg.reply_to_message:
        return await msg.answer(
            "☣️ <b>Как заразить?</b>\n\n"
            "• Ответь на сообщение жертвы: /заразить\n"
            "• /заразить @username\n"
            "• /заразить 123456789"
        )

    target = await _resolve_target(msg)
    if not target:
        return await msg.answer(
            "❌ Цель не найдена!\n"
            "/заразить @username\n"
            "/заразить 123456789\n"
            "или ответь на сообщение жертвы"
        )

    if target["user_id"] == uid:
        return await msg.answer("🤦 Нельзя заражать самого себя!")
    if target["is_banned"]:
        return await msg.answer("❌ Игрок недоступен.")
    if target.get("event_immunity"):
        return await msg.answer("🛡 У цели <b>иммунитет события</b>!")
    if infected_active(target):
        iu  = datetime.datetime.fromisoformat(str(target["infected_until"]))
        rem = int((iu - datetime.datetime.utcnow()).total_seconds())
        h, m = divmod(rem // 60, 60)
        return await msg.answer(
            f"☣️ <b>{target['full_name']}</b> уже заражён!\n"
            f"Заражение спадёт через <b>{h}ч {m}мин</b>."
        )

    chance   = infect_chance(attacker, target)
    atk_roll = random.random()
    success  = atk_roll < chance
    reward   = 0.0
    now      = datetime.datetime.utcnow()

    # Тратим патоген
    await update_player(uid,
        pathogens_ready=attacker["pathogens_ready"] - 1,
        last_pathogen_at=now.isoformat(),
        operations_total=attacker["operations_total"] + 1
    )

    if success:
        inf_secs   = infected_seconds(attacker)
        fever_secs = fever_seconds(attacker)
        inf_until  = now + datetime.timedelta(seconds=inf_secs)
        fever_until = now + datetime.timedelta(seconds=fever_secs)
        reward = round(random.uniform(10, 30) + attacker["infection"] * 2, 2)

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
        # Обновляем Био-Опыт корпорации атакующего
        if attacker.get("corp_id"):
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE corporations SET bio_exp=bio_exp+10 WHERE id=?",
                    (attacker["corp_id"],))
                await db.commit()

        inf_h, inf_m   = divmod(inf_secs // 60, 60)
        fev_h, fev_m   = divmod(fever_secs // 60, 60)
        attacker2      = await get_player(uid)
        timer          = pathogen_timer_str(attacker2)

        await msg.answer(
            f"☣️ <b>ЗАРАЖЕНИЕ УСПЕШНО!</b>\n\n"
            f"🎯 Жертва: <b>{target['full_name']}</b>\n"
            f"🦠 Заразность: {attacker['infection']} vs "
            f"🛡{target['immunity']}+🔒{target['security']}\n"
            f"🎲 Шанс: {chance*100:.0f}%\n\n"
            f"⏳ Длительность: <b>{inf_h}ч {inf_m}мин</b>\n"
            f"🤒 Горячка жертвы: <b>{fev_h}ч {fev_m}мин</b>\n"
            f"💰 Получено: +<b>{reward}</b> 🧬\n\n"
            f"🧪 Патогены: <b>{attacker2['pathogens_ready']}/{attacker2['pathogens_max']}</b> "
            f"(след. через {timer})"
        )
        try:
            await msg.bot.send_message(
                target["user_id"],
                f"☣️ <b>ВАС ЗАРАЗИЛИ!</b>\n\n"
                f"Атаковал: <b>{attacker['full_name']}</b>\n"
                f"🤒 Горячка на <b>{fev_h}ч {fev_m}мин</b> — нельзя атаковать!\n"
                f"⏳ Заражение: <b>{inf_h}ч {inf_m}мин</b>\n"
                f"💊 Вылечить горячку: /лечение",
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
        timer     = pathogen_timer_str(attacker2)
        await msg.answer(
            f"🛡 <b>Атака отражена!</b>\n\n"
            f"🎯 Цель: <b>{target['full_name']}</b>\n"
            f"🦠 {attacker['infection']} vs 🛡{target['immunity']}+🔒{target['security']}\n"
            f"🎲 Шанс: {chance*100:.0f}%\n\n"
            f"🧪 Патогены: <b>{attacker2['pathogens_ready']}/{attacker2['pathogens_max']}</b> "
            f"(след. через {timer})"
        )

    await log_attack(uid, target["user_id"], int(success),
                     int(atk_roll * 100), int(chance * 100), reward)

# ───────────────────────────────────────────────────────────────
#  ГОРЯЧКА
# ───────────────────────────────────────────────────────────────

@router.message(Command("лечение"))
async def cmd_fever(msg: Message):
    p = await get_or_create(msg.from_user.id, msg.from_user.username, msg.from_user.full_name)
    if not fever_active(p):
        return await msg.answer("✅ Горячки нет!")
    fu  = datetime.datetime.fromisoformat(str(p["fever_until"]))
    rem = int((fu - datetime.datetime.utcnow()).total_seconds())
    h, m = divmod(rem // 60, 60)
    await msg.answer(
        f"🤒 <b>Горячка активна!</b>\n"
        f"Осталось: <b>{h}ч {m}мин</b>\n"
        f"💊 Вылечить за <b>{FEVER_HEAL_COST:.0f} 🧬</b>",
        reply_markup=kb_fever()
    )

@router.callback_query(F.data == "fever_heal")
async def cb_fever_heal(cb: CallbackQuery):
    p = await get_player(cb.from_user.id)
    if not fever_active(p):
        await cb.answer("✅ Горячки нет!", show_alert=True)
        return await cb.message.edit_text("✅ Ты здоров!")
    if p["bio_resource"] < FEVER_HEAL_COST:
        return await cb.answer(f"❌ Нужно {FEVER_HEAL_COST:.0f} 🧬", show_alert=True)
    await update_player(cb.from_user.id,
        bio_resource=p["bio_resource"] - FEVER_HEAL_COST,
        fever_until=None)
    await cb.answer("💊 Вылечен!", show_alert=True)
    await cb.message.edit_text(
        f"✅ <b>Горячка вылечена!</b>\n"
        f"Потрачено: <b>{FEVER_HEAL_COST:.0f} 🧬</b>"
    )

@router.callback_query(F.data == "fever_wait")
async def cb_fever_wait(cb: CallbackQuery):
    p = await get_player(cb.from_user.id)
    if not fever_active(p):
        return await cb.answer("✅ Горячки нет!", show_alert=True)
    fu  = datetime.datetime.fromisoformat(str(p["fever_until"]))
    rem = int((fu - datetime.datetime.utcnow()).total_seconds())
    h, m = divmod(rem // 60, 60)
    await cb.answer(f"⏳ Горячка пройдёт через {h}ч {m}мин", show_alert=True)

# ───────────────────────────────────────────────────────────────
#  ТОП
# ───────────────────────────────────────────────────────────────

@router.message(F.text == "🏆 Топ")
@router.message(Command("топ"))
async def cmd_top(msg: Message):
    top = await get_top_players(10)
    if not top:
        return await msg.answer("Топ пуст.")
    medals = ["🥇","🥈","🥉"] + ["🔹"] * 7
    lines  = ["🏆 <b>ТОП-10 игроков</b> (по Био-Опыту)\n"]
    for i, p in enumerate(top):
        name  = p["full_name"] or p["username"] or str(p["user_id"])
        rank  = get_rank(p["bio_exp"])
        title = player_display_title(p)
        t_str = f" <i>{title}</i>" if title else ""
        lines.append(
            f"{medals[i]} {name}{t_str}\n"
            f"   {rank} | ☣️ {p['bio_exp']} опыта | 😤 {p['infected_count']} заражений"
        )
    await msg.answer("\n".join(lines))

@router.message(Command("топкланы"))
async def cmd_top_corps(msg: Message):
    top = await get_top_corps(10)
    if not top:
        return await msg.answer("Топ корпораций пуст.")
    medals = ["🥇","🥈","🥉"] + ["🔹"] * 7
    lines  = ["🏢 <b>ТОП-10 корпораций</b>\n"]
    for i, c in enumerate(top):
        corp_rank = get_corp_rank(c["members_count"])
        lines.append(
            f"{medals[i]} <b>[{c['tag']}] {c['name']}</b>\n"
            f"   {corp_rank} | 👥 {c['members_count']} | ☣️ {c['bio_exp']} опыта"
        )
    await msg.answer("\n".join(lines))

# ───────────────────────────────────────────────────────────────
#  КОРПОРАЦИИ
# ───────────────────────────────────────────────────────────────

@router.message(F.text == "🏢 Корпорация")
@router.message(Command("корпорация"))
async def cmd_corp_menu(msg: Message):
    uid = msg.from_user.id
    if await is_banned(uid): return await msg.answer("🚫 Заблокированы.")
    p = await get_or_create(uid, msg.from_user.username, msg.from_user.full_name)
    if p.get("corp_id"):
        corp = await get_corp(p["corp_id"])
        if corp:
            corp_rank = get_corp_rank(corp["members_count"])
            return await msg.answer(
                f"🏢 <b>[{corp['tag']}] {corp['name']}</b>\n"
                f"{corp_rank}\n\n"
                f"👥 Участников: <b>{corp['members_count']}</b>\n"
                f"🧬 Био-Ресурсы: <b>{corp['bio_resource']:.1f}</b>\n"
                f"☣️ Био-Опыт: <b>{corp['bio_exp']}</b>\n"
                f"📝 {corp['description'] or '—'}",
                reply_markup=kb_corp_actions(p)
            )
    await msg.answer(
        "🏢 <b>Корпорации</b>\n\nТы не в корпорации.",
        reply_markup=kb_corp_actions(p)
    )

@router.message(Command("создатькорпорацию"))
@router.callback_query(F.data == "corp_create")
async def cmd_create_corp(event, state: FSMContext):
    msg = event if isinstance(event, Message) else event.message
    uid = event.from_user.id
    if await is_banned(uid):
        if isinstance(event, CallbackQuery): return await event.answer("🚫", show_alert=True)
        return await msg.answer("🚫 Заблокированы.")
    p = await get_player(uid)
    if p and p.get("corp_id"):
        txt = "❌ Ты уже в корпорации!"
        if isinstance(event, CallbackQuery): return await event.answer(txt, show_alert=True)
        return await msg.answer(txt)
    await msg.answer(
        "🏗 <b>Создание корпорации</b>\n\nВведи <b>название</b> (2–32 символа):",
        reply_markup=kb_cancel()
    )
    await state.set_state(S.corp_name)
    if isinstance(event, CallbackQuery): await event.answer()

@router.message(S.corp_name)
async def proc_corp_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 2 or len(name) > 32:
        return await msg.answer("❌ 2–32 символа.")
    if await get_corp_by_name(name):
        return await msg.answer("❌ Такое название уже занято!")
    await state.update_data(corp_name=name)
    await msg.answer(
        f"✅ Название: <b>{name}</b>\n\nВведи <b>тег</b> (2–6 символов, пример: BIO):",
        reply_markup=kb_cancel()
    )
    await state.set_state(S.corp_tag)

@router.message(S.corp_tag)
async def proc_corp_tag(msg: Message, state: FSMContext):
    tag = msg.text.strip().upper()
    if len(tag) < 2 or len(tag) > 6:
        return await msg.answer("❌ 2–6 символов.")
    if await get_corp_by_tag(tag):
        return await msg.answer("❌ Такой тег уже занят!")
    data = await state.get_data()
    name = data["corp_name"]
    uid  = msg.from_user.id
    corp = await create_corp(name, tag, uid)
    if not corp:
        await state.clear()
        return await msg.answer("❌ Ошибка создания. Попробуй другое название/тег.")
    await update_player(uid, corp_id=corp["id"])
    await state.clear()
    await msg.answer(
        f"🎉 <b>Корпорация создана!</b>\n\n"
        f"🏢 <b>[{tag}] {name}</b>\n"
        f"👑 Лидер: ты\n\n"
        f"Тег для вступления: <code>{tag}</code>",
        reply_markup=kb_main()
    )

@router.message(Command("вступить"))
async def cmd_join_corp(msg: Message):
    uid   = msg.from_user.id
    p     = await get_or_create(uid, msg.from_user.username, msg.from_user.full_name)
    if p.get("corp_id"):
        return await msg.answer("❌ Ты уже в корпорации! Сначала выйди (/выйтиизкорп).")
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await msg.answer("❌ Укажи тег: /вступить ТЕГ")
    corp = await get_corp_by_tag(parts[1].strip())
    if not corp:
        return await msg.answer(f"❌ Корпорация [{parts[1].strip().upper()}] не найдена.")
    await update_player(uid, corp_id=corp["id"])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE corporations SET members_count=members_count+1 WHERE id=?", (corp["id"],))
        await db.commit()
    await msg.answer(f"✅ Ты вступил в <b>[{corp['tag']}] {corp['name']}</b>!")

@router.message(Command("выйтиизкорп"))
@router.callback_query(F.data == "corp_leave")
async def cmd_leave_corp(event):
    uid = event.from_user.id
    p   = await get_player(uid)
    msg = event if isinstance(event, Message) else event.message
    if not p or not p.get("corp_id"):
        if isinstance(event, CallbackQuery): return await event.answer("❌ Ты не в корпорации", show_alert=True)
        return await msg.answer("❌ Ты не в корпорации.")
    corp = await get_corp(p["corp_id"])
    await update_player(uid, corp_id=None)
    if corp:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE corporations SET members_count=MAX(0,members_count-1) WHERE id=?",
                (corp["id"],))
            await db.commit()
    if isinstance(event, CallbackQuery):
        await event.answer("✅ Вышел из корпорации", show_alert=True)
        await event.message.edit_text("🚪 Ты покинул корпорацию.")
    else:
        await msg.answer("🚪 Ты покинул корпорацию.")

@router.callback_query(F.data == "corp_info")
async def cb_corp_info(cb: CallbackQuery):
    p = await get_player(cb.from_user.id)
    if not p or not p.get("corp_id"):
        return await cb.answer("❌ Ты не в корпорации", show_alert=True)
    corp = await get_corp(p["corp_id"])
    if not corp: return await cb.answer("❌ Корпорация не найдена", show_alert=True)
    corp_rank = get_corp_rank(corp["members_count"])
    await cb.message.edit_text(
        f"🏢 <b>[{corp['tag']}] {corp['name']}</b>\n"
        f"{corp_rank}\n\n"
        f"👥 Участников: <b>{corp['members_count']}</b>\n"
        f"🧬 Био-Ресурсы: <b>{corp['bio_resource']:.1f}</b>\n"
        f"☣️ Био-Опыт: <b>{corp['bio_exp']}</b>",
        reply_markup=kb_corp_actions(p)
    )
    await cb.answer()

@router.callback_query(F.data == "corp_search")
async def cb_corp_search(cb: CallbackQuery):
    await cb.message.answer("🔍 Для вступления: /вступить ТЕГ")
    await cb.answer()

# ───────────────────────────────────────────────────────────────
#  СИСТЕМА АДМИНИСТРАЦИИ
# ───────────────────────────────────────────────────────────────

async def _resolve_target_arg(arg: str) -> Optional[dict]:
    if arg.startswith("@"): return await get_player_by_username(arg)
    if arg.isdigit():       return await get_player(int(arg))
    return None

# /повысить @user 1-4 причина  (или 5 — только для владельца)
@router.message(Command("повысить"))
async def cmd_promote(msg: Message):
    uid   = msg.from_user.id
    level = await get_admin_level(uid)
    if level < 5 and uid != SUPER_ADMIN_ID:
        return await msg.answer("❌ Нет доступа.")

    parts = msg.text.strip().split(maxsplit=3)
    if len(parts) < 3:
        return await msg.answer(
            "❌ Формат: /повысить @user 1-5 причина\n\n"
            "Уровни:\n1 — Стажёр\n2 — Младший адм\n"
            "3 — Администратор\n4 — Старший адм\n5 — Со-владелец"
        )

    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Игрок не найден.")

    try:
        new_level = int(parts[2])
        if not 1 <= new_level <= 5: raise ValueError
    except ValueError:
        return await msg.answer("❌ Уровень от 1 до 5.")

    reason = parts[3] if len(parts) > 3 else "Не указана"

    # Владелец SUPER_ADMIN нельзя трогать
    if target["user_id"] == SUPER_ADMIN_ID:
        return await msg.answer("❌ Владельца нельзя трогать!")

    # Со-владелец может повышать только до уровня 2
    if uid != SUPER_ADMIN_ID and level == 5:
        if new_level > 2:
            # Отправляем запрос владельцу
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO promote_requests (requester_id,target_id,target_level,reason)"
                    " VALUES (?,?,?,?)",
                    (uid, target["user_id"], new_level, reason))
                await db.commit()
            try:
                req_player = await get_player(uid)
                await msg.bot.send_message(
                    SUPER_ADMIN_ID,
                    f"📨 <b>Запрос на повышение</b>\n\n"
                    f"От: <b>{req_player['full_name']}</b> (@{req_player['username'] or '—'})\n"
                    f"Хочет повысить: <b>{target['full_name']}</b> (@{target['username'] or '—'})\n"
                    f"На должность: <b>{ADMIN_TITLES.get(new_level, str(new_level))}</b>\n"
                    f"Причина: {reason}\n\n"
                    f"Используй /повысить @{target['username']} {new_level} {reason} для подтверждения."
                )
            except Exception:
                pass
            return await msg.answer(
                f"📨 Запрос отправлен владельцу.\n"
                f"Повышение {ADMIN_TITLES.get(new_level, '')} требует одобрения."
            )

    old_level = target.get("admin_level", 0)
    await set_admin_level(target["user_id"], new_level)
    await msg.answer(
        f"✅ <b>Повышение выполнено</b>\n\n"
        f"👤 {target['full_name']} (@{target['username'] or '—'})\n"
        f"📊 {ADMIN_TITLES.get(old_level,'Игрок')} → <b>{ADMIN_TITLES.get(new_level,'')}</b>\n"
        f"📝 Причина: {reason}"
    )
    try:
        await msg.bot.send_message(
            target["user_id"],
            f"🎉 <b>Вы повышены!</b>\n\n"
            f"Новая должность: <b>{ADMIN_TITLES.get(new_level,'')}</b>\n"
            f"Причина: {reason}"
        )
    except Exception:
        pass

# /разжаловать @user причина
@router.message(Command("разжаловать"))
async def cmd_demote(msg: Message):
    uid   = msg.from_user.id
    level = await get_admin_level(uid)
    if level < 4 and uid != SUPER_ADMIN_ID:
        return await msg.answer("❌ Нет доступа. Нужен уровень Старший администратор или выше.")

    parts = msg.text.strip().split(maxsplit=2)
    if len(parts) < 2:
        return await msg.answer("❌ Формат: /разжаловать @user причина")

    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Игрок не найден.")
    if target["user_id"] == SUPER_ADMIN_ID:
        return await msg.answer("❌ Владельца нельзя трогать!")
    if target["user_id"] == msg.from_user.id:
        return await msg.answer("❌ Нельзя разжаловать самого себя!")

    target_level = target.get("admin_level", 0)
    # Со-владелец может разжаловать только до уровня 2
    if level == 5 and uid != SUPER_ADMIN_ID and target_level > 2:
        return await msg.answer("❌ Со-владелец может разжаловать только Стажёров и Младших адм.")

    reason = parts[2] if len(parts) > 2 else "Не указана"
    await set_admin_level(target["user_id"], 0)
    await msg.answer(
        f"✅ <b>Разжалован</b>\n\n"
        f"👤 {target['full_name']}\n"
        f"📊 {ADMIN_TITLES.get(target_level,'Игрок')} → Игрок\n"
        f"📝 {reason}"
    )
    try:
        await msg.bot.send_message(
            target["user_id"],
            f"⚠️ <b>Вы разжалованы</b>\n📝 Причина: {reason}"
        )
    except Exception:
        pass

# /спрятать — скрыться из топа (Младший адм+)
@router.message(Command("спрятать"))
async def cmd_hide(msg: Message):
    uid = msg.from_user.id
    if not await is_admin(uid, min_level=2):
        return await msg.answer("❌ Нужен уровень Младший администратор или выше.")
    p = await get_player(uid)
    new_val = 0 if p.get("is_hidden") else 1
    await update_player(uid, is_hidden=new_val)
    if new_val:
        await msg.answer("👻 Ты скрыт из топов.")
    else:
        await msg.answer("👁 Ты снова виден в топах.")

# /изменить текст — изменить свою пометку (Стажёр+)
@router.message(Command("изменить"))
async def cmd_change_title(msg: Message):
    uid = msg.from_user.id
    if not await is_admin(uid, min_level=1):
        return await msg.answer("❌ Нужен уровень Стажёр или выше.")
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await msg.answer(
            "❌ Формат: /изменить Моя пометка\n"
            "Пример: /изменить 🌟 Куратор"
        )
    title = parts[1].strip()
    if len(title) > 32:
        return await msg.answer("❌ Пометка до 32 символов.")
    await update_player(uid, admin_title=title)
    await msg.answer(f"✅ Пометка изменена: <b>{title}</b>")

# ───────────────────────────────────────────────────────────────
#  БАН / РАЗБАН
# ───────────────────────────────────────────────────────────────

@router.message(Command("ban"))
async def cmd_ban(msg: Message):
    if not await is_admin(msg.from_user.id, min_level=4):
        return await msg.answer("❌ Нужен уровень Старший администратор или выше.")
    parts = msg.text.strip().split(maxsplit=2)
    if len(parts) < 2: return await msg.answer("❌ Формат: /ban @username причина")
    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Игрок не найден.")
    if target["user_id"] == SUPER_ADMIN_ID:
        return await msg.answer("❌ Владельца нельзя банить!")
    if target["user_id"] == msg.from_user.id:
        return await msg.answer("❌ Нельзя банить самого себя!")
    reason = parts[2] if len(parts) > 2 else "Не указана"
    await update_player(target["user_id"], is_banned=1)
    await msg.answer(
        f"🚫 <b>Игрок забанен</b>\n"
        f"👤 {target['full_name']} (@{target['username'] or '—'})\n"
        f"📝 {reason}"
    )
    try:
        await msg.bot.send_message(target["user_id"],
            f"🚫 <b>Вы заблокированы</b>\n📝 {reason}")
    except Exception:
        pass

@router.message(Command("unban"))
async def cmd_unban(msg: Message):
    if not await is_admin(msg.from_user.id, min_level=4):
        return await msg.answer("❌ Нужен уровень Старший администратор или выше.")
    parts = msg.text.strip().split()
    if len(parts) < 2: return await msg.answer("❌ Формат: /unban @username")
    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Игрок не найден.")
    await update_player(target["user_id"], is_banned=0)
    await msg.answer(f"✅ <b>Разбанен</b>\n👤 {target['full_name']}")
    try:
        await msg.bot.send_message(target["user_id"], "✅ Вы разблокированы!")
    except Exception:
        pass

# ───────────────────────────────────────────────────────────────
#  АДМИН-ПАНЕЛЬ
# ───────────────────────────────────────────────────────────────

EVENT_INFO = {
    "mutation":  {
        "title": "🦠 Мутация",
        "desc":  "Заразность +{bonus} на {hours}ч",
        "broadcast": "🦠 <b>МУТАЦИЯ!</b> Заразность всем +{bonus} на {hours}ч!",
    },
    "epidemic":  {
        "title": "💀 Эпидемия",
        "desc":  "Выдача ресурсов",
        "broadcast": "💀 <b>ЭПИДЕМИЯ!</b> Каждый получил +{bonus} 🧬! ({hours}ч)",
    },
    "quarantine":{
        "title": "🛡 Карантин",
        "desc":  "Карантин {hours}ч",
        "broadcast": "🛡 <b>КАРАНТИН!</b> Все атаки заблокированы на {hours}ч!",
    },
    "biowar":    {
        "title": "⚔️ Биовойна",
        "desc":  "Бонус Био-Опыта",
        "broadcast": "⚔️ <b>БИОВОЙНА!</b> Бонус Био-Опыта +{bonus}% на {hours}ч!",
    },
    "loot":      {
        "title": "🎁 Трофеи",
        "desc":  "Случайные ресурсы",
        "broadcast": "🎁 <b>ТРОФЕИ!</b> {count} игроков получат по {bonus} 🧬!",
    },
}

@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    if not await is_admin(msg.from_user.id):
        return await msg.answer("❌ Нет доступа.")
    level = await get_admin_level(msg.from_user.id)
    title = ADMIN_TITLES.get(level, "")
    await msg.answer(
        f"🔧 <b>Админ-панель</b>\n"
        f"Ваш уровень: <b>{title}</b>\n\n"
        f"📌 Команды:\n"
        f"/выдать @user 500 — 🧬 Ресурсы\n"
        f"/выдатьопыт @user 100 — ☣️ Опыт игроку\n"
        f"/выдатьопыткорп ТЕГ 100 — ☣️ Опыт корпорации\n"
        f"/ban @user причина — 🚫 Бан (ур.4+)\n"
        f"/unban @user — ✅ Разбан (ур.4+)\n"
        f"/повысить @user 1-5 причина — 🎖 Повысить (ур.5+)\n"
        f"/разжаловать @user причина — 🔽 Разжаловать (ур.4+)\n"
        f"/спрятать — 👻 Скрыться из топа (ур.2+)\n"
        f"/изменить текст — ✏️ Пометка (ур.1+)\n"
        f"/setlabid @user ID — 🔑 Кастомный Lab ID",
        reply_markup=kb_admin_main()
    )

@router.callback_query(F.data == "adm_stats")
async def cb_adm_stats(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    players = await get_all_players()
    total  = len(players)
    banned = sum(1 for p in players if p["is_banned"])
    await cb.message.edit_text(
        f"🔧 <b>Админ-панель</b>\n\n"
        f"📊 Игроков: <b>{total}</b>\n"
        f"🚫 Заблокировано: <b>{banned}</b>",
        reply_markup=kb_admin_main()
    )
    await cb.answer()

@router.callback_query(F.data == "adm_give")
async def cb_adm_give(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id, min_level=3): return await cb.answer("❌ Нужен ур.3+", show_alert=True)
    await cb.message.edit_text(
        "🔧 <b>Выдача ресурсов</b>\n\n"
        "/выдать @username 500\n"
        "/выдать 123456789 500",
        reply_markup=kb_admin_main()
    )
    await cb.answer()

@router.callback_query(F.data == "adm_labid")
async def cb_adm_labid(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    await cb.message.edit_text(
        "🔑 <b>Кастомный Lab ID</b>\n\n"
        "/setlabid @username НОВЫЙ_ID\n"
        "/setlabid 123456789 НОВЫЙ_ID\n\n"
        "2–16 символов, уникальный.",
        reply_markup=kb_admin_main()
    )
    await cb.answer()

@router.callback_query(F.data == "adm_help")
async def cb_adm_help(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    await cb.message.edit_text(
        "📋 <b>Все команды администратора</b>\n\n"
        "/admin — панель\n"
        "/выдать @user 500 — ресурсы\n"
        "/выдатьопыт @user 100 — опыт игроку\n"
        "/выдатьопыткорп ТЕГ 100 — опыт корпорации\n"
        "/ban @user причина — бан (ур.4+)\n"
        "/unban @user — разбан (ур.4+)\n"
        "/повысить @user 1-5 причина (ур.5+)\n"
        "/разжаловать @user причина (ур.4+)\n"
        "/спрятать — скрыть из топа (ур.2+)\n"
        "/изменить текст — пометка (ур.1+)\n"
        "/setlabid @user ID — кастомный Lab ID",
        reply_markup=kb_admin_main()
    )
    await cb.answer()

# ── Выдать ресурсы (ур.3+, себе) / ур.9 любому ──────────────

@router.message(Command("выдать"))
async def cmd_give(msg: Message):
    uid   = msg.from_user.id
    level = await get_admin_level(uid)
    if level < 3: return await msg.answer("❌ Нужен уровень Администратор или выше.")

    parts = msg.text.strip().split()
    if len(parts) < 3: return await msg.answer("❌ /выдать @user 500")

    # Ур.3 и 4 могут выдавать только себе
    if level in (3, 4):
        target_arg = parts[1]
        t = await _resolve_target_arg(target_arg)
        if t and t["user_id"] != uid:
            return await msg.answer("❌ Ты можешь выдавать ресурсы только себе.")
        target = await get_player(uid)
    else:
        target = await _resolve_target_arg(parts[1])

    if not target: return await msg.answer("❌ Игрок не найден.")
    try:
        amount = float(parts[2])
        if amount <= 0: raise ValueError
    except ValueError:
        return await msg.answer("❌ Положительное число.")

    new_bal = target["bio_resource"] + amount
    await update_player(target["user_id"], bio_resource=new_bal)
    await msg.answer(
        f"✅ +{amount:.0f} 🧬\n"
        f"👤 {target['full_name']}\n"
        f"💰 {target['bio_resource']:.1f} → <b>{new_bal:.1f}</b>"
    )
    if target["user_id"] != uid:
        try:
            await msg.bot.send_message(target["user_id"],
                f"🎁 Тебе выдали <b>{amount:.0f} 🧬</b>!\n"
                f"Новый баланс: <b>{new_bal:.1f}</b>")
        except Exception:
            pass

# ── Выдать опыт игроку ──────────────────────────────────────

@router.message(Command("выдатьопыт"))
async def cmd_give_exp(msg: Message):
    if not await is_admin(msg.from_user.id, min_level=3):
        return await msg.answer("❌ Нужен уровень Администратор или выше.")
    parts = msg.text.strip().split()
    if len(parts) < 3: return await msg.answer("❌ /выдатьопыт @user 100")
    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Игрок не найден.")
    try:
        amount = int(parts[2])
        if amount <= 0: raise ValueError
    except ValueError:
        return await msg.answer("❌ Положительное число.")
    new_exp = target["bio_exp"] + amount
    await update_player(target["user_id"], bio_exp=new_exp)
    await msg.answer(
        f"✅ +{amount} ☣️ Био-Опыта\n"
        f"👤 {target['full_name']}\n"
        f"Опыт: {target['bio_exp']} → <b>{new_exp}</b>\n"
        f"Ранг: <b>{get_rank(new_exp)}</b>"
    )
    try:
        await msg.bot.send_message(target["user_id"],
            f"🎁 Тебе выдали <b>{amount} ☣️ Био-Опыта</b>!\n"
            f"Новый опыт: <b>{new_exp}</b> | Ранг: <b>{get_rank(new_exp)}</b>")
    except Exception:
        pass

# ── Выдать опыт корпорации ──────────────────────────────────

@router.message(Command("выдатьопыткорп"))
async def cmd_give_corp_exp(msg: Message):
    if not await is_admin(msg.from_user.id, min_level=3):
        return await msg.answer("❌ Нужен уровень Администратор или выше.")
    parts = msg.text.strip().split()
    if len(parts) < 3: return await msg.answer("❌ /выдатьопыткорп ТЕГ 100")
    corp = await get_corp_by_tag(parts[1].strip())
    if not corp: return await msg.answer(f"❌ Корпорация [{parts[1].upper()}] не найдена.")
    try:
        amount = int(parts[2])
        if amount <= 0: raise ValueError
    except ValueError:
        return await msg.answer("❌ Положительное число.")
    new_exp = corp["bio_exp"] + amount
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE corporations SET bio_exp=? WHERE id=?", (new_exp, corp["id"]))
        await db.commit()
    await msg.answer(
        f"✅ Корпорации <b>[{corp['tag']}] {corp['name']}</b>\n"
        f"+{amount} ☣️ Опыта → <b>{new_exp}</b>"
    )

# ── Кастомный Lab ID ────────────────────────────────────────

@router.message(Command("setlabid"))
async def cmd_setlabid(msg: Message):
    if not await is_admin(msg.from_user.id):
        return await msg.answer("❌ Нет доступа.")
    parts = msg.text.strip().split()
    if len(parts) < 3: return await msg.answer("❌ /setlabid @user НОВЫЙ_ID")
    target = await _resolve_target_arg(parts[1])
    if not target: return await msg.answer("❌ Игрок не найден.")
    new_id = parts[2].upper()
    if not (2 <= len(new_id) <= 16):
        return await msg.answer("❌ ID: 2–16 символов.")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM players WHERE lab_id=? AND user_id!=?",
            (new_id, target["user_id"])) as c:
            if await c.fetchone():
                return await msg.answer(f"❌ ID <code>{new_id}</code> уже занят!")
    old_id = target["lab_id"]
    await update_player(target["user_id"], lab_id=new_id)
    await msg.answer(
        f"✅ Lab ID изменён\n"
        f"👤 {target['full_name']}\n"
        f"<code>{old_id}</code> → <code>{new_id}</code>"
    )
    try:
        await msg.bot.send_message(target["user_id"],
            f"🔑 Твой Lab ID изменён!\nНовый: <code>{new_id}</code>")
    except Exception:
        pass

# ── Рассылка ────────────────────────────────────────────────

@router.callback_query(F.data == "adm_broadcast")
async def cb_adm_broadcast(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    await cb.message.answer(
        "📢 <b>Рассылка</b>\n\nВведи текст (HTML поддерживается):",
        reply_markup=kb_cancel()
    )
    await state.set_state(S.broadcast_text)
    await cb.answer()

@router.message(S.broadcast_text)
async def proc_broadcast(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id): return
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

@router.callback_query(F.data == "adm_events")
async def cb_adm_events(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    btns = [[InlineKeyboardButton(text=v["title"], callback_data=f"event_start:{k}")]
            for k, v in EVENT_INFO.items()]
    active = await get_active_events()
    for ev in active:
        btns.append([InlineKeyboardButton(
            text=f"🛑 Стоп: {ev['title']}",
            callback_data=f"event_stop:{ev['id']}"
        )])
    await cb.message.edit_text(
        "☣️ <b>События</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
    )
    await cb.answer()

@router.callback_query(F.data.startswith("event_stop:"))
async def cb_event_stop(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return await cb.answer("❌", show_alert=True)
    eid = int(cb.data.split(":")[1])
    await deactivate_event(eid)
    players = await get_all_players()
    for p in players:
        if p["is_banned"]: continue
        try:
            await cb.bot.send_message(p["user_id"],
                "☣️ <b>Событие завершено!</b>")
        except Exception: pass
        await asyncio.sleep(0.05)
    await cb.message.edit_text("✅ Событие остановлено.", reply_markup=kb_admin_main())
    await cb.answer()

@router.callback_query(F.data.startswith("event_start:"))
async def cb_event_start(cb: CallbackQuery, state: FSMContext):
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
        "mutation":   "🦠 На сколько ур. повысить заразность? (1–10):",
        "epidemic":   "💰 Сколько 🧬 выдать каждому?",
        "quarantine": "🛡 Иммунитет всем? (да/нет):",
        "biowar":     "⚔️ На сколько % бонус Био-Опыта?",
        "loot":       "🎁 Сколько случайных игроков получат награду?",
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
        await msg.answer("💰 Сколько 🧬 получит каждый счастливчик?")
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
    logger.info("Иммунитет карантина снят")

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

    await create_event(etype, info["title"], info["desc"], "{}", hours)

    winner_ids_set = {w["user_id"] for w in winners}
    sent = 0
    status = await msg.answer(f"📢 0/{len(active_players)}")
    for i, p in enumerate(active_players):
        try:
            await msg.bot.send_message(p["user_id"], broadcast_text)
            if etype == "loot" and p["user_id"] in winner_ids_set:
                la = data.get("loot_amount", 100)
                await msg.bot.send_message(p["user_id"],
                    f"🎉 <b>ПОВЕЗЛО!</b> +{la} 🧬!")
            sent += 1
        except Exception: pass
        if (i+1) % 25 == 0:
            try: await status.edit_text(f"📢 {i+1}/{len(active_players)}")
            except Exception: pass
        await asyncio.sleep(0.05)

    await status.edit_text(
        f"✅ <b>Событие '{info['title']}' запущено!</b>\n"
        f"⏱ {hours}ч | 📢 {sent} игроков"
    )
    await state.clear()

# ───────────────────────────────────────────────────────────────
#  ПОМОЩЬ
# ───────────────────────────────────────────────────────────────

@router.message(F.text == "ℹ️ Помощь")
@router.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "☣️ <b>БИО-ВОЙНЫ — Помощь</b>\n\n"
        "<b>Атаки:</b>\n"
        "/заразить @user — по юзернейму\n"
        "/заразить 123456789 — по ID\n"
        "Ответь на сообщение + /заразить\n\n"
        "<b>Лаборатория:</b>\n"
        ".лаб — открыть лабу\n"
        "/лечение — вылечить горячку\n\n"
        "<b>Корпорации:</b>\n"
        "/создатькорпорацию — создать\n"
        "/вступить ТЕГ — вступить\n"
        "/выйтиизкорп — выйти\n"
        "/топкланы — топ корпораций\n\n"
        "<b>Механика:</b>\n"
        "🦠 Заразность vs 🛡Иммунитет+🔒Безопасность\n"
        "☠️ Летальность → длительность (до 24ч)\n"
        "🧪 Патогены тратятся на атаку\n"
        "🔭 Квалификация учёных → скорость патогенов (30мин→1мин)\n"
        "🤒 Горячка после заражения — нельзя атаковать\n"
        "💊 Лечение: /лечение (за 🧬 или подождать)"
    )

# ───────────────────────────────────────────────────────────────
#  ОТМЕНА
# ───────────────────────────────────────────────────────────────

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

    p = await get_player(SUPER_ADMIN_ID)
    if p:
        if p.get("admin_level", 0) != 9:
            await update_player(SUPER_ADMIN_ID, admin_level=9)
    await set_admin_level(SUPER_ADMIN_ID, 9)
    logger.info(f"Владелец: {SUPER_ADMIN_ID}")

    await start_web()
    asyncio.create_task(self_ping())
    logger.info("Антисон запущен ✅")

    bot = Bot(token=BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp  = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Бот запущен ✅")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
