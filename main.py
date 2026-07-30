import asyncio
import base64
import html
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
import urllib.error
import urllib.parse
import urllib.request

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv


# -----------------------------------------------------------------------------
# Configuração
# -----------------------------------------------------------------------------

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS_TEXT = os.getenv("ADMIN_IDS", "").strip()
DB_PATH = os.getenv("DB_PATH", "bot.db").strip()
WEB_RESULTS_URL = os.getenv("WEB_RESULTS_URL", "https://mobixretornoconsulta.discloud.app").strip().rstrip("/")
RESULTS_API_SECRET = os.getenv("RESULTS_API_SECRET", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("Defina BOT_TOKEN no arquivo .env")

if not ADMIN_IDS_TEXT:
    raise RuntimeError("Defina ADMIN_IDS no arquivo .env")

try:
    ADMIN_IDS = {
        int(admin_id.strip())
        for admin_id in ADMIN_IDS_TEXT.split(",")
        if admin_id.strip()
    }
except ValueError as error:
    raise RuntimeError("ADMIN_IDS aceita somente IDs numéricos separados por vírgula") from error


DEFAULT_START = (
    "<b>Olá, {first_name}!</b> 👋\n\n"
    "Bem-vindo ao nosso bot.\n"
    "Seu ID: <code>{user_id}</code>"
)

DEFAULT_BUTTONS = [
    {"text": "Bases", "url": "", "emoji_id": "", "style": "primary", "row": 0, "action": "bases"},
    {"text": "Perfil", "url": "", "emoji_id": "", "style": "primary", "row": 0},
    {"text": "Suporte", "url": "", "emoji_id": "", "style": "success", "row": 1},
    {"text": "Dev", "url": "", "emoji_id": "", "style": "danger", "row": 1},
    {"text": "Planos", "url": "", "emoji_id": "", "style": "success", "row": 2, "action": "plans"},
    {"text": "Grupo de referência", "url": "", "emoji_id": "", "style": "primary", "row": 3},
]

DEFAULT_BASES = [
    {"name": "📡 Consulta CpF v1", "online": True, "url": "/api/consulta/cpf/v1?apikey=SeuToken&code=88222144634"},
    {"name": "📡 Consulta CpF v2", "online": True, "url": "/api/consulta/cpf/v2?apikey=SeuToken&code=88222144634"},
    {"name": "📡 Consulta CpF v3 Com foto do RJ MA RO SP CE BA", "online": True, "url": "/api/consulta/cpf/v3?apikey=SeuToken&code=88222144634"},
    {"name": "📡 Consulta CpF v4", "online": True, "url": "/api/consulta/cpf/v4?apikey=SeuToken&code=12537664795"},
    {"name": "📡 Consulta CpF v5 Completo", "online": True, "url": "/api/consulta/cpf/v4?apikey=SeuToken&code=12537664795"},
    {"name": "📡 Consulta Cpf dadsus", "online": True, "url": "/api/consulta/cpfsus/v1?apikey=SeuToken&cpf=00005683505"},
    {"name": "📸 Consulta fotonacional", "online": True, "url": "/api/consulta/fotonaci/v1?apikey=SeuToken&cpf=00005683505"},
    {"name": "📡 Consulta inss", "online": False, "url": "/api/consulta/inss/v1?apikey=SeuToken&cpf=86712780268"},
    {"name": "📡 Consulta Score", "online": True, "url": "/api/consulta/score/v1?apikey=SeuToken&cpf=86712780268"},
    {"name": "📸 Consulta Fotope v1", "online": True, "url": "/api/consulta/fotope/v1?apikey=SeuToken&nome=JOSENILDA%20MARIA%20DE%20ARRUDA"},
    {"name": "👤 Consulta Nome v1", "online": True, "url": "/api/consulta/nome/v1?apikey=SeuToken&nome=PEDRO%20ADAO%20FERREIRA%20DA%20SILVA"},
    {"name": "👤 Consulta Nome v2", "online": True, "url": "/api/consulta/nome/v2?apikey=SeuToken&nome=PEDRO%20FERREIRA%20DA%20SILVA"},
    {"name": "🚙 Consulta Placa Josn", "online": True, "url": "/api/consulta/placa/v1?apikey=SeuToken&placa=MIT9067"},
    {"name": "🚙 Consulta Placa v2", "online": True, "url": "/api/consulta/placa/v2?apikey=SeuToken&placa=MIT9067"},
    {"name": "🚙 Consulta Placa v3", "online": True, "url": "/api/consulta/placa/v3?apikey=SeuToken&placa=ABC1234"},
    {"name": "📞 Consulta Telefone v1", "online": True, "url": "/api/consulta/telefone/v1?apikey=SeuToken&telefone=93991415396"},
    {"name": "📞 Consulta Telefone v2", "online": False, "url": "/api/consulta/telefone/v2?apikey=SeuToken&telefone=81982112719"},
    {"name": "⚙️ Consulta Email v1", "online": True, "url": "/api/consulta/email/v1?apikey=SeuToken&email=marcelo_polli%40terra.com.br"},
    {"name": "🌐 Consulta Cep v1", "online": False, "url": "/api/consulta/cep/v1?apikey=SeuToken&cep=11436100"},
    {"name": "🗺️ Consulta CNPJ v1", "online": True, "url": "/api/consulta/cnpj/v1?apikey=SeuToken&cnpj=00910509000171"},
    {"name": "🗺️ Consulta CNPJ FGTS", "online": True, "url": "/api/consulta/cnpjFGTS/v2?apikey=SeuToken&cnpj=00910509000171"},
    {"name": "🧰 Consulta Motor v1", "online": True, "url": "/api/consulta/motor/v1?apikey=SeuToken&motor=GFG138175"},
    {"name": "⚙️ Consulta Chassi v1", "online": True, "url": "/api/consulta/chassi/v1?apikey=SeuToken&chassi=9BGKL48U0"},
]

DEFAULT_API_BASE_URL = "http://node.tconect.xyz:1116/"
DEFAULT_MISTICPAY_URL = "https://api.misticpay.com/"
DEFAULT_PAYMENT_CPF = "71422400409"
AUTO_DELETE_SECONDS = 120

API_COMMANDS = [
    {
        "aliases": ["cpf", "cpf1"],
        "title": "Consulta CPF v1",
        "path": "api/consulta/cpf/v1",
        "param": "code",
        "example": "00005683505",
    },
    {
        "aliases": ["cpf2"],
        "title": "Consulta CPF v2",
        "path": "api/consulta/cpf/v2",
        "param": "code",
        "example": "00005683505",
    },
    {
        "aliases": ["cpf3"],
        "title": "Consulta CPF v3",
        "path": "api/consulta/cpf/v3",
        "param": "code",
        "example": "00005683505",
    },
    {
        "aliases": ["cpf4"],
        "title": "Consulta CPF v4",
        "path": "api/consulta/cpf/v4",
        "param": "code",
        "example": "00005683505",
    },
    {
        "aliases": ["cpf5"],
        "title": "Consulta CPF v5",
        "path": "api/consulta/cpf/v4",
        "param": "code",
        "example": "00005683505",
    },
    {
        "aliases": ["nome", "nome1"],
        "title": "Consulta Nome v1",
        "path": "api/consulta/nome/v1",
        "param": "nome",
        "example": "PEDRO ADAO FERREIRA DA SILVA",
    },
    {
        "aliases": ["nome2"],
        "title": "Consulta Nome v2",
        "path": "api/consulta/nome/v2",
        "param": "nome",
        "example": "PEDRO FERREIRA DA SILVA",
    },
    {
        "aliases": ["placa", "placa1"],
        "title": "Consulta Placa v1",
        "path": "api/consulta/placa/v1",
        "param": "placa",
        "example": "MIT9067",
    },
    {
        "aliases": ["placa2"],
        "title": "Consulta Placa v2",
        "path": "api/consulta/placa/v2",
        "param": "placa",
        "example": "MIT9067",
    },
    {
        "aliases": ["placa3"],
        "title": "Consulta Placa v3",
        "path": "api/consulta/placa/v3",
        "param": "placa",
        "example": "ABC1234",
    },
    {
        "aliases": ["telefone", "telefone1"],
        "title": "Consulta Telefone v1",
        "path": "api/consulta/telefone/v1",
        "param": "telefone",
        "example": "93991415396",
    },
    {
        "aliases": ["telefone2"],
        "title": "Consulta Telefone v2",
        "path": "api/consulta/telefone/v2",
        "param": "telefone",
        "example": "81982112719",
    },
    {
        "aliases": ["email"],
        "title": "Consulta Email v1",
        "path": "api/consulta/email/v1",
        "param": "email",
        "example": "marcelo_polli@terra.com.br",
    },
    {
        "aliases": ["cep"],
        "title": "Consulta CEP v1",
        "path": "api/consulta/cep/v1",
        "param": "cep",
        "example": "11436100",
    },
    {
        "aliases": ["cnpj"],
        "title": "Consulta CNPJ v1",
        "path": "api/consulta/cnpj/v1",
        "param": "cnpj",
        "example": "00910509000171",
    },
    {
        "aliases": ["cnpjfgts"],
        "title": "Consulta CNPJ FGTS",
        "path": "api/consulta/cnpjFGTS/v2",
        "param": "cnpj",
        "example": "00910509000171",
    },
    {
        "aliases": ["motor"],
        "title": "Consulta Motor v1",
        "path": "api/consulta/motor/v1",
        "param": "motor",
        "example": "GFG138175",
    },
    {
        "aliases": ["chassi"],
        "title": "Consulta Chassi v1",
        "path": "api/consulta/chassi/v1",
        "param": "chassi",
        "example": "9BWZZZ377VT004251",
    },
    {
        "aliases": ["score"],
        "title": "Consulta Score v1",
        "path": "api/consulta/score/v1",
        "param": "cpf",
        "example": "86712780268",
    },
    {
        "aliases": ["foto", "fotonacional"],
        "title": "Consulta Foto Nacional",
        "path": "api/consulta/fotonaci/v1",
        "param": "cpf",
        "example": "00005683505",
    },
    {
        "aliases": ["fotope"],
        "title": "Consulta Foto PE v1",
        "path": "api/consulta/fotope/v1",
        "param": "nome",
        "example": "JOSENILDA MARIA DE ARRUDA",
    },
    {
        "aliases": ["cpfsus"],
        "title": "Consulta CPF DATASUS",
        "path": "api/consulta/cpfsus/v1",
        "param": "cpf",
        "example": "00005683505",
    },
    {
        "aliases": ["inss"],
        "title": "Consulta INSS",
        "path": "api/consulta/inss/v1",
        "param": "cpf",
        "example": "86712780268",
    },
]

API_COMMAND_LOOKUP = {
    alias: spec
    for spec in API_COMMANDS
    for alias in spec["aliases"]
}

HIDDEN_RESPONSE_FIELDS = {"status", "resposta", "developer", "developer2"}

BASE_COMMAND_EXAMPLES = {
    "cpf": "cpf",
    "cpf1": "cpf",
    "cpf2": "cpf2",
    "cpf3": "cpf3",
    "cpf4": "cpf4",
    "cpf5": "cpf5",
    "nome": "nome",
    "nome2": "nome2",
    "placa": "placa",
    "placa2": "placa2",
    "placa3": "placa3",
    "telefone": "telefone",
    "telefone2": "telefone2",
    "email": "email",
    "cep": "cep",
    "cnpj": "cnpj",
    "cnpjfgts": "cnpjfgts",
    "motor": "motor",
    "chassi": "chassi",
    "score": "score",
    "foto": "foto",
    "fotonacional": "foto",
    "fotope": "fotope",
    "cpfsus": "cpfsus",
    "inss": "inss",
}

MISTICPAY_CREATE_PATH = "api/transactions/create"
MISTICPAY_CHECK_PATH = "api/transactions/check"


# -----------------------------------------------------------------------------
# Banco de dados SQLite
# -----------------------------------------------------------------------------

async def setup_database() -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute("PRAGMA journal_mode=WAL")
        await database.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                start_text TEXT NOT NULL,
                photo_file_id TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {
            row[1] for row in await (await database.execute("PRAGMA table_info(settings)" )).fetchall()
        }
        if "button_config" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN button_config TEXT")
        if "base_config" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN base_config TEXT")
        if "api_base_url" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN api_base_url TEXT")
        if "api_key" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN api_key TEXT")
        if "misticpay_url" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN misticpay_url TEXT")
        if "misticpay_client_id" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN misticpay_client_id TEXT")
        if "misticpay_client_secret" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN misticpay_client_secret TEXT")
        if "payment_reference_channel_id" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN payment_reference_channel_id TEXT")
        if "payment_logs_channel_id" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN payment_logs_channel_id TEXT")
        if "force_join_enabled" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN force_join_enabled INTEGER")
        await database.execute(
            "INSERT OR IGNORE INTO settings(id, start_text) VALUES(1, ?)",
            (DEFAULT_START,),
        )
        await database.execute(
            "UPDATE settings SET button_config = ? WHERE button_config IS NULL",
            (json.dumps(DEFAULT_BUTTONS, ensure_ascii=False),),
        )
        await database.execute(
            "UPDATE settings SET base_config = ? WHERE base_config IS NULL",
            (json.dumps(DEFAULT_BASES, ensure_ascii=False),),
        )
        await database.execute(
            "UPDATE settings SET api_base_url = ? WHERE api_base_url IS NULL",
            (DEFAULT_API_BASE_URL,),
        )
        await database.execute(
            "UPDATE settings SET api_key = ? WHERE api_key IS NULL",
            ("",),
        )
        await database.execute(
            "UPDATE settings SET misticpay_url = ? WHERE misticpay_url IS NULL",
            (DEFAULT_MISTICPAY_URL,),
        )
        await database.execute(
            "UPDATE settings SET misticpay_client_id = ? WHERE misticpay_client_id IS NULL",
            ("",),
        )
        await database.execute(
            "UPDATE settings SET misticpay_client_secret = ? WHERE misticpay_client_secret IS NULL",
            ("",),
        )
        await database.execute(
            "UPDATE settings SET payment_reference_channel_id = ? WHERE payment_reference_channel_id IS NULL",
            ("",),
        )
        await database.execute(
            "UPDATE settings SET payment_logs_channel_id = ? WHERE payment_logs_channel_id IS NULL",
            ("",),
        )
        await database.execute(
            "UPDATE settings SET force_join_enabled = ? WHERE force_join_enabled IS NULL",
            (0,),
        )
        await database.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payer_name TEXT NOT NULL,
                payer_document TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                raw_response TEXT
            )
            """
        )
        transaction_columns = {
            row[1] for row in await (await database.execute("PRAGMA table_info(transactions)")).fetchall()
        }
        if "plan_id" not in transaction_columns:
            await database.execute("ALTER TABLE transactions ADD COLUMN plan_id INTEGER")
        if "plan_target_type" not in transaction_columns:
            await database.execute("ALTER TABLE transactions ADD COLUMN plan_target_type TEXT")
        if "plan_target_id" not in transaction_columns:
            await database.execute("ALTER TABLE transactions ADD COLUMN plan_target_id INTEGER")
        await database.execute(
            """
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL CHECK(category IN ('user', 'group')),
                duration_days INTEGER NOT NULL,
                price REAL NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await database.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                target_type TEXT NOT NULL CHECK(target_type IN ('user', 'group')),
                target_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(plan_id, target_type, target_id)
            )
            """
        )
        await database.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT,
                first_chat_id INTEGER NOT NULL,
                first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await database.execute(
            """
            CREATE TABLE IF NOT EXISTS result_deliveries (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                result_text TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await database.execute(
            """
            INSERT OR IGNORE INTO plans (id, name, category, duration_days, price, active)
            VALUES (0, '[Sistema] Liberacao manual', 'user', 1, 0, 0)
            """
        )
        await database.commit()


async def get_settings() -> tuple[str, str | None]:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            "SELECT start_text, photo_file_id FROM settings WHERE id = 1"
        )
        row = await cursor.fetchone()
    return (row[0], row[1]) if row else (DEFAULT_START, None)


async def register_user(message: Message) -> bool:
    """Registra a primeira entrada e atualiza os dados básicos nas próximas visitas."""
    user = message.from_user
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute("SELECT 1 FROM users WHERE user_id = ?", (user.id,))
        is_new = await cursor.fetchone() is None
        await database.execute(
            """
            INSERT INTO users (
                user_id, username, first_name, last_name, language_code, first_chat_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                language_code = excluded.language_code,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            (
                user.id,
                user.username,
                user.first_name,
                user.last_name,
                user.language_code,
                message.chat.id,
            ),
        )
        await database.commit()
    if is_new:
        logger.info("Novo usuário registrado | id=%s | username=%s", user.id, user.username or "sem_username")
    return is_new


async def get_api_settings() -> tuple[str, str]:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            "SELECT api_base_url, api_key FROM settings WHERE id = 1"
        )
        row = await cursor.fetchone()
    if not row:
        return DEFAULT_API_BASE_URL, ""
    return (row[0] or DEFAULT_API_BASE_URL, row[1] or "")


async def get_misticpay_settings() -> tuple[str, str, str, str, str]:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            """
            SELECT misticpay_url, misticpay_client_id, misticpay_client_secret,
                   payment_reference_channel_id, payment_logs_channel_id
            FROM settings WHERE id = 1
            """
        )
        row = await cursor.fetchone()
    if not row:
        return DEFAULT_MISTICPAY_URL, "", "", "", ""
    return tuple(value or default for value, default in zip(row, (DEFAULT_MISTICPAY_URL, "", "", "", "")))


async def save_start_text(text: str) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute(
            """
            UPDATE settings
            SET start_text = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (text,),
        )
        await database.commit()


async def save_photo(file_id: str | None) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute(
            """
            UPDATE settings
            SET photo_file_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (file_id,),
        )
        await database.commit()


async def save_api_settings(api_base_url: str, api_key: str) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute(
            """
            UPDATE settings
            SET api_base_url = ?, api_key = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (api_base_url, api_key),
        )
        await database.commit()


async def save_misticpay_settings(
    misticpay_url: str,
    client_id: str,
    client_secret: str,
    reference_channel_id: str,
    logs_channel_id: str,
) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute(
            """
            UPDATE settings
            SET misticpay_url = ?,
                misticpay_client_id = ?,
                misticpay_client_secret = ?,
                payment_reference_channel_id = ?,
                payment_logs_channel_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (misticpay_url, client_id, client_secret, reference_channel_id, logs_channel_id),
        )
        await database.commit()


async def get_force_join_settings() -> tuple[str, bool]:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            "SELECT payment_reference_channel_id, force_join_enabled FROM settings WHERE id = 1"
        )
        row = await cursor.fetchone()
    if not row:
        return "", False
    return row[0] or "", bool(row[1])


async def set_force_join_enabled(enabled: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute(
            "UPDATE settings SET force_join_enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
            (int(enabled),),
        )
        await database.commit()


async def get_buttons() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute("SELECT button_config FROM settings WHERE id = 1")
        row = await cursor.fetchone()
    try:
        buttons = json.loads(row[0]) if row and row[0] else DEFAULT_BUTTONS
        if isinstance(buttons, list):
            for button in buttons:
                if button.get("text", "").strip().lower() == "bases":
                    button.setdefault("action", "bases")
            if not any(button.get("action") == "plans" for button in buttons):
                buttons.append({"text": "Planos", "url": "", "emoji_id": "", "style": "success", "row": 99, "action": "plans"})
            return buttons
        return DEFAULT_BUTTONS
    except (json.JSONDecodeError, TypeError):
        return DEFAULT_BUTTONS


async def save_buttons(buttons: list[dict]) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute(
            "UPDATE settings SET button_config = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
            (json.dumps(buttons, ensure_ascii=False),),
        )
        await database.commit()


async def get_bases() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute("SELECT base_config FROM settings WHERE id = 1")
        row = await cursor.fetchone()
    try:
        bases = json.loads(row[0]) if row and row[0] else None
        if isinstance(bases, list):
            normalized = []
            for base in bases:
                if isinstance(base, dict) and "name" in base:
                    default_base = next((item for item in DEFAULT_BASES if item["name"] == base["name"]), {})
                    normalized.append(
                        {
                            "name": base["name"],
                            "online": bool(base.get("online")),
                            "url": base.get("url") or default_base.get("url", ""),
                        }
                    )
                elif isinstance(base, list) and len(base) == 2:
                    default_base = next((item for item in DEFAULT_BASES if item["name"] == base[0]), {})
                    normalized.append(
                        {
                            "name": base[0],
                            "online": bool(base[1]),
                            "url": default_base.get("url", ""),
                        }
                    )
            if normalized:
                return normalized
    except (json.JSONDecodeError, TypeError):
        pass
    return DEFAULT_BASES


async def save_bases(bases: list[dict]) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute(
            "UPDATE settings SET base_config = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
            (json.dumps(bases, ensure_ascii=False),),
        )
        await database.commit()


# -----------------------------------------------------------------------------
# Conteúdo e validação
# -----------------------------------------------------------------------------

VARIABLE_PATTERN = re.compile(
    r"\{(first_name|last_name|username|user_id)\}"
)


def render_variables(template: str, user) -> str:
    values = {
        "first_name": html.escape(user.first_name or "amigo"),
        "last_name": html.escape(user.last_name or ""),
        "username": html.escape(
            f"@{user.username}" if user.username else "sem username"
        ),
        "user_id": str(user.id),
    }
    return VARIABLE_PATTERN.sub(
        lambda match: values[match.group(1)],
        template,
    )


def visible_length(text: str) -> int:
    return len(re.sub(r"<[^>]*>", "", text))


def validate_start_text(text: str, has_photo: bool) -> str | None:
    if not text.strip():
        return "O texto não pode ficar vazio."

    limit = 1024 if has_photo else 4096
    if visible_length(text) > limit:
        return f"O limite é de {limit} caracteres."

    if "<tg-emoji" in text.lower():
        valid_emojis = re.findall(
            r'<tg-emoji\s+emoji-id="\d+">.+?</tg-emoji>',
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not valid_emojis:
            return (
                "Emoji premium inválido. Use: "
                '<tg-emoji emoji-id="ID_NUMERICO">🙂</tg-emoji>'
            )

    return None


def normalize_command_name(command: str) -> str:
    return command.strip().lower().lstrip("/")


def extract_command_name_from_base(base: dict) -> str | None:
    url = (base.get("url") or "").strip()
    name_text = (base.get("name") or "").strip().lower()

    if not url:
        url = ""

    parsed = urllib.parse.urlparse(url) if url else None
    segments = [segment.lower() for segment in parsed.path.split("/") if segment] if parsed else []

    command = ""
    version = ""
    if len(segments) >= 2:
        command = segments[-2]
        version = segments[-1]
    else:
        match = re.search(r"\b(cpf|nome|placa|telefone|email|cep|cnpj|motor|chassi|score|inss|cpfsus|fotonaci|fotope)\b", name_text)
        if match:
            command = match.group(1)
        version_match = re.search(r"\bv(\d+)\b", name_text)
        if version_match:
            version = f"v{version_match.group(1)}"

    if command == "fotonaci":
        command = "foto"

    if command == "cpf" and version == "v1":
        return "cpf"
    if command == "cpf" and version == "v2":
        return "cpf1"
    if command == "cpf" and version == "v3":
        return "cpf2"
    if command == "cpf" and version == "v4":
        return "cpf3"
    if command == "cpf" and version == "v5":
        return "cpf5"
    if command == "nome" and version == "v1":
        return "nome"
    if command == "nome" and version == "v2":
        return "nome2"
    if command == "placa" and version == "v1":
        return "placa"
    if command == "placa" and version == "v2":
        return "placa2"
    if command == "placa" and version == "v3":
        return "placa3"
    if command == "telefone" and version == "v1":
        return "telefone"
    if command == "telefone" and version == "v2":
        return "telefone2"
    if command == "foto":
        return "fotope" if "pe" in name_text else "foto"
    if command == "email":
        return "email"
    if command == "cep":
        return "cep"
    if command == "cnpj" and "fgts" in name_text:
        return "cnpjfgts"
    if command == "cnpj":
        return "cnpj"
    if command == "motor":
        return "motor"
    if command == "chassi":
        return "chassi"
    if command == "score":
        return "score"
    if command == "cpfsus":
        return "cpfsus"
    if command == "inss":
        return "inss"
    if command and version.startswith("v"):
        return f"{command}{version[1:]}"
    return command or None


def format_base_usage(base: dict) -> str:
    command_name = extract_command_name_from_base(base)
    if not command_name:
        return "° <b>Comando:</b> <code>/comando VALOR</code>"

    spec = API_COMMAND_LOOKUP.get(command_name)
    if not spec:
        return f"° <b>Comando:</b> <code>/{html.escape(command_name)} VALOR</code>"

    return (
        f"° <b>Comando:</b> <code>/{html.escape(command_name)} {html.escape(spec['example'])}</code>"
    )


def build_api_command_url(api_base_url: str, api_key: str, spec: dict, value: str) -> str:
    base = api_base_url.rstrip("/") + "/"
    query = urllib.parse.urlencode({"apikey": api_key, spec["param"]: value})
    return f"{base}{spec['path'].lstrip('/')}?{query}"


def sanitize_api_result(data: object) -> object:
    if isinstance(data, dict):
        sanitized: dict[str, object] = {}
        for key, value in data.items():
            if key.lower() in HIDDEN_RESPONSE_FIELDS:
                continue
            sanitized[key] = sanitize_api_result(value)
        return sanitized
    if isinstance(data, list):
        return [sanitize_api_result(item) for item in data]
    return data


def parse_api_error_body(body: str) -> object:
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def format_field_label(name: str) -> str:
    normalized = name.replace("_", " ").strip()
    special_labels = {
        "cpf": "CPF",
        "rg": "RG",
        "uf": "UF",
        "cns": "CNS",
        "cep": "CEP",
        "cnpj": "CNPJ",
        "rais": "RAIS",
    }
    words = []
    for word in normalized.split():
        words.append(special_labels.get(word.lower(), word.capitalize()))
    return " ".join(words)


def format_scalar_value(value: object) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "Sim" if value else "Nao"
    return str(value)


def build_user_mention(user) -> str:
    display_name = html.escape(user.first_name or "usuario")
    return f'<a href="tg://user?id={user.id}">{display_name}</a>'


def build_formatted_lines(data: object, indent: int = 0) -> list[str]:
    prefix = "    " * indent
    lines: list[str] = []

    if isinstance(data, dict):
        for key, value in data.items():
            label = format_field_label(key)
            if isinstance(value, dict):
                lines.append(f"{prefix}° <b>{html.escape(label)}:</b>")
                nested_lines = build_formatted_lines(value, indent + 1)
                lines.extend(nested_lines or [f"{prefix}    ° <code>N/A</code>"])
                lines.append("")
            elif isinstance(value, list):
                if not value:
                    lines.append(f"{prefix}° <b>{html.escape(label)}:</b> <code>[]</code>")
                    lines.append("")
                    continue
                lines.append(f"{prefix}° <b>{html.escape(label)}:</b>")
                for index, item in enumerate(value, start=1):
                    if isinstance(item, (dict, list)):
                        lines.append(f"{prefix}    ° <b>Item {index}</b>")
                        lines.extend(build_formatted_lines(item, indent + 2))
                    else:
                        lines.append(
                            f"{prefix}    ° <code>{html.escape(format_scalar_value(item))}</code>"
                        )
                lines.append("")
            else:
                lines.append(
                    f"{prefix}° <b>{html.escape(label)}:</b> "
                    f"<code>{html.escape(format_scalar_value(value))}</code>"
                )
        return lines

    if isinstance(data, list):
        if not data:
            return [f"{prefix}° <code>[]</code>"]
        for index, item in enumerate(data, start=1):
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}° <b>Item {index}</b>")
                lines.extend(build_formatted_lines(item, indent + 1))
            else:
                lines.append(f"{prefix}° <code>{html.escape(format_scalar_value(item))}</code>")
        return lines

    return [f"{prefix}° <code>{html.escape(format_scalar_value(data))}</code>"]


def render_api_result(title: str, data: object, user, bot_username: str) -> str:
    sanitized = sanitize_api_result(data)
    raw_lines = build_formatted_lines(sanitized)
    lines: list[str] = []
    previous_blank = False
    for line in raw_lines:
        if line == "":
            if lines and not previous_blank:
                lines.append("")
            previous_blank = True
            continue
        lines.append(line)
        previous_blank = False
    body = "\n".join(lines) if lines else "<code>Nenhum dado retornado.</code>"
    footer = (
        f"\n\n<b>Consulta enviada para:</b> {build_user_mention(user)}\n"
        f"<b>Creditos:</b> @{html.escape(bot_username or 'bot')}"
    )
    return f"<b>{html.escape(title)}</b>\n\n{body}{footer}"


def render_not_found_result(title: str, data: object, user, bot_username: str) -> str:
    sanitized = sanitize_api_result(data)
    detail = "Nenhum dado foi encontrado para os parametros informados."
    if isinstance(sanitized, dict):
        resposta = sanitized.get("resposta")
        status = sanitized.get("status")
        if isinstance(resposta, str) and resposta.strip():
            detail = resposta.strip()
        elif isinstance(status, str) and status.strip():
            detail = status.strip()

    footer = (
        f"\n\n<b>Consulta enviada para:</b> {build_user_mention(user)}\n"
        f"<b>Creditos:</b> @{html.escape(bot_username or 'bot')}"
    )


def html_to_plain_text(text: str) -> str:
    text = re.sub(r'<a\s+href="[^"]*">(.*?)</a>', r"\1", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def query_result_filename(value: str) -> str:
    safe_value = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_-")
    return f"{safe_value[:80] or 'resultado'}.txt"


async def create_result_delivery(user_id: int, result_text: str) -> str:
    token = uuid.uuid4().hex
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    plain_text = html_to_plain_text(result_text)
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute("DELETE FROM result_deliveries WHERE expires_at <= CURRENT_TIMESTAMP")
        await database.execute(
            "INSERT INTO result_deliveries (token, user_id, result_text, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, plain_text, expires_at),
        )
        await database.commit()

    if RESULTS_API_SECRET and WEB_RESULTS_URL:
        asyncio.create_task(push_result_to_web(token, user_id, plain_text, expires_at))
    return token


async def push_result_to_web(token: str, user_id: int, result_text: str, expires_at: str) -> None:
    payload = json.dumps({
        "token": token,
        "user_id": user_id,
        "result_text": result_text,
        "expires_at": expires_at,
    }).encode("utf-8")

    def _push() -> None:
        request = urllib.request.Request(
            f"{WEB_RESULTS_URL}/api/results",
            data=payload,
            headers={"Content-Type": "application/json", "X-Results-Secret": RESULTS_API_SECRET},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15):
            pass

    try:
        await asyncio.to_thread(_push)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        logger.exception("Falha ao enviar resultado temporário para o Mini App")


async def get_private_result_delivery(token: str, user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            """
            SELECT result_text FROM result_deliveries
            WHERE token = ? AND user_id = ? AND expires_at > CURRENT_TIMESTAMP
            """,
            (token, user_id),
        )
        row = await cursor.fetchone()
        if row:
            await database.execute("DELETE FROM result_deliveries WHERE token = ?", (token,))
            await database.commit()
    return row[0] if row else None


async def send_query_result(
    status_message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup,
    filename: str,
    user,
    bot_username: str,
    delivery_only: bool = False,
) -> Message:
    if delivery_only:
        await status_message.edit_text(
            "<b>✅ Consulta concluída</b>\n\n"
            "Use um dos botões abaixo para ver seu resultado com privacidade.",
            reply_markup=reply_markup,
        )
        return status_message
    plain_text = html_to_plain_text(text)
    if len(plain_text) <= 3900:
        await status_message.edit_text(text, reply_markup=reply_markup)
        return status_message

    try:
        await status_message.delete()
    except TelegramBadRequest:
        pass
    return await status_message.bot.send_document(
        chat_id=status_message.chat.id,
        document=BufferedInputFile(plain_text.encode("utf-8"), filename=filename),
        caption=(
            "📄 O resultado excedeu o limite de mensagens e foi enviado em arquivo.\n\n"
            f"<b>Consulta enviada para:</b> {build_user_mention(user)}\n"
            f"<b>Creditos:</b> @{html.escape(bot_username or 'bot')}"
        ),
        reply_markup=reply_markup,
    )
    return (
        f"<b>{html.escape(title)}</b>\n\n"
        f"° <b>Resultado:</b> <code>Nao encontrado</code>\n"
        f"° <b>Mensagem:</b> <code>{html.escape(detail)}</code>"
        f"{footer}"
    )


def render_payment_create_result(data: object, user, bot_username: str) -> str:
    payload = data if isinstance(data, dict) else {}
    info = payload.get("data") if isinstance(payload, dict) else {}
    payer = info.get("payer") if isinstance(info, dict) else {}
    lines = [
        "<b>💳 Pagamento PIX</b>",
        "",
        "° <b>Resultado:</b> <code>Transacao criada</code>",
        f"° <b>Mensagem:</b> <code>{html.escape(str(payload.get('message', 'Transacao criada com sucesso')))}</code>",
    ]
    if isinstance(info, dict):
        transaction_id = info.get("transactionId")
        amount = info.get("transactionAmount")
        state = info.get("transactionState")
        copy_paste = info.get("copyPaste")
        if transaction_id is not None:
            lines.append(f"° <b>Transaction Id:</b> <code>{html.escape(str(transaction_id))}</code>")
        if amount is not None:
            lines.append(f"° <b>Valor:</b> <code>{html.escape(str(amount))}</code>")
        if state is not None:
            lines.append(f"° <b>Status:</b> <code>{html.escape(str(state))}</code>")
        if isinstance(payer, dict):
            if payer.get("name") is not None:
                lines.append(f"° <b>Pagador:</b> <code>{html.escape(str(payer.get('name')))}</code>")
            if payer.get("document") is not None:
                lines.append(f"° <b>Documento:</b> <code>{html.escape(str(payer.get('document')))}</code>")
        if copy_paste:
            lines.append(f"° <b>Copy/Paste:</b> <code>{html.escape(str(copy_paste))}</code>")
    lines.extend([
        "",
        "° <b>Validação:</b> <code>Automática</code>",
        "",
        f"<b>Consulta enviada para:</b> {build_user_mention(user)}",
        f"<b>Creditos:</b> @{html.escape(bot_username or 'bot')}",
    ])
    return "\n".join(lines)


def extract_qrcode_image(data: object) -> bytes | None:
    if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
        return None
    encoded = data["data"].get("qrCodeBase64")
    if not isinstance(encoded, str) or not encoded.strip():
        return None
    try:
        content = encoded.split(",", 1)[1] if "," in encoded else encoded
        return base64.b64decode(content, validate=True)
    except (ValueError, base64.binascii.Error):
        logger.warning("A MisticPay retornou um QR Code Base64 inválido")
        return None


async def send_pix_result(
    status_message: Message,
    data: object,
    user,
    bot_username: str,
    reply_markup: InlineKeyboardMarkup,
) -> Message:
    caption = render_payment_create_result(data, user, bot_username)
    qr_code = extract_qrcode_image(data)
    if not qr_code:
        await status_message.edit_text(caption, reply_markup=reply_markup)
        return status_message
    await status_message.delete()
    return await status_message.bot.send_photo(
        chat_id=status_message.chat.id,
        photo=BufferedInputFile(qr_code, filename="pix-qrcode.png"),
        caption=caption[:1024],
        reply_markup=reply_markup,
    )


def parse_chat_id(text: str) -> str:
    value = text.strip()
    if value.startswith("@"):
        return value
    return value


def is_valid_cpf(value: str) -> bool:
    return bool(re.fullmatch(r"\d{11}", value.strip()))


def parse_pix_create_command(text: str) -> tuple[float, str, str, str]:
    parts = text.split()
    if len(parts) < 3:
        raise ValueError("Use assim: /pix <valor> <nome> [cpf] [descricao]")

    amount = float(parts[1].replace(",", "."))
    payer_name = parts[2].strip()
    payer_document = DEFAULT_PAYMENT_CPF
    description_parts: list[str] = []

    if len(parts) >= 4:
        third = parts[3].strip()
        if is_valid_cpf(third):
            payer_document = third
            description_parts = parts[4:]
        else:
            description_parts = parts[3:]

    description = " ".join(description_parts).strip() or "Pagamento via Telegram"
    return amount, payer_name, payer_document, description


def build_misticpay_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


async def request_misticpay_json(
    base_url: str,
    client_id: str,
    client_secret: str,
    path: str,
    payload: dict,
) -> object:
    url = build_misticpay_url(base_url, path)

    def _request() -> object:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "ci": client_id,
                "cs": client_secret,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return body

    return await asyncio.to_thread(_request)


def format_misticpay_result(title: str, data: object, user, bot_username: str) -> str:
    sanitized = sanitize_api_result(data)
    body = render_api_result(title, sanitized, user, bot_username)
    return body


async def save_transaction_record(
    transaction_id: str,
    user_id: int,
    amount: float,
    payer_name: str,
    payer_document: str,
    description: str,
    status: str,
    raw_response: object,
    plan_id: int | None = None,
    plan_target_type: str | None = None,
    plan_target_id: int | None = None,
) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute(
            """
            INSERT INTO transactions (
                transaction_id, user_id, amount, payer_name, payer_document,
                description, status, raw_response, plan_id, plan_target_type, plan_target_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(transaction_id) DO UPDATE SET
                user_id = excluded.user_id,
                amount = excluded.amount,
                payer_name = excluded.payer_name,
                payer_document = excluded.payer_document,
                description = excluded.description,
                status = excluded.status,
                raw_response = excluded.raw_response,
                plan_id = COALESCE(excluded.plan_id, transactions.plan_id),
                plan_target_type = COALESCE(excluded.plan_target_type, transactions.plan_target_type),
                plan_target_id = COALESCE(excluded.plan_target_id, transactions.plan_target_id),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                transaction_id,
                user_id,
                amount,
                payer_name,
                payer_document,
                description,
                status,
                json.dumps(raw_response, ensure_ascii=False) if not isinstance(raw_response, str) else raw_response,
                plan_id,
                plan_target_type,
                plan_target_id,
            ),
        )
        await database.commit()


async def get_plans(active_only: bool = False) -> list[tuple[int, str, str, int, float, int]]:
    query = "SELECT id, name, category, duration_days, price, active FROM plans WHERE name NOT LIKE '[Sistema]%'"
    if active_only:
        query += " AND active = 1"
    query += " ORDER BY price ASC, id ASC"
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(query)
        return await cursor.fetchall()


async def get_plan(plan_id: int) -> tuple[int, str, str, int, float, int] | None:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            "SELECT id, name, category, duration_days, price, active FROM plans WHERE id = ?",
            (plan_id,),
        )
        return await cursor.fetchone()


async def create_plan(name: str, category: str, duration_days: int, price: float) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute(
            "INSERT INTO plans (name, category, duration_days, price) VALUES (?, ?, ?, ?)",
            (name, category, duration_days, price),
        )
        await database.commit()


async def set_plan_active(plan_id: int, active: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute("UPDATE plans SET active = ? WHERE id = ?", (int(active), plan_id))
        await database.commit()


async def delete_plan(plan_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute("DELETE FROM subscriptions WHERE plan_id = ?", (plan_id,))
        await database.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
        await database.commit()


async def grant_subscription(plan_id: int, target_type: str, target_id: int, duration_days: int) -> str:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            "SELECT expires_at FROM subscriptions WHERE plan_id = ? AND target_type = ? AND target_id = ?",
            (plan_id, target_type, target_id),
        )
        row = await cursor.fetchone()
        now = datetime.utcnow()
        previous = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") if row else now
        base = previous if previous > now else now
        expires_at = (base + timedelta(days=duration_days)).strftime("%Y-%m-%d %H:%M:%S")
        await database.execute(
            """
            INSERT INTO subscriptions (plan_id, target_type, target_id, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(plan_id, target_type, target_id) DO UPDATE SET expires_at = excluded.expires_at
            """,
            (plan_id, target_type, target_id, expires_at),
        )
        await database.commit()
    return expires_at


async def get_active_subscriptions() -> list[tuple[int, str, str, int, str]]:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            """
            SELECT subscriptions.id, plans.name, subscriptions.target_type,
                   subscriptions.target_id, subscriptions.expires_at
            FROM subscriptions
            JOIN plans ON plans.id = subscriptions.plan_id
            WHERE subscriptions.expires_at > CURRENT_TIMESTAMP
            ORDER BY subscriptions.expires_at ASC
            LIMIT 40
            """
        )
        return await cursor.fetchall()


async def get_subscription(subscription_id: int) -> tuple[int, str, str, int, str] | None:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            """
            SELECT subscriptions.id, plans.name, subscriptions.target_type,
                   subscriptions.target_id, subscriptions.expires_at
            FROM subscriptions
            JOIN plans ON plans.id = subscriptions.plan_id
            WHERE subscriptions.id = ?
            """,
            (subscription_id,),
        )
        return await cursor.fetchone()


async def cancel_subscription(subscription_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute("DELETE FROM subscriptions WHERE id = ?", (subscription_id,))
        await database.commit()


async def has_active_access(chat_id: int, user_id: int, private_chat: bool) -> bool:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            """
            SELECT 1 FROM subscriptions
            WHERE expires_at > CURRENT_TIMESTAMP
              AND ((target_type = 'user' AND target_id = ? AND ?) OR (target_type = 'group' AND target_id = ?))
            LIMIT 1
            """,
            (user_id, int(private_chat), chat_id),
        )
        return await cursor.fetchone() is not None


async def notify_payment_channels(bot: Bot, text: str) -> None:
    _, _, _, ref_channel, logs_channel = await get_misticpay_settings()
    for channel in (ref_channel, logs_channel):
        channel = (channel or "").strip()
        if not channel:
            continue
        try:
            await bot.send_message(channel, text, parse_mode=ParseMode.HTML)
        except Exception:
            logger.exception("Falha ao enviar notificação para canal %s", channel)


async def send_payment_notifications(bot: Bot, reference_text: str | None, log_text: str | None) -> None:
    _, _, _, ref_channel, logs_channel = await get_misticpay_settings()
    if reference_text and (ref_channel or "").strip():
        try:
            await bot.send_message(ref_channel, reference_text, parse_mode=ParseMode.HTML)
        except Exception:
            logger.exception("Falha ao enviar para canal de referência %s", ref_channel)
    if log_text and (logs_channel or "").strip():
        try:
            await bot.send_message(logs_channel, log_text, parse_mode=ParseMode.HTML)
        except Exception:
            logger.exception("Falha ao enviar para canal de logs %s", logs_channel)


async def get_pending_transactions() -> list[tuple[str, int, float, str, str, str, str, int | None, str | None, int | None]]:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            """
            SELECT transaction_id, user_id, amount, payer_name, payer_document, description, status,
                   plan_id, plan_target_type, plan_target_id
            FROM transactions
            WHERE UPPER(status) = 'PENDENTE'
            ORDER BY updated_at ASC
            LIMIT 15
            """
        )
        return await cursor.fetchall()


async def monitor_pending_payments(bot: Bot) -> None:
    """Confirma automaticamente os PIX pendentes sem expor comando ao usuario."""
    while True:
        try:
            misticpay_url, client_id, client_secret, _, _ = await get_misticpay_settings()
            if client_id and client_secret:
                for transaction in await get_pending_transactions():
                    (
                        transaction_id, user_id, amount, payer_name, payer_document, description, old_status,
                        plan_id, plan_target_type, plan_target_id,
                    ) = transaction
                    try:
                        data = await request_misticpay_json(
                            misticpay_url,
                            client_id,
                            client_secret,
                            MISTICPAY_CHECK_PATH,
                            {"transactionId": transaction_id},
                        )
                    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
                        logger.exception("Falha ao validar PIX automaticamente: %s", transaction_id)
                        continue

                    payment = data.get("transaction") if isinstance(data, dict) else {}
                    new_status = str(payment.get("transactionState") or old_status).upper()
                    await save_transaction_record(
                        transaction_id=transaction_id,
                        user_id=user_id,
                        amount=float(payment.get("value") or amount) if isinstance(payment, dict) else amount,
                        payer_name=payer_name,
                        payer_document=payer_document,
                        description=description,
                        status=new_status,
                        raw_response=data,
                        plan_id=plan_id,
                        plan_target_type=plan_target_type,
                        plan_target_id=plan_target_id,
                    )

                    if new_status not in {"COMPLETO", "FALHA"}:
                        continue

                    status_label = "Pagamento aprovado" if new_status == "COMPLETO" else "Pagamento recusado"
                    expiration = None
                    if new_status == "COMPLETO" and plan_id and plan_target_type and plan_target_id:
                        plan = await get_plan(plan_id)
                        if plan:
                            expiration = await grant_subscription(
                                plan_id,
                                plan_target_type,
                                plan_target_id,
                                plan[3],
                            )
                    reference_notification = (
                        "<b>💳 MisticPay - Atualização automática</b>\n\n"
                        f"° <b>Transaction Id:</b> <code>{html.escape(transaction_id)}</code>\n"
                        f"° <b>Valor:</b> <code>{html.escape(str(amount))}</code>\n"
                        f"° <b>Status:</b> <code>{html.escape(status_label)}</code>"
                    )
                    if expiration:
                        reference_notification += f"\n° <b>Válido até:</b> <code>{html.escape(expiration)}</code>"
                    log_notification = (
                        f"{reference_notification}\n"
                        f"° <b>Usuário:</b> <code>{user_id}</code>\n"
                        f"° <b>CPF:</b> <code>{html.escape(payer_document)}</code>"
                    )
                    await send_payment_notifications(bot, reference_notification, log_notification)
                    try:
                        await bot.send_message(
                            user_id,
                            f"<b>💳 Atualização do pagamento</b>\n\n"
                            f"° <b>Transaction Id:</b> <code>{html.escape(transaction_id)}</code>\n"
                            f"° <b>Status:</b> <code>{html.escape(status_label)}</code>",
                        )
                    except TelegramBadRequest:
                        logger.info("Não foi possível avisar o usuário %s sobre o PIX %s", user_id, transaction_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Falha no monitor automático da MisticPay")

        await asyncio.sleep(30)


def build_chassi_url(api_base_url: str, api_key: str, chassi: str) -> str:
    base = api_base_url.rstrip("/") + "/"
    query = urllib.parse.urlencode({"apikey": api_key, "chassi": chassi})
    return f"{base}api/consulta/chassi/v1?{query}"


async def fetch_api_data(api_base_url: str, api_key: str, spec: dict, value: str) -> object:
    url = build_api_command_url(api_base_url, api_key, spec, value)
    logger.info(
        "Enviando consulta | comando=/%s | parametro=%s | valor=%r | url=%s",
        spec["aliases"][0],
        spec["param"],
        value,
        url,
    )

    def _request() -> object:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return body

    return await asyncio.to_thread(_request)


async def fetch_chassi_data(api_base_url: str, api_key: str, chassi: str) -> object:
    url = build_chassi_url(api_base_url, api_key, chassi)

    def _request() -> object:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return body

    return await asyncio.to_thread(_request)


# -----------------------------------------------------------------------------
# Botões e estados do painel
# -----------------------------------------------------------------------------

def main_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎨 Personalizar Start",
                    callback_data="admin:start_menu",
                )
            ],
            [InlineKeyboardButton(text="🗂 Gerenciar Bases", callback_data="admin:bases")],
            [InlineKeyboardButton(text="🔑 Configurar API", callback_data="admin:api")],
            [InlineKeyboardButton(text="💳 MisticPay", callback_data="admin:misticpay")],
            [InlineKeyboardButton(text="📦 Planos e acessos", callback_data="admin:plans")],
        ]
    )


def start_keyboard(has_photo: bool) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✏️ Editar texto", callback_data="admin:text")],
        [InlineKeyboardButton(text="🖼 Definir imagem", callback_data="admin:photo")],
        [InlineKeyboardButton(text="🔘 Editar botões", callback_data="admin:buttons")],
    ]

    if has_photo:
        buttons.append(
            [InlineKeyboardButton(text="🗑 Remover imagem", callback_data="admin:remove")]
        )

    buttons.extend(
        [
            [InlineKeyboardButton(text="👁 Testar /start", callback_data="admin:preview")],
            [InlineKeyboardButton(text="❓ Ajuda HTML", callback_data="admin:help")],
            [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:back")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancelar", callback_data="admin:cancel")]
        ]
    )


def result_keyboard(user_id: int, command_message_id: int, token: str | None = None, bot_username: str = "") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if token:
        delivery_buttons = []
        if WEB_RESULTS_URL and RESULTS_API_SECRET:
            delivery_buttons.append(InlineKeyboardButton(
                text="🌐 Ver resultado web",
                url=f"{WEB_RESULTS_URL}/r/{token}",
            ))
        if bot_username:
            delivery_buttons.append(InlineKeyboardButton(
                text="📩 Ver no privado",
                url=f"https://t.me/{bot_username}?start=result_{token}",
            ))
        if delivery_buttons:
            rows.append(delivery_buttons)
    rows.append([
        InlineKeyboardButton(
            text="🗑 Deletar",
            callback_data=f"result:delete:{user_id}:{command_message_id}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def api_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Alterar base", callback_data="admin:api_base")],
            [InlineKeyboardButton(text="🔐 Alterar key", callback_data="admin:api_key")],
            [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:back")],
        ]
    )


def misticpay_admin_keyboard(force_join_enabled: bool = False) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Alterar URL", callback_data="admin:mp_url")],
            [InlineKeyboardButton(text="🆔 Alterar Client ID", callback_data="admin:mp_client_id")],
            [InlineKeyboardButton(text="🧾 Alterar Client Secret", callback_data="admin:mp_client_secret")],
            [InlineKeyboardButton(text="📣 Canal de referência", callback_data="admin:mp_ref_channel")],
            [InlineKeyboardButton(
                text=f"{'🟢' if force_join_enabled else '🔴'} Obrigatoriedade de canal",
                callback_data="admin:force_join_toggle",
            )],
            [InlineKeyboardButton(text="📜 Canal de logs", callback_data="admin:mp_logs_channel")],
            [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:back")],
        ]
    )


def plans_admin_keyboard(plans: list[tuple[int, str, str, int, float, int]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{'🟢' if plan[5] else '🔴'} {plan[1]} | {'Plano' if plan[2] == 'user' else 'Grupo'}",
            callback_data=f"admin:plan:{plan[0]}",
        )]
        for plan in plans
    ]
    rows.extend([
        [InlineKeyboardButton(text="➕ Criar plano", callback_data="admin:plan_create")],
        [InlineKeyboardButton(text="🎯 Liberar acesso", callback_data="admin:plan_grant")],
        [InlineKeyboardButton(text="👥 Gerenciar acessos ativos", callback_data="admin:subscriptions")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:back")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plan_editor_keyboard(plan: tuple[int, str, str, int, float, int]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔴 Desativar" if plan[5] else "🟢 Ativar",
            callback_data=f"admin:plan_toggle:{plan[0]}",
        )],
        [InlineKeyboardButton(text="🗑 Excluir", callback_data=f"admin:plan_delete:{plan[0]}")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:plans")],
    ])


def public_plans_keyboard(plans: list[tuple[int, str, str, int, float, int]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"💳 {plan[1]} | R$ {plan[4]:.2f}",
            callback_data=f"plan:buy:{plan[0]}",
        )]
        for plan in plans if plan[2] == "user"
    ]
    rows.append([InlineKeyboardButton(text="✖️ Fechar", callback_data="plans:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscriptions_admin_keyboard(subscriptions: list[tuple[int, str, str, int, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{'👤' if subscription[2] == 'user' else '👥'} {subscription[3]} | vence {subscription[4][:10]}",
            callback_data=f"admin:subscription:{subscription[0]}",
        )]
        for subscription in subscriptions
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:plans")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_editor_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Cancelar acesso", callback_data=f"admin:subscription_cancel:{subscription_id}")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:subscriptions")],
    ])


def format_button_text(text: str) -> str:
    """Simula negrito + itálico, pois botões do Telegram não aceitam HTML."""
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    styled = (
        "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁"
        "𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛"
    )
    digits = "0123456789"
    bold_digits = "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    return text.translate(str.maketrans(normal + digits, styled + bold_digits))


class AdminState(StatesGroup):
    waiting_text = State()
    waiting_photo = State()
    waiting_button_text = State()
    waiting_button_url = State()
    waiting_button_emoji = State()
    waiting_api_base = State()
    waiting_api_key = State()
    waiting_misticpay_url = State()
    waiting_misticpay_client_id = State()
    waiting_misticpay_client_secret = State()
    waiting_reference_channel = State()
    waiting_logs_channel = State()
    waiting_plan_create = State()
    waiting_plan_grant = State()


def public_buttons_keyboard(buttons: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for row_number in sorted({int(button.get("row", 0)) for button in buttons}):
        row = []
        for index, button in enumerate(buttons):
            if int(button.get("row", 0)) != row_number:
                continue
            data = {
                "text": format_button_text(button.get("text", "Botão")),
                "url": button.get("url") or None,
                "callback_data": (
                    None if button.get("url") else
                    "start:bases" if button.get("action") == "bases" else
                    "start:plans" if button.get("action") == "plans" else f"start:button:{index}"
                ),
            }
            if button.get("emoji_id"):
                data["icon_custom_emoji_id"] = button["emoji_id"]
            if button.get("style"):
                data["style"] = button["style"]
            row.append(InlineKeyboardButton(**data))
        if row:
            rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def buttons_admin_keyboard(buttons: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{i + 1}. {button.get('text', 'Botão')}", callback_data=f"admin:button:{i}")]
        for i, button in enumerate(buttons)
    ]
    rows.extend([
        [InlineKeyboardButton(text="▦ Alterar organização", callback_data="admin:layout")],
        [InlineKeyboardButton(text="👁 Testar /start", callback_data="admin:preview")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:start_menu")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def button_editor_keyboard(index: int, button: dict) -> InlineKeyboardMarkup:
    colors = {"primary": "azul", "success": "verde", "danger": "vermelho", "": "padrão"}
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Alterar texto", callback_data=f"admin:btext:{index}")],
        [InlineKeyboardButton(text="🔗 Alterar link", callback_data=f"admin:burl:{index}")],
        [InlineKeyboardButton(text="✨ Emoji premium", callback_data=f"admin:bemoji:{index}")],
        [InlineKeyboardButton(text=f"🎨 Cor: {colors.get(button.get('style', ''), 'padrão')}", callback_data=f"admin:bstyle:{index}")],
        [InlineKeyboardButton(text="⬆️ Mover", callback_data=f"admin:bmove:{index}:-1"), InlineKeyboardButton(text="⬇️ Mover", callback_data=f"admin:bmove:{index}:1")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:buttons")],
    ])


def bases_keyboard(bases: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=f"{base['name']} {'🟢' if base['online'] else '🔴'}",
            callback_data=f"bases:category:{index}",
            style="success" if base["online"] else "danger",
        )
        for index, base in enumerate(bases)
    ]
    rows = [buttons[index:index + 2] for index in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="✖️ Fechar", callback_data="bases:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bases_admin_keyboard(bases: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=f"{base['name']} {'🟢' if base['online'] else '🔴'}",
            callback_data=f"admin:base_toggle:{index}",
            style="success" if base["online"] else "danger",
        )
        for index, base in enumerate(bases)
    ]
    rows = [buttons[index:index + 2] for index in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:base_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# -----------------------------------------------------------------------------
# Handlers do aiogram
# -----------------------------------------------------------------------------

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_private_chat(chat) -> bool:
    return getattr(getattr(chat, "type", None), "value", getattr(chat, "type", None)) == "private"


def required_channel_keyboard(channel: str) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    if channel.startswith("@"):
        buttons.append([InlineKeyboardButton(text="📢 Entrar no canal", url=f"https://t.me/{channel[1:]}")])
    buttons.append([InlineKeyboardButton(text="✅ Verificar inscrição", callback_data="required:check")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def has_required_channel_access(bot: Bot, user_id: int) -> tuple[bool, str]:
    if is_admin(user_id):
        return True, ""
    channel, enabled = await get_force_join_settings()
    if not enabled:
        return True, channel
    if not channel:
        return False, ""
    try:
        member = await bot.get_chat_member(channel, user_id)
        status = getattr(member.status, "value", member.status)
        return status in {"creator", "administrator", "member"}, channel
    except Exception:
        logger.exception("Não foi possível validar entrada no canal obrigatório")
        return False, channel


async def enforce_required_channel(message: Message) -> bool:
    allowed, channel = await has_required_channel_access(message.bot, message.from_user.id)
    if allowed:
        return True
    await message.answer(
        "📢 Para utilizar o bot, entre primeiro no nosso canal de referência e toque em verificar.",
        reply_markup=required_channel_keyboard(channel),
    )
    return False


async def delete_messages_later(bot: Bot, chat_id: int, message_ids: list[int], delay: int = AUTO_DELETE_SECONDS) -> None:
    await asyncio.sleep(delay)
    for message_id in message_ids:
        try:
            await bot.delete_message(chat_id, message_id)
        except TelegramBadRequest:
            pass


def schedule_query_cleanup(message: Message, response_message: Message, delay: int = AUTO_DELETE_SECONDS) -> None:
    asyncio.create_task(delete_messages_later(message.bot, message.chat.id, [message.message_id, response_message.message_id], delay))


async def send_start(bot: Bot, chat_id: int, user) -> None:
    text, photo_file_id = await get_settings()
    buttons = await get_buttons()
    rendered = render_variables(text, user)
    reply_markup = public_buttons_keyboard(buttons)

    if photo_file_id:
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo_file_id,
            caption=rendered,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=rendered,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await register_user(message)
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("result_"):
        result_text = await get_private_result_delivery(parts[1][7:], message.from_user.id)
        if not result_text:
            await message.answer("⏳ Este resultado expirou ou não pertence a você. Faça uma nova consulta.")
            return
        if len(result_text) <= 3900:
            await message.answer(f"<pre>{html.escape(result_text)}</pre>")
        else:
            await message.answer_document(
                BufferedInputFile(result_text.encode("utf-8"), filename="resultado-privado.txt"),
                caption="📄 Seu resultado foi enviado em arquivo.",
            )
        return
    await send_start(message.bot, message.chat.id, message.from_user)


@router.message(Command("chatid"))
async def chat_id_handler(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return await message.answer("Somente administradores podem ver o ID do chat.")
    response = await message.answer(
        "<b>🆔 ID deste chat</b>\n\n"
        f"<code>{message.chat.id}</code>\n\n"
        "Use este ID em <b>Planos e acessos</b> → <b>Liberar acesso</b>."
    )
    schedule_query_cleanup(message, response)


@router.callback_query(F.data.startswith("start:button:"))
async def unconfigured_start_button_handler(query: CallbackQuery) -> None:
    await query.answer("Este botão ainda não tem um link. Configure-o no /admin.", show_alert=True)


@router.callback_query(F.data == "required:check")
async def required_channel_check_handler(query: CallbackQuery) -> None:
    allowed, _ = await has_required_channel_access(query.bot, query.from_user.id)
    if allowed:
        await query.answer("Inscrição confirmada. Agora você já pode usar o bot.", show_alert=True)
    else:
        await query.answer("Ainda não localizei sua inscrição. Entre no canal e tente novamente.", show_alert=True)


@router.callback_query(F.data == "start:bases")
async def bases_handler(query: CallbackQuery) -> None:
    bases = await get_bases()
    await query.message.answer(
        "<b>📚 Bases disponíveis</b>\n\nEscolha uma categoria:",
        reply_markup=bases_keyboard(bases),
    )
    await query.answer()


@router.callback_query(F.data == "start:plans")
async def public_plans_handler(query: CallbackQuery) -> None:
    category = "user" if is_private_chat(query.message.chat) else "group"
    plans = [plan for plan in await get_plans(active_only=True) if plan[2] == category]
    if not plans:
        kind = "privados" if category == "user" else "para grupos"
        return await query.answer(f"Não há planos {kind} disponíveis no momento.", show_alert=True)
    text = ["<b>📦 Planos disponíveis</b>", "", "Escolha um plano para gerar seu PIX:"]
    for _, name, _, duration_days, price, _ in plans:
        text.append(f"° <b>{html.escape(name)}:</b> <code>{duration_days} dias | R$ {price:.2f}</code>")
    await query.message.answer("\n".join(text), reply_markup=public_plans_keyboard(plans))
    await query.answer()


@router.callback_query(F.data == "plans:close")
async def close_plans_handler(query: CallbackQuery) -> None:
    await query.message.delete()
    await query.answer()


@router.callback_query(F.data.startswith("plan:buy:"))
async def buy_plan_handler(query: CallbackQuery) -> None:
    allowed, channel = await has_required_channel_access(query.bot, query.from_user.id)
    if not allowed:
        await query.message.answer(
            "📢 Entre no canal de referência antes de comprar um plano.",
            reply_markup=required_channel_keyboard(channel),
        )
        return await query.answer("Entre no canal obrigatório primeiro.", show_alert=True)
    plan = await get_plan(int(query.data.rsplit(":", 1)[1]))
    target_type = "user" if is_private_chat(query.message.chat) else "group"
    target_id = query.from_user.id if target_type == "user" else query.message.chat.id
    if not plan or not plan[5] or plan[2] != target_type:
        return await query.answer("Este plano não está disponível.", show_alert=True)
    plan_id, plan_name, _, duration_days, price, _ = plan
    misticpay_url, client_id, client_secret, _, _ = await get_misticpay_settings()
    if not client_id or not client_secret:
        return await query.answer("Os pagamentos ainda não foram configurados.", show_alert=True)

    await query.answer("Gerando PIX...")
    status_message = await query.message.answer("⏳ Criando PIX do seu plano...")
    transaction_id = uuid.uuid4().hex[:12]
    payer_name = query.from_user.full_name or query.from_user.first_name or "usuario"
    description = f"Plano {plan_name} - {duration_days} dias"
    try:
        data = await request_misticpay_json(
            misticpay_url,
            client_id,
            client_secret,
            MISTICPAY_CREATE_PATH,
            {
                "amount": price,
                "payerName": payer_name,
                "payerDocument": DEFAULT_PAYMENT_CPF,
                "transactionId": transaction_id,
                "description": description,
            },
        )
    except urllib.error.HTTPError as error:
        detail = await asyncio.to_thread(error.read) if error.fp else b""
        body = detail.decode("utf-8", errors="replace") if detail else error.reason
        await status_message.edit_text(f"❌ Não foi possível criar o PIX:\n<code>{html.escape(str(body))}</code>")
        return
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        await status_message.edit_text(f"❌ Não foi possível criar o PIX:\n<code>{html.escape(str(error))}</code>")
        return

    response = data.get("data") if isinstance(data, dict) else {}
    response_transaction_id = str(response.get("transactionId") or transaction_id) if isinstance(response, dict) else transaction_id
    response_status = str(response.get("transactionState") or "PENDENTE") if isinstance(response, dict) else "PENDENTE"
    await save_transaction_record(
        transaction_id=response_transaction_id,
        user_id=query.from_user.id,
        amount=price,
        payer_name=payer_name,
        payer_document=DEFAULT_PAYMENT_CPF,
        description=description,
        status=response_status,
        raw_response=data,
        plan_id=plan_id,
        plan_target_type=target_type,
        plan_target_id=target_id,
    )
    bot_me = await query.bot.get_me()
    payment_message = await send_pix_result(
        status_message,
        data,
        query.from_user,
        bot_me.username or "",
        result_keyboard(query.from_user.id, query.message.message_id),
    )
    asyncio.create_task(delete_messages_later(query.bot, query.message.chat.id, [payment_message.message_id], 600))
    await send_payment_notifications(
        query.bot,
        (
            "<b>📣 MisticPay - Compra de plano</b>\n\n"
            f"° <b>Plano:</b> <code>{html.escape(plan_name)}</code>\n"
            f"° <b>Transaction Id:</b> <code>{html.escape(response_transaction_id)}</code>\n"
            f"° <b>Valor:</b> <code>R$ {price:.2f}</code>"
        ),
        (
            "<b>📜 MisticPay - Compra de plano</b>\n\n"
            f"° <b>Usuário:</b> {build_user_mention(query.from_user)}\n"
            f"° <b>Plano:</b> <code>{html.escape(plan_name)}</code>\n"
            f"° <b>Transaction Id:</b> <code>{html.escape(response_transaction_id)}</code>\n"
            f"° <b>Status:</b> <code>{html.escape(response_status)}</code>"
        ),
    )


@router.callback_query(F.data.startswith("bases:category:"))
async def bases_category_handler(query: CallbackQuery) -> None:
    index = int(query.data.rsplit(":", 1)[1])
    bases = await get_bases()
    if not 0 <= index < len(bases):
        return await query.answer("Categoria não encontrada.", show_alert=True)
    name, online = bases[index]["name"], bases[index]["online"]
    status = "online" if online else "offline"
    offline_hint = (
        "\n\n⚠️ Essa base está offline. Use outra base."
        if not online
        else ""
    )
    await query.message.answer(
        f"<b>{html.escape(name)}</b>\n\n"
        f"° <b>Status:</b> <code>{status}</code>\n"
        f"{format_base_usage(bases[index])}"
        f"{offline_hint}"
    )
    await query.answer(f"{name}: {status}.", show_alert=True)


@router.callback_query(F.data == "bases:close")
async def close_bases_handler(query: CallbackQuery) -> None:
    await query.message.delete()
    await query.answer()


@router.message(Command("admin"))
async def admin_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    await state.clear()
    _, photo_file_id = await get_settings()
    await message.answer(
        "<b>⚙️ Painel administrativo</b>\n\n"
        "Escolha uma categoria:",
        reply_markup=main_admin_keyboard(),
    )


@router.callback_query(F.data == "admin:bases")
async def admin_bases_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.clear()
    bases = await get_bases()
    await query.message.edit_text(
        "<b>🗂 Gerenciar Bases</b>\n\n"
        "Toque em uma base para alternar o status entre online e offline.",
        reply_markup=bases_admin_keyboard(bases),
    )
    await query.answer()


@router.callback_query(F.data.startswith("admin:base_toggle:"))
async def admin_base_toggle_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    index = int(query.data.rsplit(":", 1)[1])
    bases = await get_bases()
    if not 0 <= index < len(bases):
        return await query.answer("Base não encontrada.", show_alert=True)
    bases[index]["online"] = not bases[index]["online"]
    await save_bases(bases)
    await query.message.edit_reply_markup(reply_markup=bases_admin_keyboard(bases))
    await query.answer("Status atualizado.")


@router.callback_query(F.data == "admin:base_back")
async def admin_base_back_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await query.message.edit_text(
        "<b>⚙️ Painel administrativo</b>\n\nEscolha uma categoria:",
        reply_markup=main_admin_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == "admin:start_menu")
async def start_menu_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.clear()
    _, photo_file_id = await get_settings()
    await query.message.edit_text(
        "<b>🎨 Personalizar Start</b>\n\n"
        "Gerencie tudo relacionado à mensagem inicial:",
        reply_markup=start_keyboard(bool(photo_file_id)),
    )
    await query.answer()


@router.callback_query(F.data == "admin:back")
async def back_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.clear()
    await query.message.edit_text(
        "<b>⚙️ Painel administrativo</b>\n\n"
        "Escolha uma categoria:",
        reply_markup=main_admin_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == "admin:api")
async def api_menu_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.clear()
    api_base_url, api_key = await get_api_settings()
    masked_key = "•" * min(len(api_key), 12) if api_key else "não configurada"
    await query.message.edit_text(
        "<b>🔑 Configurar API</b>\n\n"
        f"Base atual: <code>{html.escape(api_base_url)}</code>\n"
        f"Key atual: <code>{html.escape(masked_key)}</code>\n\n"
        "Aqui o admin pode trocar a base padrão e cadastrar a key da API.",
        reply_markup=api_admin_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == "admin:api_base")
async def api_base_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.set_state(AdminState.waiting_api_base)
    await query.message.answer(
        "Envie a nova base da API.\n\n"
        f"Base padrão atual: <code>{html.escape(DEFAULT_API_BASE_URL)}</code>\n"
        "Exemplo: <code>http://node.tconect.xyz:1116/</code>",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_api_base, F.text)
async def receive_api_base_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    api_base_url = message.text.strip()
    if not re.match(r"^https?://", api_base_url, re.IGNORECASE):
        return await message.answer(
            "❌ A base precisa começar com http:// ou https://.",
            reply_markup=cancel_keyboard(),
        )

    await save_api_settings(api_base_url, (await get_api_settings())[1])
    await state.clear()
    await message.answer("✅ Base da API salva com sucesso.", reply_markup=api_admin_keyboard())


@router.callback_query(F.data == "admin:api_key")
async def api_key_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.set_state(AdminState.waiting_api_key)
    await query.message.answer(
        "Envie a nova key/token da API.\n\n"
        "Se quiser remover, envie <code>remover</code>.",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_api_key, F.text)
async def receive_api_key_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    api_key = message.text.strip()
    if api_key.lower() == "remover":
        api_key = ""

    api_base_url, _ = await get_api_settings()
    await save_api_settings(api_base_url, api_key)
    await state.clear()
    await message.answer("✅ Key/token salvo com sucesso.", reply_markup=api_admin_keyboard())


@router.callback_query(F.data == "admin:plans")
async def admin_plans_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.clear()
    plans = await get_plans()
    await query.message.edit_text(
        "<b>📦 Planos e acessos</b>\n\n"
        "Crie planos para usuários ou grupos. O botão público vende apenas planos de usuário; "
        "planos de grupo são liberados manualmente pelo ID do chat.",
        reply_markup=plans_admin_keyboard(plans),
    )
    await query.answer()


@router.callback_query(F.data == "admin:plan_create")
async def admin_plan_create_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.set_state(AdminState.waiting_plan_create)
    await query.message.answer(
        "Envie os dados do plano neste formato:\n\n"
        "<code>Nome do plano | plano ou privado | dias | valor</code>\n"
        "<code>Nome do grupo | grupo | dias | valor</code>\n\n"
        "Exemplo: <code>Mensal | plano | 30 | 19.90</code>",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_plan_create, F.text)
async def receive_plan_create_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = [part.strip() for part in message.text.split("|")]
    if len(parts) != 4:
        return await message.answer("❌ Use: <code>Nome | plano ou grupo | dias | valor</code>", reply_markup=cancel_keyboard())
    name, category_text, days_text, price_text = parts
    category = "user" if category_text.lower() in {"plano", "privado", "publico", "público", "user", "usuario", "usuário"} else "group" if category_text.lower() in {"grupo", "group"} else ""
    try:
        duration_days = int(days_text)
        price = float(price_text.replace(",", "."))
    except ValueError:
        return await message.answer("❌ Dias e valor precisam ser números válidos.", reply_markup=cancel_keyboard())
    if not name or not category or duration_days <= 0 or price <= 0:
        return await message.answer("❌ Informe nome, tipo válido, dias e valor maiores que zero.", reply_markup=cancel_keyboard())
    await create_plan(name, category, duration_days, price)
    await state.clear()
    await message.answer("✅ Plano criado.", reply_markup=plans_admin_keyboard(await get_plans()))


@router.callback_query(F.data.startswith("admin:plan:"))
async def admin_plan_editor_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    plan = await get_plan(int(query.data.rsplit(":", 1)[1]))
    if not plan:
        return await query.answer("Plano não encontrado.", show_alert=True)
    _, name, category, duration_days, price, active = plan
    await query.message.edit_text(
        f"<b>📦 {html.escape(name)}</b>\n\n"
        f"° <b>Tipo:</b> <code>{'Plano' if category == 'user' else 'Grupo'}</code>\n"
        f"° <b>Duração:</b> <code>{duration_days} dias</code>\n"
        f"° <b>Valor:</b> <code>R$ {price:.2f}</code>\n"
        f"° <b>Status:</b> <code>{'Ativo' if active else 'Inativo'}</code>",
        reply_markup=plan_editor_keyboard(plan),
    )
    await query.answer()


@router.callback_query(F.data.startswith("admin:plan_toggle:"))
async def admin_plan_toggle_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    plan_id = int(query.data.rsplit(":", 1)[1])
    plan = await get_plan(plan_id)
    if not plan:
        return await query.answer("Plano não encontrado.", show_alert=True)
    await set_plan_active(plan_id, not bool(plan[5]))
    await admin_plan_editor_handler(query)


@router.callback_query(F.data.startswith("admin:plan_delete:"))
async def admin_plan_delete_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await delete_plan(int(query.data.rsplit(":", 1)[1]))
    await query.message.edit_text("✅ Plano e acessos vinculados removidos.", reply_markup=plans_admin_keyboard(await get_plans()))
    await query.answer()


@router.callback_query(F.data == "admin:plan_grant")
async def admin_plan_grant_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.set_state(AdminState.waiting_plan_grant)
    await query.message.answer(
        "Envie: <code>ID do usuário/chat | quantidade de dias</code>\n\n"
        "Exemplos:\n"
        "<code>123456789 | 30</code> para usuário no privado\n"
        "<code>-1001234567890 | 15</code> para grupo\n\n"
        "Use <code>/chatid</code> dentro do grupo para descobrir o ID.",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == "admin:subscriptions")
async def admin_subscriptions_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.clear()
    subscriptions = await get_active_subscriptions()
    if not subscriptions:
        await query.message.edit_text(
            "<b>👥 Acessos ativos</b>\n\nNenhum acesso ativo no momento.",
            reply_markup=subscriptions_admin_keyboard([]),
        )
        return await query.answer()
    await query.message.edit_text(
        "<b>👥 Acessos ativos</b>\n\nToque em um acesso para ver detalhes ou cancelar.",
        reply_markup=subscriptions_admin_keyboard(subscriptions),
    )
    await query.answer()


@router.callback_query(F.data.startswith("admin:subscription:"))
async def admin_subscription_editor_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    subscription = await get_subscription(int(query.data.rsplit(":", 1)[1]))
    if not subscription:
        return await query.answer("Acesso não encontrado.", show_alert=True)
    subscription_id, plan_name, target_type, target_id, expires_at = subscription
    await query.message.edit_text(
        "<b>👥 Gerenciar acesso</b>\n\n"
        f"° <b>Plano:</b> <code>{html.escape(plan_name.replace('[Sistema] ', ''))}</code>\n"
        f"° <b>Tipo:</b> <code>{'Usuário privado' if target_type == 'user' else 'Grupo'}</code>\n"
        f"° <b>ID:</b> <code>{target_id}</code>\n"
        f"° <b>Vence em:</b> <code>{html.escape(expires_at)}</code>",
        reply_markup=subscription_editor_keyboard(subscription_id),
    )
    await query.answer()


@router.callback_query(F.data.startswith("admin:subscription_cancel:"))
async def admin_subscription_cancel_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    subscription_id = int(query.data.rsplit(":", 1)[1])
    await cancel_subscription(subscription_id)
    await query.message.edit_text(
        "✅ Acesso cancelado imediatamente.",
        reply_markup=subscriptions_admin_keyboard(await get_active_subscriptions()),
    )
    await query.answer()


@router.message(AdminState.waiting_plan_grant, F.text)
async def receive_plan_grant_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = [part.strip() for part in message.text.split("|")]
    if len(parts) != 2:
        return await message.answer("❌ Use: <code>ID do usuário/chat | quantidade de dias</code>", reply_markup=cancel_keyboard())
    try:
        target_id, days = int(parts[0]), int(parts[1])
    except ValueError:
        return await message.answer("❌ Os IDs e os dias precisam ser numéricos.", reply_markup=cancel_keyboard())
    if days <= 0:
        return await message.answer("❌ O tempo deve ser maior que zero.", reply_markup=cancel_keyboard())
    target_type = "group" if target_id < 0 else "user"
    expires_at = await grant_subscription(0, target_type, target_id, days)
    await state.clear()
    await message.answer(
        f"✅ Acesso liberado para <code>{target_id}</code> até <code>{expires_at}</code>.",
        reply_markup=plans_admin_keyboard(await get_plans()),
    )


@router.callback_query(F.data == "admin:misticpay")
async def misticpay_menu_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.clear()
    misticpay_url, client_id, client_secret, ref_channel, logs_channel = await get_misticpay_settings()
    _, force_join_enabled = await get_force_join_settings()
    await query.message.edit_text(
        "<b>💳 MisticPay</b>\n\n"
        f"URL atual: <code>{html.escape(misticpay_url)}</code>\n"
        f"Client ID: <code>{html.escape(client_id or 'não configurado')}</code>\n"
        f"Client Secret: <code>{html.escape('•' * min(len(client_secret), 12) if client_secret else 'não configurado')}</code>\n"
        f"Canal referência: <code>{html.escape(ref_channel or 'não configurado')}</code>\n"
        f"Canal obrigatório: <code>{'Ativo' if force_join_enabled else 'Desativado'}</code>\n"
        f"Canal logs: <code>{html.escape(logs_channel or 'não configurado')}</code>\n\n"
        "Configure a gate, os canais e acompanhe as transações.",
        reply_markup=misticpay_admin_keyboard(force_join_enabled),
    )
    await query.answer()


@router.callback_query(F.data == "admin:mp_url")
async def mp_url_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.set_state(AdminState.waiting_misticpay_url)
    await query.message.answer(
        "Envie a URL base da MisticPay.\n\nExemplo: <code>https://api.misticpay.com/</code>",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_misticpay_url, F.text)
async def receive_mp_url_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    url = message.text.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return await message.answer("❌ A URL precisa começar com http:// ou https://.", reply_markup=cancel_keyboard())
    _, client_id, client_secret, ref_channel, logs_channel = await get_misticpay_settings()
    await save_misticpay_settings(url, client_id, client_secret, ref_channel, logs_channel)
    await state.clear()
    await message.answer("✅ URL da MisticPay salva.", reply_markup=misticpay_admin_keyboard())


@router.callback_query(F.data == "admin:mp_client_id")
async def mp_client_id_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.set_state(AdminState.waiting_misticpay_client_id)
    await query.message.answer("Envie o Client ID da MisticPay.", reply_markup=cancel_keyboard())
    await query.answer()


@router.message(AdminState.waiting_misticpay_client_id, F.text)
async def receive_mp_client_id_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    client_id = message.text.strip()
    misticpay_url, _, client_secret, ref_channel, logs_channel = await get_misticpay_settings()
    await save_misticpay_settings(misticpay_url, client_id, client_secret, ref_channel, logs_channel)
    await state.clear()
    await message.answer("✅ Client ID salvo.", reply_markup=misticpay_admin_keyboard())


@router.callback_query(F.data == "admin:mp_client_secret")
async def mp_client_secret_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.set_state(AdminState.waiting_misticpay_client_secret)
    await query.message.answer("Envie o Client Secret da MisticPay.", reply_markup=cancel_keyboard())
    await query.answer()


@router.message(AdminState.waiting_misticpay_client_secret, F.text)
async def receive_mp_client_secret_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    client_secret = message.text.strip()
    misticpay_url, client_id, _, ref_channel, logs_channel = await get_misticpay_settings()
    await save_misticpay_settings(misticpay_url, client_id, client_secret, ref_channel, logs_channel)
    await state.clear()
    await message.answer("✅ Client Secret salvo.", reply_markup=misticpay_admin_keyboard())


@router.callback_query(F.data == "admin:mp_ref_channel")
async def mp_ref_channel_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.set_state(AdminState.waiting_reference_channel)
    await query.message.answer(
        "Envie o canal de referência.\n\nUse <code>@canal</code> ou o ID numérico. "
        "Para ativar a obrigatoriedade de entrada, use <code>@canal</code> e deixe o bot como admin no canal.",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_reference_channel, F.text)
async def receive_mp_ref_channel_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    ref_channel = parse_chat_id(message.text)
    misticpay_url, client_id, client_secret, _, logs_channel = await get_misticpay_settings()
    await save_misticpay_settings(misticpay_url, client_id, client_secret, ref_channel, logs_channel)
    await state.clear()
    await message.answer("✅ Canal de referência salvo.", reply_markup=misticpay_admin_keyboard())


@router.callback_query(F.data == "admin:force_join_toggle")
async def force_join_toggle_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    channel, enabled = await get_force_join_settings()
    if not channel:
        return await query.answer("Defina primeiro o canal de referência.", show_alert=True)
    await set_force_join_enabled(not enabled)
    misticpay_url, client_id, client_secret, ref_channel, logs_channel = await get_misticpay_settings()
    await query.answer("Obrigatoriedade atualizada.")
    await query.message.edit_text(
        "<b>💳 MisticPay</b>\n\n"
        f"URL atual: <code>{html.escape(misticpay_url)}</code>\n"
        f"Client ID: <code>{html.escape(client_id or 'não configurado')}</code>\n"
        f"Client Secret: <code>{html.escape('•' * min(len(client_secret), 12) if client_secret else 'não configurado')}</code>\n"
        f"Canal referência: <code>{html.escape(ref_channel or 'não configurado')}</code>\n"
        f"Canal obrigatório: <code>{'Ativo' if not enabled else 'Desativado'}</code>\n"
        f"Canal logs: <code>{html.escape(logs_channel or 'não configurado')}</code>",
        reply_markup=misticpay_admin_keyboard(not enabled),
    )


@router.callback_query(F.data == "admin:mp_logs_channel")
async def mp_logs_channel_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.set_state(AdminState.waiting_logs_channel)
    await query.message.answer(
        "Envie o canal de logs.\n\nUse <code>@canal</code> ou o ID numérico.",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_logs_channel, F.text)
async def receive_mp_logs_channel_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    logs_channel = parse_chat_id(message.text)
    misticpay_url, client_id, client_secret, ref_channel, _ = await get_misticpay_settings()
    await save_misticpay_settings(misticpay_url, client_id, client_secret, ref_channel, logs_channel)
    await state.clear()
    await message.answer("✅ Canal de logs salvo.", reply_markup=misticpay_admin_keyboard())


@router.callback_query(F.data == "admin:text")
async def edit_text_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.set_state(AdminState.waiting_text)
    await query.message.answer(
        "Envie o novo texto do <b>/start</b> escrevendo as tags HTML.\n\n"
        "Variáveis disponíveis:\n"
        "<code>{first_name}</code>\n"
        "<code>{last_name}</code>\n"
        "<code>{username}</code>\n"
        "<code>{user_id}</code>\n\n"
        "Emoji premium:\n"
        "<code>&lt;tg-emoji emoji-id=\"ID\"&gt;🙂&lt;/tg-emoji&gt;</code>",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_text, F.text)
async def receive_text_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    _, photo_file_id = await get_settings()
    error = validate_start_text(message.text, bool(photo_file_id))
    if error:
        await message.answer(f"❌ {html.escape(error)}", reply_markup=cancel_keyboard())
        return

    try:
        rendered = render_variables(message.text, message.from_user)
        if photo_file_id:
            preview = await message.answer_photo(
                photo_file_id,
                caption=rendered,
                parse_mode=ParseMode.HTML,
            )
        else:
            preview = await message.answer(rendered, parse_mode=ParseMode.HTML)
        await preview.delete()
    except TelegramBadRequest as error:
        await message.answer(
            f"❌ HTML inválido:\n<code>{html.escape(str(error))}</code>",
            reply_markup=cancel_keyboard(),
        )
        return

    await save_start_text(message.text)
    await state.clear()
    await message.answer(
        "✅ Texto salvo com sucesso.",
        reply_markup=start_keyboard(bool(photo_file_id)),
    )


@router.callback_query(F.data == "admin:photo")
async def edit_photo_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.set_state(AdminState.waiting_photo)
    await query.message.answer(
        "Envie a nova imagem usando a opção <b>Foto</b> do Telegram.",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_photo, F.photo)
async def receive_photo_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    start_text, _ = await get_settings()
    error = validate_start_text(start_text, True)
    if error:
        await message.answer(
            f"❌ Antes de usar imagem: {html.escape(error)}",
            reply_markup=cancel_keyboard(),
        )
        return

    await save_photo(message.photo[-1].file_id)
    await state.clear()
    await message.answer(
        "✅ Imagem salva com sucesso.",
        reply_markup=start_keyboard(True),
    )


@router.message(AdminState.waiting_photo)
async def invalid_photo_handler(message: Message) -> None:
    if is_admin(message.from_user.id):
        await message.answer(
            "Envie como <b>Foto</b>, não como documento.",
            reply_markup=cancel_keyboard(),
        )


@router.callback_query(F.data == "admin:remove")
async def remove_photo_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await save_photo(None)
    await query.message.answer(
        "✅ Imagem removida.",
        reply_markup=start_keyboard(False),
    )
    await query.answer()


@router.callback_query(F.data == "admin:preview")
async def preview_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    try:
        await send_start(query.bot, query.message.chat.id, query.from_user)
        await query.answer("Prévia enviada.")
    except TelegramBadRequest as error:
        await query.answer("O HTML está inválido.", show_alert=True)
        await query.message.answer(
            f"❌ Erro do Telegram:\n<code>{html.escape(str(error))}</code>"
        )


@router.callback_query(F.data == "admin:help")
async def help_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await query.message.answer(
        "<b>Tags HTML aceitas</b>\n\n"
        "<code>&lt;b&gt;negrito&lt;/b&gt;</code>\n"
        "<code>&lt;i&gt;itálico&lt;/i&gt;</code>\n"
        "<code>&lt;u&gt;sublinhado&lt;/u&gt;</code>\n"
        "<code>&lt;s&gt;riscado&lt;/s&gt;</code>\n"
        "<code>&lt;tg-spoiler&gt;segredo&lt;/tg-spoiler&gt;</code>\n"
        "<code>&lt;a href=\"https://site.com\"&gt;link&lt;/a&gt;</code>\n"
        "<code>&lt;code&gt;código&lt;/code&gt;</code>\n"
        "<code>&lt;blockquote&gt;citação&lt;/blockquote&gt;</code>\n\n"
        "Limite sem imagem: 4096 caracteres.\n"
        "Limite com imagem: 1024 caracteres."
    )
    await query.answer()


@router.message(F.text.regexp(r"^/(?!start\b|admin\b|chassi\b)\w+(?:@\w+)?(?:\s+.+)?$"))
async def dynamic_api_command_handler(message: Message) -> None:
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    command_part = parts[0]
    command_name = normalize_command_name(command_part.split("@", 1)[0])
    spec = API_COMMAND_LOOKUP.get(command_name)
    if not spec:
        return

    if not await enforce_required_channel(message):
        return

    if not await has_active_access(message.chat.id, message.from_user.id, is_private_chat(message.chat)):
        await message.answer(
            "⏳ Seu plano expirou ou este chat não possui um plano ativo.\n\n"
            "Use o botão <b>Planos</b> no /start para comprar ou renovar o acesso."
        )
        return

    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Envie o parâmetro após o comando.\n\n"
            f"Exemplo: <code>/{html.escape(command_name)} {html.escape(spec['example'])}</code>"
        )
        return

    value = parts[1].strip()
    logger.info(
        "Comando recebido | bruto=%r | comando=/%s | valor_digitado=%r",
        text,
        command_name,
        value,
    )
    api_base_url, api_key = await get_api_settings()
    if not api_key:
        await message.answer("A key da API ainda não foi configurada no /admin.")
        return

    status_message = await message.answer("⏳ Processando sua consulta...")
    schedule_query_cleanup(message, status_message)
    try:
        data = await fetch_api_data(api_base_url, api_key, spec, value)
    except urllib.error.HTTPError as error:
        detail = await asyncio.to_thread(error.read) if error.fp else b""
        body = detail.decode("utf-8", errors="replace") if detail else error.reason
        bot_me = await message.bot.get_me()
        parsed_body = parse_api_error_body(body)
        if error.code == 404:
            await status_message.edit_text(
                render_not_found_result(
                    spec["title"],
                    parsed_body,
                    message.from_user,
                    bot_me.username or "",
                ),
                reply_markup=result_keyboard(message.from_user.id, message.message_id),
            )
            return
        await status_message.edit_text(
            f"❌ Erro na consulta ({error.code}):\n<code>{html.escape(str(body))}</code>"
        )
        return
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        await status_message.edit_text(
            f"❌ Não foi possível consultar a API:\n<code>{html.escape(str(error))}</code>"
        )
        return

    bot_me = await message.bot.get_me()
    result_text = render_api_result(spec["title"], data, message.from_user, bot_me.username or "")
    result_token = await create_result_delivery(message.from_user.id, result_text)
    result_message = await send_query_result(
        status_message,
        result_text,
        result_keyboard(message.from_user.id, message.message_id, result_token, bot_me.username or ""),
        query_result_filename(value),
        message.from_user,
        bot_me.username or "",
        delivery_only=bool(RESULTS_API_SECRET and WEB_RESULTS_URL),
    )
    schedule_query_cleanup(message, result_message)


@router.message(Command("chassi"))
async def chassi_handler(message: Message) -> None:
    if not await enforce_required_channel(message):
        return
    if not await has_active_access(message.chat.id, message.from_user.id, is_private_chat(message.chat)):
        await message.answer(
            "⏳ Seu plano expirou ou este chat não possui um plano ativo.\n\n"
            "Use o botão <b>Planos</b> no /start para comprar ou renovar o acesso."
        )
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Use assim: <code>/chassi 9BWZZZ377VT004251</code>")
        return

    chassi = parts[1].strip()
    api_base_url, api_key = await get_api_settings()
    if not api_key:
        await message.answer("A key da API ainda não foi configurada no /admin.")
        return

    status_message = await message.answer("⏳ Processando sua consulta...")
    schedule_query_cleanup(message, status_message)
    try:
        data = await fetch_chassi_data(api_base_url, api_key, chassi)
    except urllib.error.HTTPError as error:
        detail = await asyncio.to_thread(error.read) if error.fp else b""
        body = detail.decode("utf-8", errors="replace") if detail else error.reason
        bot_me = await message.bot.get_me()
        parsed_body = parse_api_error_body(body)
        if error.code == 404:
            await status_message.edit_text(
                render_not_found_result(
                    "Resultado do chassi",
                    parsed_body,
                    message.from_user,
                    bot_me.username or "",
                ),
                reply_markup=result_keyboard(message.from_user.id, message.message_id),
            )
            return
        await status_message.edit_text(
            f"❌ Erro na consulta ({error.code}):\n<code>{html.escape(str(body))}</code>"
        )
        return
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        await status_message.edit_text(
            f"❌ Não foi possível consultar a API:\n<code>{html.escape(str(error))}</code>"
        )
        return

    bot_me = await message.bot.get_me()
    result_text = render_api_result("Resultado do chassi", data, message.from_user, bot_me.username or "")
    result_token = await create_result_delivery(message.from_user.id, result_text)
    result_message = await send_query_result(
        status_message,
        result_text,
        result_keyboard(message.from_user.id, message.message_id, result_token, bot_me.username or ""),
        query_result_filename(chassi),
        message.from_user,
        bot_me.username or "",
        delivery_only=bool(RESULTS_API_SECRET and WEB_RESULTS_URL),
    )
    schedule_query_cleanup(message, result_message)


@router.message(F.text.regexp(r"^/pix(?:@\w+)?(?:\s+.+)?$"))
async def pix_handler(message: Message) -> None:
    if not await enforce_required_channel(message):
        return
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Use assim:\n"
            "<code>/pix 5.00 Nome 71422400409 Pagamento do cliente</code>\n\n"
            "O pagamento será validado automaticamente após a criação do PIX."
        )
        return

    args = parts[1].strip()
    try:
        amount, payer_name, payer_document, description = parse_pix_create_command(f"/pix {args}")
    except ValueError:
        await message.answer(
            "Use assim:\n"
            "<code>/pix 5.00 Nome 71422400409 Pagamento do cliente</code>\n\n"
            "O pagamento será validado automaticamente após a criação do PIX."
        )
        return
    except Exception as error:
        await message.answer(f"❌ Dados inválidos: <code>{html.escape(str(error))}</code>")
        return

    misticpay_url, client_id, client_secret, _, _ = await get_misticpay_settings()
    if not client_id or not client_secret:
        await message.answer("Os pagamentos PIX ainda não foram configurados pelo administrador.")
        return

    status_message = await message.answer("⏳ Criando transação...")
    schedule_query_cleanup(message, status_message, delay=600)
    transaction_id = uuid.uuid4().hex[:12]
    try:
        data = await request_misticpay_json(
            misticpay_url,
            client_id,
            client_secret,
            MISTICPAY_CREATE_PATH,
            {
                "amount": amount,
                "payerName": payer_name,
                "payerDocument": payer_document,
                "transactionId": transaction_id,
                "description": description,
            },
        )
    except urllib.error.HTTPError as error:
        body = (await asyncio.to_thread(error.read)).decode("utf-8", errors="replace") if error.fp else error.reason
        if error.code == 404:
            bot_me = await message.bot.get_me()
            await status_message.edit_text(
                render_not_found_result(
                    "💳 Pagamento PIX",
                    parse_api_error_body(body),
                    message.from_user,
                    bot_me.username or "",
                ),
                reply_markup=result_keyboard(message.from_user.id, message.message_id),
            )
            return
        await status_message.edit_text(
            f"❌ Erro na criação ({error.code}):\n<code>{html.escape(str(body))}</code>"
        )
        return
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        await status_message.edit_text(
            f"❌ Não foi possível criar a transação:\n<code>{html.escape(str(error))}</code>"
        )
        return

    bot_me = await message.bot.get_me()
    response_transaction_id = str(((data or {}).get("data") or {}).get("transactionId") or transaction_id) if isinstance(data, dict) else transaction_id
    response_status = str(((data or {}).get("data") or {}).get("transactionState") or "PENDENTE") if isinstance(data, dict) else "PENDENTE"
    await save_transaction_record(
        transaction_id=response_transaction_id,
        user_id=message.from_user.id,
        amount=amount,
        payer_name=payer_name,
        payer_document=payer_document,
        description=description,
        status=response_status,
        raw_response=data,
    )
    payment_message = await send_pix_result(
        status_message,
        data,
        message.from_user,
        bot_me.username or "",
        result_keyboard(message.from_user.id, message.message_id),
    )
    schedule_query_cleanup(message, payment_message, delay=600)
    await send_payment_notifications(
        message.bot,
        (
            "<b>📣 MisticPay - Referência</b>\n\n"
            f"° <b>Transaction Id:</b> <code>{html.escape(response_transaction_id)}</code>\n"
            f"° <b>Valor:</b> <code>{html.escape(str(amount))}</code>\n"
            f"° <b>Status:</b> <code>{html.escape(response_status)}</code>"
        ),
        (
            "<b>📜 MisticPay - Logs</b>\n\n"
            f"° <b>Usuário:</b> {build_user_mention(message.from_user)}\n"
            f"° <b>Transaction Id:</b> <code>{html.escape(response_transaction_id)}</code>\n"
            f"° <b>Valor:</b> <code>{html.escape(str(amount))}</code>\n"
            f"° <b>CPF:</b> <code>{html.escape(payer_document)}</code>\n"
            f"° <b>Status:</b> <code>{html.escape(response_status)}</code>"
        ),
    )


@router.callback_query(F.data.startswith("result:delete:"))
async def result_delete_handler(query: CallbackQuery) -> None:
    _, _, owner_id_text, command_message_id_text = query.data.split(":")
    owner_id = int(owner_id_text)
    command_message_id = int(command_message_id_text)
    if query.from_user.id != owner_id:
        return await query.answer("Somente quem fez a consulta pode apagar.", show_alert=True)
    await query.message.delete()
    try:
        await query.bot.delete_message(query.message.chat.id, command_message_id)
    except TelegramBadRequest:
        pass
    await query.answer("Mensagem apagada.")


@router.callback_query(F.data == "admin:cancel")
async def cancel_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.clear()
    _, photo_file_id = await get_settings()
    await query.message.answer(
        "Edição cancelada.",
        reply_markup=start_keyboard(bool(photo_file_id)),
    )
    await query.answer()


@router.callback_query(F.data == "admin:buttons")
async def buttons_menu_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.clear()
    buttons = await get_buttons()
    await query.message.edit_text(
        "<b>🔘 Botões do /start</b>\n\nEscolha um botão ou altere a organização das linhas:",
        reply_markup=buttons_admin_keyboard(buttons),
    )
    await query.answer()


@router.callback_query(F.data.startswith("admin:button:"))
async def button_editor_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    index = int(query.data.rsplit(":", 1)[1])
    buttons = await get_buttons()
    if index >= len(buttons):
        return await query.answer("Botão não encontrado.", show_alert=True)
    button = buttons[index]
    await query.message.edit_text(
        f"<b>🔧 {html.escape(button.get('text', 'Botão'))}</b>\n\n"
        f"Link: <code>{html.escape(button.get('url') or 'não configurado')}</code>\n"
        f"Emoji premium: <code>{html.escape(button.get('emoji_id') or 'nenhum')}</code>",
        reply_markup=button_editor_keyboard(index, button),
    )
    await query.answer()


async def ask_button_value(query: CallbackQuery, state: FSMContext, state_name: State, index: int, prompt: str) -> None:
    await state.set_state(state_name)
    await state.update_data(button_index=index)
    await query.message.answer(prompt, reply_markup=cancel_keyboard())
    await query.answer()


@router.callback_query(F.data.startswith("admin:btext:"))
async def ask_button_text_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await ask_button_value(query, state, AdminState.waiting_button_text, int(query.data.rsplit(":", 1)[1]), "Envie o novo texto do botão (1 a 64 caracteres). Ele aparecerá automaticamente em negrito e itálico.")


@router.callback_query(F.data.startswith("admin:burl:"))
async def ask_button_url_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await ask_button_value(query, state, AdminState.waiting_button_url, int(query.data.rsplit(":", 1)[1]), "Envie o link completo começando com <code>https://</code> ou <code>tg://</code>. Envie <code>remover</code> para apagar o link.")


@router.callback_query(F.data.startswith("admin:bemoji:"))
async def ask_button_emoji_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await ask_button_value(
        query,
        state,
        AdminState.waiting_button_emoji,
        int(query.data.rsplit(":", 1)[1]),
        "Envie o próprio <b>emoji premium</b> que deseja usar. "
        "Envie <code>remover</code> para apagar.",
    )


async def update_button_from_message(message: Message, state: FSMContext, field: str, value: str) -> None:
    data = await state.get_data()
    buttons = await get_buttons()
    index = data["button_index"]
    buttons[index][field] = value
    await save_buttons(buttons)
    await state.clear()
    await message.answer("✅ Botão atualizado.", reply_markup=button_editor_keyboard(index, buttons[index]))


@router.message(AdminState.waiting_button_text, F.text)
async def receive_button_text_handler(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not 1 <= len(text) <= 64:
        return await message.answer("❌ Use entre 1 e 64 caracteres.", reply_markup=cancel_keyboard())
    await update_button_from_message(message, state, "text", text)


@router.message(AdminState.waiting_button_url, F.text)
async def receive_button_url_handler(message: Message, state: FSMContext) -> None:
    url = message.text.strip()
    if url.lower() == "remover":
        url = ""
    elif not re.match(r"^(https://|tg://)", url, re.IGNORECASE):
        return await message.answer("❌ O link deve começar com https:// ou tg://.", reply_markup=cancel_keyboard())
    await update_button_from_message(message, state, "url", url)


@router.message(AdminState.waiting_button_emoji)
async def receive_button_emoji_handler(message: Message, state: FSMContext) -> None:
    text = (message.text or message.caption or "").strip()
    if text.lower() == "remover":
        emoji_id = ""
    else:
        entities = message.entities or message.caption_entities or []
        emoji_id = next(
            (
                entity.custom_emoji_id
                for entity in entities
                if entity.custom_emoji_id
            ),
            None,
        )
        if not emoji_id and message.sticker:
            emoji_id = message.sticker.custom_emoji_id
        if not emoji_id:
            await message.answer(
                "❌ Não encontrei um emoji premium nessa mensagem. "
                "Escolha um emoji premium pelo seletor do Telegram e envie aqui.",
                reply_markup=cancel_keyboard(),
            )
            return
    await update_button_from_message(message, state, "emoji_id", emoji_id)


@router.callback_query(F.data.startswith("admin:bstyle:"))
async def button_style_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    index = int(query.data.rsplit(":", 1)[1])
    buttons = await get_buttons()
    styles = ["", "primary", "success", "danger"]
    current = buttons[index].get("style", "")
    buttons[index]["style"] = styles[(styles.index(current) + 1) % len(styles)] if current in styles else ""
    await save_buttons(buttons)
    await query.message.edit_reply_markup(reply_markup=button_editor_keyboard(index, buttons[index]))
    await query.answer("Cor alterada.")


@router.callback_query(F.data.startswith("admin:bmove:"))
async def button_move_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    _, _, index_text, direction_text = query.data.split(":")
    index, new_index = int(index_text), int(index_text) + int(direction_text)
    buttons = await get_buttons()
    if not 0 <= new_index < len(buttons):
        return await query.answer("Esse botão já está no limite.")
    buttons[index], buttons[new_index] = buttons[new_index], buttons[index]
    await save_buttons(buttons)
    await query.message.edit_text(
        f"<b>🔧 {html.escape(buttons[new_index].get('text', 'Botão'))}</b>",
        reply_markup=button_editor_keyboard(new_index, buttons[new_index]),
    )
    await query.answer("Posição alterada.")


@router.callback_query(F.data == "admin:layout")
async def button_layout_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    buttons = await get_buttons()
    current = [button.get("row", 0) for button in buttons]
    layouts = [[0, 0, 1, 1, 2], [0, 1, 2, 3, 4], [0, 0, 0, 1, 1]]
    next_layout = layouts[(layouts.index(current) + 1) % len(layouts)] if current in layouts else layouts[0]
    for button, row in zip(buttons, next_layout):
        button["row"] = row
    await save_buttons(buttons)
    names = {tuple(layouts[0]): "2 + 2 + 1", tuple(layouts[1]): "1 por linha", tuple(layouts[2]): "3 + 2"}
    await query.answer(f"Organização: {names[tuple(next_layout)]}", show_alert=True)


# -----------------------------------------------------------------------------
# Inicialização
# -----------------------------------------------------------------------------

async def main() -> None:
    await setup_database()

    bot = Bot(
        BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    payment_monitor_task = asyncio.create_task(monitor_pending_payments(bot))

    logging.info("Bot iniciado. Painel administrativo: /admin")
    try:
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        payment_monitor_task.cancel()
        try:
            await payment_monitor_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
