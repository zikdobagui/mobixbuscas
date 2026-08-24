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
    WebAppInfo,
)
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse


# -----------------------------------------------------------------------------
# Configuração
# -----------------------------------------------------------------------------

load_dotenv()

logger = logging.getLogger(__name__)
web_app = FastAPI()
LAST_BOT_MESSAGE_BY_CHAT: dict[int, int] = {}

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS_TEXT = os.getenv("ADMIN_IDS", "").strip()
DB_PATH = os.getenv("DB_PATH", "bot.db").strip()
WEB_RESULTS_URL = os.getenv("WEB_RESULTS_URL", "https://mobixretornoconsulta.discloud.app").strip().rstrip("/")
BOT_DISPLAY_NAME = os.getenv("BOT_DISPLAY_NAME", "MOBIX BUSCAS").strip() or "MOBIX BUSCAS"
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")

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

DEFAULT_NEW_USER_REFERENCE_TEXT = (
    "<b>👤 Novo usuário registrado</b>\n\n"
    "Usuário: {MENTION}\n"
    "ID: <code>{ID}</code>\n"
    "Username: <code>{USERNAME}</code>\n"
    "Entrada: <code>{DATE} {TIME}</code>"
)
DEFAULT_GROUP_WELCOME_TEXT = (
    "<b>Bem-vindo, {MENTION}!</b>\n\n"
    "Você entrou no grupo <b>{CHAT_TITLE}</b>."
)
REFERENCE_BUTTON_COLORS = ("🟦", "🟩", "🟥", "⬛")

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
        "aliases": ["foto1"],
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

# Quando uma versão estiver lenta, tenta as demais versões compatíveis sem
# obrigar o usuário a reenviar o comando. As consultas sem alternativa seguem
# usando apenas a base escolhida.
FALLBACK_COMMAND_GROUPS = {
    "cpf": ("cpf", "cpf2", "cpf3", "cpf4", "cpfsus", "score", "inss", "foto"),
    "cpf1": ("cpf", "cpf2", "cpf3", "cpf4", "cpfsus", "score", "inss", "foto"),
    "cpf2": ("cpf", "cpf2", "cpf3", "cpf4", "cpfsus", "score", "inss", "foto"),
    "cpf3": ("cpf", "cpf2", "cpf3", "cpf4", "cpfsus", "score", "inss", "foto"),
    "cpf4": ("cpf", "cpf2", "cpf3", "cpf4", "cpfsus", "score", "inss", "foto"),
    "cpf5": ("cpf", "cpf2", "cpf3", "cpf4", "cpfsus", "score", "inss", "foto"),
    "cpfsus": ("cpfsus", "cpf", "cpf2", "cpf3", "cpf4", "score", "inss", "foto"),
    "score": ("score", "cpf", "cpf2", "cpf3", "cpf4", "cpfsus", "inss", "foto"),
    "inss": ("inss", "cpf", "cpf2", "cpf3", "cpf4", "cpfsus", "score", "foto"),
    "foto": ("foto", "cpf3", "cpf4", "cpf2", "cpf", "cpfsus", "score", "inss"),
    "fotonacional": ("foto", "cpf3", "cpf4", "cpf2", "cpf", "cpfsus", "score", "inss"),
    "fotope": ("fotope", "nome", "nome2"),
    "nome": ("nome", "nome2", "fotope"),
    "nome1": ("nome", "nome2", "fotope"),
    "nome2": ("nome", "nome2", "fotope"),
    "placa": ("placa", "placa2", "placa3"),
    "placa1": ("placa", "placa2", "placa3"),
    "placa2": ("placa", "placa2", "placa3"),
    "placa3": ("placa", "placa2", "placa3"),
    "telefone": ("telefone", "telefone2"),
    "telefone1": ("telefone", "telefone2"),
    "telefone2": ("telefone", "telefone2"),
    "cnpj": ("cnpj", "cnpjfgts"),
    "cnpjfgts": ("cnpjfgts", "cnpj"),
}
FALLBACK_TIMEOUT_SECONDS = 12

HIDDEN_RESPONSE_FIELDS = {"status", "resposta", "developer", "developer2", "base64"}
HIDDEN_RESPONSE_TEXTS = {
    "api desenvolvida por @astrahvhdev telegram",
}
HIDDEN_RESPONSE_PATTERNS = [
    re.compile(r"api\s+desenvolvida\s+por\s+@astrahvhdev\s+telegram", re.IGNORECASE),
]

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
        if "new_user_reference_text" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN new_user_reference_text TEXT")
        if "new_user_reference_photo_file_id" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN new_user_reference_photo_file_id TEXT")
        if "new_user_reference_button_text" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN new_user_reference_button_text TEXT")
        if "new_user_reference_button_url" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN new_user_reference_button_url TEXT")
        if "new_user_reference_button_color" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN new_user_reference_button_color TEXT")
        if "group_welcome_enabled" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN group_welcome_enabled INTEGER")
        if "group_welcome_text" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN group_welcome_text TEXT")
        if "group_welcome_photo_file_id" not in columns:
            await database.execute("ALTER TABLE settings ADD COLUMN group_welcome_photo_file_id TEXT")
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
            "UPDATE settings SET new_user_reference_text = ? WHERE new_user_reference_text IS NULL",
            (DEFAULT_NEW_USER_REFERENCE_TEXT,),
        )
        await database.execute(
            "UPDATE settings SET new_user_reference_button_text = ? WHERE new_user_reference_button_text IS NULL",
            ("Conhecer o bot",),
        )
        await database.execute(
            "UPDATE settings SET new_user_reference_button_color = ? WHERE new_user_reference_button_color IS NULL",
            (REFERENCE_BUTTON_COLORS[0],),
        )
        await database.execute(
            "UPDATE settings SET group_welcome_enabled = ? WHERE group_welcome_enabled IS NULL",
            (0,),
        )
        await database.execute(
            "UPDATE settings SET group_welcome_text = ? WHERE group_welcome_text IS NULL",
            (DEFAULT_GROUP_WELCOME_TEXT,),
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
                image_base64 TEXT,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        delivery_columns = {row[1] for row in await (await database.execute("PRAGMA table_info(result_deliveries)")).fetchall()}
        if "image_base64" not in delivery_columns:
            await database.execute("ALTER TABLE result_deliveries ADD COLUMN image_base64 TEXT")
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


async def get_registered_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            "SELECT user_id, username, first_name, last_name FROM users ORDER BY last_seen_at DESC"
        )
        rows = await cursor.fetchall()
    return [
        {"id": int(row[0]), "username": row[1] or "", "first_name": row[2] or "usuário", "last_name": row[3] or ""}
        for row in rows
    ]


async def get_new_user_reference_settings() -> tuple[str, str | None, str, str, str]:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            """
            SELECT new_user_reference_text, new_user_reference_photo_file_id,
                   new_user_reference_button_text, new_user_reference_button_url,
                   new_user_reference_button_color
            FROM settings WHERE id = 1
            """
        )
        row = await cursor.fetchone()
    if not row:
        return DEFAULT_NEW_USER_REFERENCE_TEXT, None, "Conhecer o bot", "", REFERENCE_BUTTON_COLORS[0]
    return (
        row[0] or DEFAULT_NEW_USER_REFERENCE_TEXT,
        row[1],
        row[2] or "Conhecer o bot",
        row[3] or "",
        row[4] if row[4] in REFERENCE_BUTTON_COLORS else REFERENCE_BUTTON_COLORS[0],
    )


async def save_new_user_reference_settings(
    text: str, photo_file_id: str | None, button_text: str, button_url: str, button_color: str
) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute(
            """
            UPDATE settings SET new_user_reference_text = ?, new_user_reference_photo_file_id = ?,
                new_user_reference_button_text = ?, new_user_reference_button_url = ?,
                new_user_reference_button_color = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1
            """,
            (text, photo_file_id, button_text, button_url, button_color),
        )
        await database.commit()


async def get_group_welcome_settings() -> tuple[bool, str, str | None]:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            "SELECT group_welcome_enabled, group_welcome_text, group_welcome_photo_file_id FROM settings WHERE id = 1"
        )
        row = await cursor.fetchone()
    if not row:
        return False, DEFAULT_GROUP_WELCOME_TEXT, None
    return bool(row[0]), row[1] or DEFAULT_GROUP_WELCOME_TEXT, row[2]


async def save_group_welcome_settings(enabled: bool, text: str, photo_file_id: str | None) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute(
            """
            UPDATE settings
            SET group_welcome_enabled = ?, group_welcome_text = ?,
                group_welcome_photo_file_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (int(enabled), text, photo_file_id),
        )
        await database.commit()


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
                            "command": normalize_command_name(base.get("command") or ""),
                            "param": (base.get("param") or "").strip(),
                            "example": (base.get("example") or "").strip(),
                        }
                    )
                elif isinstance(base, list) and len(base) == 2:
                    default_base = next((item for item in DEFAULT_BASES if item["name"] == base[0]), {})
                    normalized.append(
                        {
                            "name": base[0],
                            "online": bool(base[1]),
                            "url": default_base.get("url", ""),
                            "command": "",
                            "param": "",
                            "example": "",
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


def render_new_user_reference(template: str, user) -> str:
    now = datetime.now()
    name = user.first_name or "Usuário"
    surname = user.last_name or ""
    values = {
        "{ID}": str(user.id),
        "{NAME}": html.escape(name),
        "{SURNAME}": html.escape(surname),
        "{NAMESURNAME}": html.escape(f"{name} {surname}".strip()),
        "{LANG}": html.escape(user.language_code or "não informado"),
        "{DATE}": now.strftime("%d/%m/%Y"),
        "{TIME}": now.strftime("%H:%M"),
        "{WEEKDAY}": now.strftime("%A"),
        "{MENTION}": build_user_mention(user),
        "{USERNAME}": html.escape(f"@{user.username}" if user.username else "sem username"),
    }
    for key, value in values.items():
        template = template.replace(key, value)
    return template


def render_group_welcome(template: str, user, chat) -> str:
    name = user.first_name or "Usuário"
    surname = user.last_name or ""
    username = f"@{user.username}" if user.username else "sem username"
    values = {
        "{ID}": str(user.id),
        "{USER_ID}": str(user.id),
        "{NAME}": html.escape(name),
        "{NOME}": html.escape(name),
        "{SURNAME}": html.escape(surname),
        "{NAMESURNAME}": html.escape(f"{name} {surname}".strip()),
        "{USERNAME}": html.escape(username),
        "{USUARIO}": html.escape(username),
        "{MENTION}": build_user_mention(user),
        "{CHAT_ID}": str(chat.id),
        "{CHAT_TITLE}": html.escape(getattr(chat, "title", "") or "grupo"),
        "{GRUPO}": html.escape(getattr(chat, "title", "") or "grupo"),
    }
    for key, value in values.items():
        template = template.replace(key, value)
    return template


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


def validate_custom_emoji_html(text: str) -> str | None:
    if "<tg-emoji" not in text.lower():
        return None
    stripped = re.sub(
        r'<tg-emoji\s+emoji-id="\d+">.+?</tg-emoji>',
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if "<tg-emoji" in stripped.lower() or "</tg-emoji>" in stripped.lower():
        return 'Emoji premium inválido. Use: <tg-emoji emoji-id="ID_NUMERICO">🙂</tg-emoji>'
    return None


def render_custom_emoji_text(text: str) -> str:
    parts: list[str] = []
    position = 0
    pattern = re.compile(
        r'<tg-emoji\s+emoji-id="\d+">.+?</tg-emoji>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(text):
        parts.append(html.escape(text[position:match.start()]))
        parts.append(match.group(0))
        position = match.end()
    parts.append(html.escape(text[position:]))
    return "".join(parts)


def strip_custom_emoji_tags(text: str) -> str:
    return re.sub(
        r'<tg-emoji\s+emoji-id="\d+">(.+?)</tg-emoji>',
        r"\1",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )


def utf16_index_to_py_index(text: str, utf16_index: int) -> int:
    units = 0
    for index, char in enumerate(text):
        if units >= utf16_index:
            return index
        units += len(char.encode("utf-16-le")) // 2
    return len(text)


def text_with_custom_emoji_tags(message: Message) -> str:
    text = message.text or ""
    entities = [
        entity for entity in (message.entities or [])
        if str(entity.type).lower().endswith("custom_emoji") and entity.custom_emoji_id
    ]
    if not entities:
        return text

    pieces: list[str] = []
    position = 0
    for entity in sorted(entities, key=lambda item: item.offset):
        start = utf16_index_to_py_index(text, entity.offset)
        end = utf16_index_to_py_index(text, entity.offset + entity.length)
        if start < position:
            continue
        emoji_text = text[start:end]
        pieces.append(text[position:start])
        pieces.append(f'<tg-emoji emoji-id="{entity.custom_emoji_id}">{emoji_text}</tg-emoji>')
        position = end
    pieces.append(text[position:])
    return "".join(pieces)


def normalize_command_name(command: str) -> str:
    return command.strip().lower().lstrip("/")


def extract_command_name_from_base(base: dict) -> str | None:
    configured_command = normalize_command_name(base.get("command") or "")
    if configured_command:
        return configured_command

    url = (base.get("url") or "").strip()
    name_text = (base.get("name") or "").strip().lower()
    known_commands = r"(cpf|nome|placa|telefone|email|cep|cnpj|motor|chassi|score|inss|cpfsus|fotonaci|fotope)"

    if not url:
        url = ""

    parsed = urllib.parse.urlparse(url) if url else None
    segments = [segment.lower() for segment in parsed.path.split("/") if segment] if parsed else []

    command = ""
    version = ""
    if len(segments) >= 2:
        command = segments[-2]
        version = segments[-1]
    if not re.fullmatch(known_commands, command):
        match = re.search(rf"\b{known_commands}\b", name_text)
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

    spec = API_COMMAND_LOOKUP.get(command_name) or build_base_command_spec(base, command_name)
    if not spec:
        return f"° <b>Comando:</b> <code>/{html.escape(command_name)} VALOR</code>"

    return (
        f"° <b>Comando:</b> <code>/{html.escape(command_name)} {html.escape(spec['example'])}</code>"
    )


def build_base_command_spec(base: dict, command_name: str | None = None) -> dict | None:
    command = normalize_command_name(command_name or base.get("command") or "")
    if not command:
        return None

    param = (base.get("param") or "").strip()
    if not param:
        placeholders = re.findall(r"\{([A-Za-z_][A-Za-z0-9_-]*)\}", base.get("url") or "")
        param = placeholders[0] if placeholders else command

    return {
        "aliases": [command],
        "title": base.get("name") or f"Consulta {command}",
        "path": "",
        "param": param,
        "example": (base.get("example") or "VALOR").strip() or "VALOR",
    }


async def get_command_spec(command_name: str) -> dict | None:
    spec = API_COMMAND_LOOKUP.get(command_name)
    if spec:
        return spec

    for base in await get_bases():
        base_command = extract_command_name_from_base(base)
        if base_command and normalize_command_name(base_command) == command_name:
            return build_base_command_spec(base, command_name)
    return None


def build_api_command_url(api_base_url: str, api_key: str, spec: dict, value: str) -> str:
    base = api_base_url.rstrip("/") + "/"
    query = urllib.parse.urlencode({"apikey": api_key, spec["param"]: value})
    return f"{base}{spec['path'].lstrip('/')}?{query}"


def build_configured_base_url(api_base_url: str, api_key: str, spec: dict, value: str, configured_url: str) -> str:
    template = configured_url.strip()
    if not template:
        return build_api_command_url(api_base_url, api_key, spec, value)

    if not re.match(r"^https?://", template, re.IGNORECASE):
        template = api_base_url.rstrip("/") + "/" + template.lstrip("/")

    encoded_value = urllib.parse.quote_plus(value)
    placeholders = set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_-]*)\}", template))
    for placeholder in placeholders:
        template = template.replace("{" + placeholder + "}", encoded_value)

    parsed = urllib.parse.urlsplit(template)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    updated_query: list[tuple[str, str]] = []
    has_api_key = False
    has_param = False
    for key, current_value in query:
        lowered = key.lower()
        if lowered == "apikey":
            has_api_key = True
            updated_query.append((key, api_key))
        elif key == spec["param"]:
            has_param = True
            updated_query.append((key, value))
        elif current_value.lower() in {"seutoken", "token"} and api_key:
            updated_query.append((key, api_key))
        else:
            updated_query.append((key, current_value))

    if api_key and not has_api_key:
        updated_query.append(("apikey", api_key))
    if not has_param and not placeholders:
        updated_query.append((spec["param"], value))

    return urllib.parse.urlunsplit(
        parsed._replace(query=urllib.parse.urlencode(updated_query))
    )


def sanitize_api_result(data: object) -> object:
    if isinstance(data, dict):
        sanitized: dict[str, object] = {}
        for key, value in data.items():
            if key.lower() in HIDDEN_RESPONSE_FIELDS:
                continue
            sanitized_value = sanitize_api_result(value)
            if sanitized_value is None and isinstance(value, str):
                continue
            sanitized[key] = sanitized_value
        return sanitized
    if isinstance(data, list):
        sanitized_items = [sanitize_api_result(item) for item in data]
        return [
            item for original, item in zip(data, sanitized_items)
            if not (item is None and isinstance(original, str))
        ]
    if isinstance(data, str):
        cleaned = clean_hidden_response_text(data).strip()
        if not cleaned or cleaned.lower() in HIDDEN_RESPONSE_TEXTS:
            return None
        return cleaned
    return data


def clean_hidden_response_text(text: str) -> str:
    cleaned = text
    for pattern in HIDDEN_RESPONSE_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return cleaned


def extract_base64_photo(data: object) -> bytes | None:
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() == "base64" and isinstance(value, str):
                try:
                    raw = value.split(",", 1)[1] if "," in value else value
                    image = base64.b64decode(raw, validate=True)
                    if image.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")):
                        return image
                except (ValueError, base64.binascii.Error):
                    continue
            found = extract_base64_photo(value)
            if found:
                return found
    if isinstance(data, list):
        for value in data:
            found = extract_base64_photo(value)
            if found:
                return found
    return None


def is_html_error_response(data: object) -> bool:
    """Evita exibir páginas 404/erro da API como se fossem resultados."""
    if not isinstance(data, str):
        return False
    normalized = data.lstrip().lower()
    return normalized.startswith("<!doctype html") or normalized.startswith("<html")


def parse_api_response(body: str) -> object:
    """Aceita JSON normal e o formato incompleto retornado por algumas bases."""
    normalized = clean_hidden_response_text(body).lstrip("\ufeff \t\r\n")
    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        # Algumas rotas retornam os pares JSON sem as chaves externas.
        if normalized.startswith('"') and normalized.rstrip().endswith("}"):
            try:
                return json.loads("{" + normalized)
            except json.JSONDecodeError:
                pass
        return body


def parse_api_error_body(body: str) -> object:
    body = clean_hidden_response_text(body)
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


def render_api_failure(title: str, status_code: int, user, bot_username: str) -> str:
    messages = {
        401: "A base não autorizou esta consulta. Tente novamente mais tarde.",
        403: "Esta consulta não está disponível no momento.",
        429: "Muitas consultas foram enviadas. Aguarde alguns instantes e tente novamente.",
        500: "A base apresentou instabilidade. Tente novamente em alguns minutos.",
        502: "A base está temporariamente indisponível. Tente novamente mais tarde.",
        503: "A base está em manutenção. Use outra base ou tente novamente mais tarde.",
        504: "A base demorou para responder. Tente novamente em alguns instantes.",
    }
    footer = (
        f"\n\n<b>Consulta enviada para:</b> {build_user_mention(user)}\n"
        f"<b>Creditos:</b> @{html.escape(bot_username or 'bot')}"
    )
    return (
        f"<b>{html.escape(title)}</b>\n\n"
        "° <b>Resultado:</b> <code>Consulta indisponível</code>\n"
        f"° <b>Mensagem:</b> <code>{html.escape(messages.get(status_code, 'Não foi possível concluir a consulta agora. Tente novamente mais tarde.'))}</code>"
        f"{footer}"
    )


def html_to_plain_text(text: str) -> str:
    text = re.sub(r'<a\s+href="[^"]*">(.*?)</a>', r"\1", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def query_result_filename(value: str) -> str:
    safe_value = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_-")
    return f"{safe_value[:80] or 'resultado'}.txt"


async def create_result_delivery(user_id: int, result_text: str, image: bytes | None = None) -> str:
    token = uuid.uuid4().hex
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    plain_text = html_to_plain_text(result_text)
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute("DELETE FROM result_deliveries WHERE expires_at <= CURRENT_TIMESTAMP")
        await database.execute(
            "INSERT INTO result_deliveries (token, user_id, result_text, image_base64, expires_at) VALUES (?, ?, ?, ?, ?)",
            (token, user_id, plain_text, base64.b64encode(image).decode("ascii") if image else None, expires_at),
        )
        await database.commit()

    return token


async def get_private_result_delivery(token: str, user_id: int) -> tuple[str, bytes | None] | None:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            """
            SELECT result_text, image_base64 FROM result_deliveries
            WHERE token = ? AND user_id = ? AND expires_at > CURRENT_TIMESTAMP
            """,
            (token, user_id),
        )
        row = await cursor.fetchone()
        if row:
            await database.execute("DELETE FROM result_deliveries WHERE token = ?", (token,))
            await database.commit()
    return (row[0], base64.b64decode(row[1]) if row and row[1] else None) if row else None


async def get_web_result_delivery(token: str) -> tuple[str, str, str | None] | None:
    async with aiosqlite.connect(DB_PATH) as database:
        cursor = await database.execute(
            """
            SELECT result_text, expires_at, image_base64 FROM result_deliveries
            WHERE token = ? AND expires_at > CURRENT_TIMESTAMP
            """,
            (token,),
        )
        row = await cursor.fetchone()
    return (row[0], row[1], row[2]) if row else None


@web_app.get("/api/results/{token}")
async def web_result_api(token: str) -> dict:
    result = await get_web_result_delivery(token)
    if not result:
        raise HTTPException(status_code=404, detail="Resultado expirado ou indisponível.")
    return {"result": result[0], "expires_at": result[1], "image_base64": result[2]}


@web_app.get("/api/bases")
async def web_bases_api() -> dict:
    commands = []
    for base in await get_bases():
        command_name = extract_command_name_from_base(base)
        if not command_name:
            continue
        spec = API_COMMAND_LOOKUP.get(command_name) or build_base_command_spec(base, command_name)
        if not spec:
            continue
        param = spec.get("param") or command_name
        display_param = "cpf" if command_name.startswith("cpf") and param == "code" else param
        commands.append({
            "name": strip_custom_emoji_tags(base.get("name") or spec["title"]),
            "command": command_name,
            "param": display_param,
            "example": spec.get("example") or "VALOR",
            "online": bool(base.get("online")),
        })
    return {
        "bot_name": BOT_DISPLAY_NAME,
        "bot_username": BOT_USERNAME,
        "commands": commands,
    }


@web_app.get("/api/planos")
async def web_plans_api() -> dict:
    plans = await get_plans(active_only=True)
    return {
        "bot_name": BOT_DISPLAY_NAME,
        "bot_username": BOT_USERNAME,
        "plans": [
            {
                "id": plan_id,
                "name": name,
                "category": category,
                "duration_days": duration_days,
                "price": price,
            }
            for plan_id, name, category, duration_days, price, _ in plans
        ],
    }


@web_app.get("/planos", response_class=HTMLResponse)
async def web_plans_page() -> str:
    return """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0b1020"><title>Planos</title><style>
:root{--bg:#080f1d;--panel:#10182c;--panel2:#0c1426;--line:#22304a;--text:#f7fbff;--muted:#93a8c9;--blue:#4388ff;--blue2:#2f73ef;--green:#3ddc97;--gold:#ffd166}*{box-sizing:border-box}body{margin:0;min-height:100dvh;background:radial-gradient(circle at top,#172a56 0,transparent 36%),linear-gradient(180deg,#080f1d,#111326 62%,#0a101c);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.top{position:sticky;top:0;z-index:3;border-bottom:1px solid var(--line);background:rgba(8,15,29,.94);backdrop-filter:blur(14px)}.top-inner{display:flex;align-items:center;justify-content:space-between;gap:14px;width:min(100%,1080px);margin:0 auto;padding:14px clamp(14px,4vw,24px)}.brand{display:flex;align-items:center;gap:12px;min-width:0}.logo{display:grid;place-items:center;width:42px;height:42px;border-radius:12px;background:linear-gradient(145deg,#192744,#101a31);font-size:23px;border:1px solid #28395b}.brand strong{display:block;font-size:18px;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.brand strong span{color:var(--blue)}.brand small{display:block;color:var(--muted);margin-top:2px}.open-bot,.primary{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:42px;border:0;border-radius:12px;background:linear-gradient(180deg,var(--blue),var(--blue2));color:white;font-weight:850;text-decoration:none;padding:0 18px;cursor:pointer}.shell{width:min(100%,1080px);margin:0 auto;padding:clamp(24px,5vw,48px) clamp(14px,4vw,24px) 56px}.hero{text-align:center;margin:0 auto 26px;max-width:720px}.hero h1{margin:0 0 10px;font-size:clamp(30px,7vw,48px);line-height:1.05}.hero h1 span{color:var(--blue)}.hero p{margin:0;color:#a6bce0;font-size:clamp(15px,3.5vw,17px);line-height:1.5}.tabs{display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:620px;margin:24px auto 28px;padding:6px;border:1px solid var(--line);border-radius:16px;background:#0b1326}.tab{border:0;border-radius:12px;background:transparent;color:#9fb4d2;font-weight:900;padding:12px;cursor:pointer}.tab.active{background:var(--blue);color:white}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:16px}.plan{position:relative;overflow:hidden;border:1px solid var(--line);border-radius:18px;background:linear-gradient(180deg,#121c34,#0c1426);padding:20px;box-shadow:0 18px 42px rgba(0,0,0,.3)}.plan:before{content:"";position:absolute;inset:0 0 auto 0;height:4px;background:linear-gradient(90deg,var(--blue),var(--green))}.badge{display:inline-flex;border:1px solid #265f76;border-radius:999px;background:#0e3446;color:#9fe8ff;padding:5px 10px;font-size:11px;font-weight:900;text-transform:uppercase}.plan h2{margin:16px 0 12px;font-size:20px;line-height:1.2;overflow-wrap:anywhere}.price{display:flex;align-items:flex-end;gap:6px;margin:0 0 10px}.price strong{font-size:34px;line-height:1;color:white}.price span{color:var(--muted);font-weight:700;margin-bottom:4px}.meta{display:grid;gap:9px;margin:16px 0 20px;color:#c7d8f2}.meta div{display:flex;align-items:center;gap:9px;border:1px solid #202c46;border-radius:12px;background:#0a1020;padding:11px 12px}.hint{margin:0 0 18px;color:var(--muted);line-height:1.45;font-size:14px}.empty{display:none;text-align:center;color:var(--muted);padding:36px 0}@media(max-width:560px){.top-inner{padding:12px}.brand small{display:none}.open-bot{padding:0 12px}.tabs{grid-template-columns:1fr}.plan{border-radius:15px}.price strong{font-size:30px}}
</style></head><body><header class="top"><div class="top-inner"><div class="brand"><div class="logo">💎</div><div><strong id="brand">MOBIX <span>BUSCAS</span></strong><small>Planos disponíveis</small></div></div><a class="open-bot" id="openBot" href="#" target="_blank" rel="noopener">▷ Abrir Bot</a></div></header><main class="shell"><section class="hero"><h1>Planos do <span>Bot</span></h1><p>Escolha entre acesso privado individual ou liberação para grupos.</p></section><div class="tabs"><button class="tab active" data-cat="user">🔐 Planos privados</button><button class="tab" data-cat="group">👥 Planos para grupos</button></div><section class="grid" id="grid"></section><p class="empty" id="empty">Nenhum plano disponível nessa categoria.</p></main><script>
const grid=document.querySelector('#grid'),empty=document.querySelector('#empty'),brand=document.querySelector('#brand'),openBot=document.querySelector('#openBot');let plans=[],active='user',botUser='';
const esc=s=>String(s||'').replace(/[<>&"]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]));
const money=v=>Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
function botUrl(){return botUser?`https://t.me/${encodeURIComponent(botUser)}?start=start`:'#'}
function render(){const items=plans.filter(p=>p.category===active);empty.style.display=items.length?'none':'block';grid.innerHTML=items.map(p=>`<article class="plan"><span class="badge">${active==='user'?'Privado':'Grupo'}</span><h2>${esc(p.name)}</h2><p class="price"><strong>${money(p.price)}</strong><span>/${p.duration_days} dias</span></p><div class="meta"><div>⏱ ${p.duration_days} dias de acesso</div><div>${active==='user'?'👤 Uso no privado':'👥 Liberação para grupo'}</div></div><p class="hint">${active==='user'?'Ideal para consultar direto no privado com mais privacidade.':'Ideal para liberar comandos em um grupo inteiro.'}</p><a class="primary" href="${botUrl()}" target="_blank" rel="noopener">↗ Comprar no Bot</a></article>`).join('')}
document.querySelectorAll('.tab').forEach(btn=>btn.addEventListener('click',()=>{active=btn.dataset.cat;document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('active',b===btn));render()}));
fetch('/api/planos').then(r=>r.json()).then(data=>{plans=data.plans||[];botUser=data.bot_username||'';const name=data.bot_name||'MOBIX BUSCAS';const parts=name.split(/\\s+/);brand.innerHTML=`${esc(parts[0]||name)} <span>${esc(parts.slice(1).join(' ')||'BOT')}</span>`;openBot.href=botUrl();render()}).catch(()=>{empty.textContent='Não foi possível carregar os planos.';empty.style.display='block'});
</script></body></html>"""


@web_app.get("/bases", response_class=HTMLResponse)
async def web_bases_page() -> str:
    return """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0d1324"><title>Bases disponíveis</title>
<style>
:root{--bg:#080f1d;--panel:#10182c;--panel2:#0c1426;--line:#22304a;--text:#f4f7fb;--muted:#8ea3c2;--blue:#4388ff;--blue2:#2f73ef;--green:#38d48a;--danger:#ff6b7a}*{box-sizing:border-box}body{margin:0;min-height:100dvh;background:linear-gradient(180deg,#080f1d,#111326 58%,#0a101c);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.top{position:sticky;top:0;z-index:3;border-bottom:1px solid var(--line);background:rgba(8,15,29,.94);backdrop-filter:blur(14px)}.top-inner{display:flex;align-items:center;justify-content:space-between;gap:14px;width:min(100%,1100px);margin:0 auto;padding:14px clamp(14px,4vw,24px)}.brand{display:flex;align-items:center;gap:12px;min-width:0}.logo{display:grid;place-items:center;width:42px;height:42px;border-radius:12px;background:linear-gradient(145deg,#192744,#101a31);font-size:24px;border:1px solid #28395b}.brand strong{display:block;font-size:18px;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.brand strong span{color:var(--blue)}.brand small{display:block;color:var(--muted);margin-top:2px}.open-bot,.primary{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:42px;border:0;border-radius:12px;background:linear-gradient(180deg,var(--blue),var(--blue2));color:white;font-weight:800;text-decoration:none;padding:0 18px;cursor:pointer}.shell{width:min(100%,1100px);margin:0 auto;padding:clamp(22px,5vw,48px) clamp(14px,4vw,24px) 56px}.hero{text-align:center;margin:0 auto 28px;max-width:720px}.hero h1{margin:0 0 10px;font-size:clamp(30px,7vw,48px);line-height:1.05}.hero h1 span{color:var(--blue)}.hero p{margin:0;color:#9bb4d9;font-size:clamp(15px,3.5vw,17px);line-height:1.5}.search{display:flex;align-items:center;gap:10px;margin:24px auto 14px;max-width:720px;border:1px solid var(--line);border-radius:16px;background:#0d1427;padding:0 14px}.search input{width:100%;height:50px;border:0;outline:0;background:transparent;color:var(--text);font-size:16px}.search svg{flex:0 0 auto;color:var(--muted)}.chips{display:flex;flex-wrap:wrap;justify-content:center;gap:10px;margin:16px auto 10px;max-width:760px}.chip{border:1px solid var(--line);border-radius:999px;background:#10182b;color:#9fb4d2;font-weight:800;padding:8px 16px;cursor:pointer;text-transform:uppercase}.chip.active{background:var(--blue);border-color:var(--blue);color:white}.count{text-align:center;color:var(--muted);font-size:14px;margin:14px 0 34px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:16px}.card{border:1px solid var(--line);border-radius:16px;background:linear-gradient(180deg,#111a31,#0d1427);padding:18px;box-shadow:0 18px 42px rgba(0,0,0,.28)}.card-head{display:flex;gap:12px;align-items:center;margin-bottom:14px}.icon{display:grid;place-items:center;width:44px;height:44px;border:1px solid #226449;border-radius:12px;background:#123a35;color:#8dffd0}.title{min-width:0}.title h2{margin:0;font-size:16px;line-height:1.2;text-transform:uppercase;overflow-wrap:anywhere}.tag{display:inline-flex;margin-top:6px;border:1px solid #1d7d5c;border-radius:999px;background:#0d493a;color:#75f5bf;padding:4px 9px;font-size:11px;font-weight:850;text-transform:uppercase}.tag.off{border-color:#74404a;background:#3a1420;color:#ff9baa}.box{border:1px solid #202c46;border-radius:13px;background:#0a1020;padding:13px 14px;margin:12px 0 14px}.box small{display:block;color:var(--muted);margin-bottom:7px}.cmd{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;color:#d8e7ff;overflow-wrap:anywhere}.actions{display:grid;grid-template-columns:1fr 1fr;gap:10px}.ghost{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:42px;border:1px solid var(--line);border-radius:12px;background:#0e172b;color:white;font-weight:800;cursor:pointer;text-decoration:none}.empty{display:none;text-align:center;color:var(--muted);padding:36px 0}@media(max-width:560px){.top-inner{padding:12px}.brand small{display:none}.open-bot{padding:0 12px}.shell{padding-top:28px}.actions{grid-template-columns:1fr}.card{border-radius:14px}}
</style></head><body><header class="top"><div class="top-inner"><div class="brand"><div class="logo">🔎</div><div><strong id="brand">MOBIX <span>BUSCAS</span></strong><small>Comandos disponíveis</small></div></div><a class="open-bot" id="openBot" href="#" target="_blank" rel="noopener">▷ Abrir Bot</a></div></header><main class="shell"><section class="hero"><h1>Comandos do <span>Bot</span></h1><p>Toque em um comando para copiar ou abrir diretamente no Telegram</p><label class="search"><svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="m21 21-4.3-4.3m1.3-5.2a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0Z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><input id="search" placeholder="Buscar comando..." autocomplete="off"></label><div class="chips" id="chips"></div><p class="count" id="count"></p></section><section class="grid" id="grid"></section><p class="empty" id="empty">Nenhum comando encontrado.</p></main><script>
const grid=document.querySelector('#grid'),chips=document.querySelector('#chips'),search=document.querySelector('#search'),count=document.querySelector('#count'),empty=document.querySelector('#empty'),brand=document.querySelector('#brand'),openBot=document.querySelector('#openBot');let commands=[],active='todos',botUser='';
const label=s=>String(s||'').replace(/[<>&"]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]));
const category=c=>String(c.param||c.command||'outros').toLowerCase();
const commandText=c=>`/${c.command} ${c.example||'VALOR'}`;
function botUrl(text=''){return botUser?`https://t.me/${encodeURIComponent(botUser)}${text?`?text=${encodeURIComponent(text)}`:''}`:'#'}
function renderChips(){const cats=['todos',...Array.from(new Set(commands.map(category))).sort()];chips.innerHTML=cats.map(cat=>`<button class="chip ${cat===active?'active':''}" data-cat="${label(cat)}">${label(cat)}</button>`).join('')}
function filtered(){const q=search.value.trim().toLowerCase();return commands.filter(c=>(active==='todos'||category(c)===active)&&[c.name,c.command,c.param].join(' ').toLowerCase().includes(q))}
function render(){const items=filtered();count.textContent=`${items.length} comando${items.length===1?'':'s'} encontrado${items.length===1?'':'s'}`;empty.style.display=items.length?'none':'block';grid.innerHTML=items.map(c=>{const cmd=commandText(c);return `<article class="card"><div class="card-head"><div class="icon">⌕</div><div class="title"><h2>${label(c.name)}</h2><span class="tag ${c.online?'':'off'}">${label(category(c))}</span></div></div><div class="box"><small>Comando:</small><div class="cmd">${label(cmd)}</div></div><div class="actions"><button class="ghost" data-copy="${label(cmd)}">⧉ Copiar</button><a class="primary" href="${botUrl(cmd)}" target="_blank" rel="noopener">↗ Usar no Bot</a></div></article>`}).join('')}
chips.addEventListener('click',e=>{const b=e.target.closest('.chip');if(!b)return;active=b.dataset.cat;renderChips();render()});
grid.addEventListener('click',async e=>{const b=e.target.closest('[data-copy]');if(!b)return;try{await navigator.clipboard.writeText(b.dataset.copy);b.textContent='✓ Copiado';setTimeout(()=>b.textContent='⧉ Copiar',1300)}catch{b.textContent='Selecione e copie';}});
search.addEventListener('input',render);
fetch('/api/bases').then(r=>r.json()).then(data=>{commands=data.commands||[];botUser=data.bot_username||'';const name=data.bot_name||'MOBIX BUSCAS';const parts=name.split(/\\s+/);brand.innerHTML=`${label(parts[0]||name)} <span>${label(parts.slice(1).join(' ')||'BOT')}</span>`;openBot.href=botUrl();renderChips();render()}).catch(()=>{count.textContent='Não foi possível carregar os comandos.'});
</script></body></html>"""


@web_app.get("/r/{token}", response_class=HTMLResponse)
async def web_result_page(token: str) -> str:
    return """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#101b2a"><title>Resultado da consulta</title>
<style>
:root{--ink:#eaf2f8;--muted:#9fb1c3;--surface:#152437;--surface-2:#0d1826;--line:#294056;--accent:#42c987;--accent-dark:#113a2a;--danger:#ff9f9f}*{box-sizing:border-box}body{min-height:100dvh;margin:0;background:radial-gradient(circle at top left,#1c3c55 0,transparent 35%),linear-gradient(145deg,#09131f,#101e2d 55%,#0a1622);color:var(--ink);font:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.shell{width:min(100%,980px);margin:0 auto;padding:clamp(16px,4vw,48px) clamp(12px,3vw,28px)}.card{overflow:hidden;border:1px solid var(--line);border-radius:22px;background:rgba(21,36,55,.94);box-shadow:0 24px 70px #0008}.hero{display:flex;gap:16px;align-items:center;padding:clamp(18px,4vw,32px);border-bottom:1px solid var(--line);background:linear-gradient(110deg,#17344c,#13283b)}.mark{display:grid;place-items:center;flex:0 0 46px;width:46px;height:46px;border-radius:14px;background:var(--accent-dark);font-size:24px}.eyebrow{margin:0 0 4px;color:var(--accent);font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.hero h1{margin:0;font-size:clamp(21px,4vw,30px);letter-spacing:-.03em}.content{padding:clamp(16px,3vw,28px)}.tools{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}.status{margin:0;color:var(--muted);font-size:14px}.copy{border:1px solid #397b61;border-radius:10px;padding:10px 14px;background:var(--accent-dark);color:#dfffea;font-weight:750;cursor:pointer;transition:transform .15s,background .15s}.copy:hover{background:#19563d}.copy:active{transform:scale(.97)}.copy:disabled{opacity:.55;cursor:wait}.photo{display:block;width:min(100%,420px);max-height:560px;object-fit:contain;margin:0 auto 16px;border:1px solid var(--line);border-radius:14px;background:var(--surface-2)}.photo[hidden]{display:none}.result{min-height:160px;margin:0;padding:clamp(14px,3vw,24px);overflow:auto;border:1px solid var(--line);border-radius:14px;background:var(--surface-2);color:#dce9f4;font:clamp(12px,2.6vw,14px)/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}.error{margin:0;color:var(--danger);font-weight:650}@media(max-width:520px){.shell{padding:12px}.card{border-radius:16px}.hero{padding:18px}.tools{align-items:stretch;flex-direction:column}.copy{width:100%}.result{border-radius:11px}}
</style></head><body><div class="shell"><main class="card"><header class="hero"><div class="mark">✓</div><div><p class="eyebrow">Consulta privada</p><h1>Resultado da consulta</h1></div></header><section class="content"><div class="tools"><p class="status" id="status">Carregando resultado com segurança...</p><button class="copy" id="copy" type="button" disabled>⧉ Copiar retorno</button></div><img class="photo" id="photo" hidden alt="Foto retornada pela consulta"><pre class="result" id="result"></pre><p class="error" id="error"></p></section></main></div><script>
const token=location.pathname.split('/').pop(),result=document.querySelector('#result'),status=document.querySelector('#status'),error=document.querySelector('#error'),copy=document.querySelector('#copy'),photo=document.querySelector('#photo');
fetch('/api/results/'+encodeURIComponent(token)).then(async response=>{const data=await response.json();if(!response.ok)throw new Error(data.detail||'Resultado indisponível.');result.textContent=data.result;if(data.image_base64){photo.src='data:image/jpeg;base64,'+data.image_base64;photo.hidden=false;}status.textContent='Disponível até '+data.expires_at;copy.disabled=false;}).catch(reason=>{status.textContent='';error.textContent=reason.message;});
copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(result.textContent);copy.textContent='✓ Retorno copiado';setTimeout(()=>copy.textContent='⧉ Copiar retorno',1800);}catch{error.textContent='Não foi possível copiar automaticamente. Selecione o texto para copiar.';}});
</script></body></html>"""


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
            "Use um dos botões abaixo para ver seu resultado com privacidade.\n\n"
            f"<b>Consulta enviada para:</b> {build_user_mention(user)}\n"
            f"<b>Creditos:</b> @{html.escape(bot_username or 'bot')}",
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
    value = value.removeprefix("https://t.me/").removeprefix("http://t.me/").strip("/")
    if value and not value.startswith("@") and not value.lstrip("-").isdigit():
        return f"@{value}"
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
        data = parse_api_response(body)
        if is_html_error_response(data):
            raise ValueError("A base retornou uma página HTML de erro.")
        return data

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


async def update_plan_duration(plan_id: int, duration_days: int) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute(
            "UPDATE plans SET duration_days = ? WHERE id = ?",
            (duration_days, plan_id),
        )
        await database.commit()


async def update_plan_price(plan_id: int, price: float) -> None:
    async with aiosqlite.connect(DB_PATH) as database:
        await database.execute("UPDATE plans SET price = ? WHERE id = ?", (price, plan_id))
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


async def bot_start_url(bot: Bot) -> str:
    global BOT_USERNAME
    if not BOT_USERNAME:
        try:
            bot_me = await bot.get_me()
            BOT_USERNAME = bot_me.username or ""
        except TelegramBadRequest:
            BOT_USERNAME = ""
    return f"https://t.me/{BOT_USERNAME}?start=start" if BOT_USERNAME else WEB_RESULTS_URL


async def inactive_access_keyboard(bot: Bot) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✨ Saiba Mais", url=await bot_start_url(bot))
    ]])


async def send_inactive_access_message(message: Message, command_name: str) -> Message:
    sent_message = await message.answer(
        f"<b>Olá, {html.escape(message.from_user.first_name or 'usuário')}!</b> "
        f"O módulo <b>{html.escape(command_name.upper())}</b> está disponível exclusivamente "
        "para assinantes do nosso plano privado.\n\n"
        "<b>Quer saber mais?</b> Clique abaixo para descobrir todos os benefícios:",
        reply_markup=await inactive_access_keyboard(message.bot),
    )
    remember_last_bot_message(sent_message)
    return sent_message


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


async def send_error_log(bot: Bot, message: Message, command: str, status_code: int, error: object) -> None:
    _, _, _, _, logs_channel = await get_misticpay_settings()
    if not (logs_channel or "").strip():
        return
    text = (
        "<b>⚠️ Erro de consulta</b>\n\n"
        f"° <b>Comando:</b> <code>/{html.escape(command)}</code>\n"
        f"° <b>Status:</b> <code>{status_code}</code>\n"
        f"° <b>Usuário:</b> {build_user_mention(message.from_user)}\n"
        f"° <b>Chat:</b> <code>{message.chat.id}</code>\n"
        f"° <b>Detalhe:</b> <code>{html.escape(str(error))[:700]}</code>"
    )
    try:
        await bot.send_message(logs_channel, text, parse_mode=ParseMode.HTML)
    except Exception:
        logger.exception("Falha ao enviar erro para canal de logs %s", logs_channel)


async def notify_new_user_reference(bot: Bot, user) -> None:
    _, _, _, reference_channel, _ = await get_misticpay_settings()
    if not (reference_channel or "").strip():
        return
    text, photo_file_id, button_text, button_url, button_color = await get_new_user_reference_settings()
    keyboard = None
    if button_url:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"{button_color} {button_text}", url=button_url)
        ]])
    try:
        rendered = render_new_user_reference(text, user)
        if photo_file_id:
            await bot.send_photo(reference_channel, photo_file_id, caption=rendered, reply_markup=keyboard)
        else:
            await bot.send_message(reference_channel, rendered, reply_markup=keyboard)
    except Exception:
        logger.exception("Falha ao anunciar novo usuário no canal de referência %s", reference_channel)


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


async def fetch_api_data(
    api_base_url: str,
    api_key: str,
    spec: dict,
    value: str,
    configured_url: str = "",
    timeout: int = 60,
) -> object:
    url = build_configured_base_url(api_base_url, api_key, spec, value, configured_url)
    logger.info(
        "Enviando consulta | comando=/%s | parametro=%s | valor=%r | url=%s",
        spec["aliases"][0],
        spec["param"],
        value,
        url,
    )

    def _request() -> object:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
        data = parse_api_response(body)
        if is_html_error_response(data):
            raise ValueError("A base retornou uma página HTML de erro.")
        return data

    return await asyncio.to_thread(_request)


async def fallback_specs_for(command_name: str, primary_spec: dict) -> list[dict]:
    aliases = FALLBACK_COMMAND_GROUPS.get(command_name, ())
    candidates = [API_COMMAND_LOOKUP[alias] for alias in aliases if alias in API_COMMAND_LOOKUP]
    if not candidates:
        return [primary_spec]
    ordered = [primary_spec, *[candidate for candidate in candidates if candidate is not primary_spec]]
    unique_paths: set[str] = set()
    unique_candidates = [
        candidate
        for candidate in ordered
        if not (candidate["path"] in unique_paths or unique_paths.add(candidate["path"]))
    ]
    bases = await get_bases()
    configured = {
        extract_command_name_from_base(base): bool(base.get("online"))
        for base in bases
        if extract_command_name_from_base(base)
    }
    online_candidates = [
        candidate for candidate in unique_candidates
        if configured.get(candidate["aliases"][0], True)
    ]
    return online_candidates or unique_candidates


async def configured_url_for_spec(spec: dict) -> str:
    bases = await get_bases()
    aliases = {normalize_command_name(alias) for alias in spec["aliases"]}
    for base in bases:
        command_name = extract_command_name_from_base(base)
        if command_name and normalize_command_name(command_name) in aliases:
            return base.get("url") or ""
    return ""


async def fetch_api_data_with_fallback(
    api_base_url: str,
    api_key: str,
    command_name: str,
    primary_spec: dict,
    value: str,
    status_message: Message,
) -> object:
    candidates = await fallback_specs_for(command_name, primary_spec)
    last_error: Exception | None = None

    for index, candidate in enumerate(candidates):
        try:
            return await fetch_api_data(
                api_base_url,
                api_key,
                candidate,
                value,
                await configured_url_for_spec(candidate),
                timeout=FALLBACK_TIMEOUT_SECONDS if index < len(candidates) - 1 else 60,
            )
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            last_error = error
            if index == len(candidates) - 1:
                break
            logger.warning(
                "Base lenta ou indisponível | comando=/%s | tentativa=/%s | próximo=/%s | erro=%s",
                command_name,
                candidate["aliases"][0],
                candidates[index + 1]["aliases"][0],
                error,
            )
            try:
                await status_message.edit_text("⏳ A consulta está demorando. Tentando outra base automaticamente...")
            except TelegramBadRequest:
                pass

    if last_error:
        raise last_error
    raise TimeoutError("Nenhuma base de consulta disponível.")


async def fetch_chassi_data(api_base_url: str, api_key: str, chassi: str) -> object:
    url = build_chassi_url(api_base_url, api_key, chassi)

    def _request() -> object:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
        data = parse_api_response(body)
        if is_html_error_response(data):
            raise ValueError("A base retornou uma página HTML de erro.")
        return data

    return await asyncio.to_thread(_request)


# -----------------------------------------------------------------------------
# Botões e estados do painel
# -----------------------------------------------------------------------------

def keyboard_rows(buttons: list[InlineKeyboardButton], columns: int = 2) -> list[list[InlineKeyboardButton]]:
    return [buttons[index:index + columns] for index in range(0, len(buttons), columns)]


def main_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📌 Conteúdo e vitrine", callback_data="admin:section_content")],
            [
                InlineKeyboardButton(text="🎨 Start", callback_data="admin:start_menu"),
                InlineKeyboardButton(text="🗂 Bases", callback_data="admin:bases"),
            ],
            [
                InlineKeyboardButton(text="📢 Broadcast", callback_data="admin:broadcast"),
                InlineKeyboardButton(text="👋 Boas-vindas", callback_data="admin:welcome"),
            ],
            [InlineKeyboardButton(text="💰 Planos e pagamentos", callback_data="admin:section_sales")],
            [
                InlineKeyboardButton(text="📦 Planos", callback_data="admin:plans"),
                InlineKeyboardButton(text="💳 MisticPay", callback_data="admin:misticpay"),
            ],
            [InlineKeyboardButton(text="⚙️ Sistema", callback_data="admin:section_system")],
            [InlineKeyboardButton(text="🔑 API", callback_data="admin:api")],
        ]
    )


def start_keyboard(has_photo: bool) -> InlineKeyboardMarkup:
    action_buttons = [
        InlineKeyboardButton(text="✏️ Texto", callback_data="admin:text"),
        InlineKeyboardButton(text="🖼 Imagem", callback_data="admin:photo"),
        InlineKeyboardButton(text="🔘 Botões", callback_data="admin:buttons"),
        InlineKeyboardButton(text="👁 Prévia", callback_data="admin:preview"),
        InlineKeyboardButton(text="❓ HTML", callback_data="admin:help"),
    ]

    buttons = keyboard_rows(action_buttons, 2)
    if has_photo:
        buttons.append([InlineKeyboardButton(text="🗑 Remover imagem", callback_data="admin:remove")])

    buttons.append([InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:back")])
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
        if WEB_RESULTS_URL:
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


def private_result_keyboard(user_id: int, command_message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🗑 Deletar resultado",
            callback_data=f"result:delete:{user_id}:{command_message_id}",
        )
    ]])


def api_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🌐 Base URL", callback_data="admin:api_base"),
                InlineKeyboardButton(text="🔐 Key/token", callback_data="admin:api_key"),
            ],
            [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:back")],
        ],
    )


def misticpay_admin_keyboard(force_join_enabled: bool = False) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Gateway de pagamento", callback_data="admin:section_payment")],
            [
                InlineKeyboardButton(text="🔑 URL", callback_data="admin:mp_url"),
                InlineKeyboardButton(text="🆔 Client ID", callback_data="admin:mp_client_id"),
            ],
            [InlineKeyboardButton(text="🧾 Client Secret", callback_data="admin:mp_client_secret")],
            [InlineKeyboardButton(text="📣 Canais e entrada", callback_data="admin:section_channels")],
            [
                InlineKeyboardButton(text="📣 Canal/grupo", callback_data="admin:mp_ref_channel"),
                InlineKeyboardButton(text="📜 Logs", callback_data="admin:mp_logs_channel"),
            ],
            [InlineKeyboardButton(
                text=f"{'🟢' if force_join_enabled else '🔴'} Entrada obrigatória",
                callback_data="admin:force_join_toggle",
            )],
            [InlineKeyboardButton(text="👤 Aviso de novo usuário", callback_data="admin:new_user_reference")],
            [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:back")],
        ]
    )


def plans_admin_keyboard(plans: list[tuple[int, str, str, int, float, int]]) -> InlineKeyboardMarkup:
    private_plans = [plan for plan in plans if plan[2] == "user"]
    group_plans = [plan for plan in plans if plan[2] == "group"]
    rows: list[list[InlineKeyboardButton]] = []

    def add_section(title: str, section_plans: list[tuple[int, str, str, int, float, int]]) -> None:
        if not section_plans:
            return
        rows.append([InlineKeyboardButton(text=title, callback_data="admin:plans_header")])
        plan_buttons = []
        for plan in section_plans:
            status = "🟢" if plan[5] else "🔴"
            name = plan[1][:18] + ("…" if len(plan[1]) > 18 else "")
            plan_buttons.append(InlineKeyboardButton(
                text=f"{status} {name} • {plan[3]}d",
                callback_data=f"admin:plan:{plan[0]}",
            ))
        rows.extend(keyboard_rows(plan_buttons, 2))

    add_section("🔐 PLANOS PRIVADOS", private_plans)
    add_section("👥 PLANOS DE GRUPO", group_plans)
    if not plans:
        rows.append([InlineKeyboardButton(text="📭 Nenhum plano cadastrado", callback_data="admin:plans_header")])
    rows.extend([
        [InlineKeyboardButton(text="⚙️ Ações", callback_data="admin:plans_header")],
        [
            InlineKeyboardButton(text="➕ Criar", callback_data="admin:plan_create"),
            InlineKeyboardButton(text="🎯 Liberar", callback_data="admin:plan_grant"),
        ],
        [InlineKeyboardButton(text="👥 Acessos ativos", callback_data="admin:subscriptions")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:back")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plan_editor_keyboard(plan: tuple[int, str, str, int, float, int]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏱ Alterar tempo", callback_data=f"admin:plan_duration:{plan[0]}"),
            InlineKeyboardButton(text="💰 Alterar valor", callback_data=f"admin:plan_price:{plan[0]}"),
        ],
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
            text=f"💳 {plan[1]} • {plan[3]} dias • R$ {plan[4]:.2f}",
            callback_data=f"plan:buy:{plan[0]}",
        )]
        for plan in plans
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
    waiting_base_name = State()
    waiting_base_command = State()
    waiting_base_param = State()
    waiting_base_url = State()
    waiting_misticpay_url = State()
    waiting_misticpay_client_id = State()
    waiting_misticpay_client_secret = State()
    waiting_reference_channel = State()
    waiting_logs_channel = State()
    waiting_plan_create = State()
    waiting_plan_grant = State()
    waiting_plan_duration = State()
    waiting_plan_price = State()
    waiting_broadcast_text = State()
    waiting_group_welcome_text = State()
    waiting_group_welcome_photo = State()
    waiting_new_user_reference_text = State()
    waiting_new_user_reference_photo = State()
    waiting_new_user_reference_button_text = State()
    waiting_new_user_reference_button_url = State()


def public_buttons_keyboard(buttons: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for row_number in sorted({int(button.get("row", 0)) for button in buttons}):
        row = []
        for index, button in enumerate(buttons):
            if int(button.get("row", 0)) != row_number:
                continue
            is_bases_webapp = button.get("action") == "bases" and bool(WEB_RESULTS_URL)
            is_plans_webapp = button.get("action") == "plans" and bool(WEB_RESULTS_URL)
            data = {
                "text": format_button_text(button.get("text", "Botão")),
                "url": (
                    None if is_bases_webapp or is_plans_webapp else button.get("url") or None
                ),
                "web_app": (
                    WebAppInfo(url=f"{WEB_RESULTS_URL}/bases") if is_bases_webapp else
                    WebAppInfo(url=f"{WEB_RESULTS_URL}/planos") if is_plans_webapp else
                    None
                ),
                "callback_data": (
                    None if button.get("url") else
                    None if is_bases_webapp else
                    None if is_plans_webapp else
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
    button_rows = keyboard_rows([
        InlineKeyboardButton(text=f"{i + 1}. {button.get('text', 'Botão')[:16]}", callback_data=f"admin:button:{i}")
        for i, button in enumerate(buttons)
    ], 2)
    rows = button_rows
    rows.extend([
        [
            InlineKeyboardButton(text="▦ Organização", callback_data="admin:layout"),
            InlineKeyboardButton(text="👁 Prévia", callback_data="admin:preview"),
        ],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:start_menu")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def button_editor_keyboard(index: int, button: dict) -> InlineKeyboardMarkup:
    colors = {"primary": "azul", "success": "verde", "danger": "vermelho", "": "padrão"}
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Texto", callback_data=f"admin:btext:{index}"),
            InlineKeyboardButton(text="🔗 Link", callback_data=f"admin:burl:{index}"),
        ],
        [
            InlineKeyboardButton(text="✨ Emoji", callback_data=f"admin:bemoji:{index}"),
            InlineKeyboardButton(text=f"🎨 {colors.get(button.get('style', ''), 'padrão')}", callback_data=f"admin:bstyle:{index}"),
        ],
        [InlineKeyboardButton(text="⬆️ Mover", callback_data=f"admin:bmove:{index}:-1"), InlineKeyboardButton(text="⬇️ Mover", callback_data=f"admin:bmove:{index}:1")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:buttons")],
    ])


def bases_keyboard(bases: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=f"{strip_custom_emoji_tags(base['name'])} {'🟢' if base['online'] else '🔴'}",
            callback_data=f"bases:category:{index}",
            style="success" if base["online"] else "danger",
        )
        for index, base in enumerate(bases)
    ]
    rows = [buttons[index:index + 2] for index in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="✖️ Fechar", callback_data="bases:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def group_welcome_keyboard(enabled: bool, photo_configured: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔴 Desativar" if enabled else "🟢 Ativar",
            callback_data="admin:welcome_toggle",
        )],
        [
            InlineKeyboardButton(text="✏️ Texto", callback_data="admin:welcome_text"),
            InlineKeyboardButton(
                text="🗑 Imagem" if photo_configured else "🖼 Imagem",
                callback_data="admin:welcome_photo",
            ),
        ],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:back")],
    ])


def bases_admin_keyboard(bases: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=f"{strip_custom_emoji_tags(base['name'])} {'🟢' if base['online'] else '🔴'}",
            callback_data=f"admin:base:{index}",
            style="success" if base["online"] else "danger",
        )
        for index, base in enumerate(bases)
    ]
    rows = [buttons[index:index + 2] for index in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="➕ Adicionar base", callback_data="admin:base_add")])
    rows.append([InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:base_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def base_editor_keyboard(index: int, base: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔴 Desativar" if base.get("online") else "🟢 Ativar",
            callback_data=f"admin:base_toggle:{index}",
        )],
        [InlineKeyboardButton(text="✏️ Alterar nome", callback_data=f"admin:base_name:{index}")],
        [InlineKeyboardButton(text="⌨️ Alterar comando", callback_data=f"admin:base_command:{index}")],
        [InlineKeyboardButton(text="🏷 Alterar variável", callback_data=f"admin:base_param:{index}")],
        [InlineKeyboardButton(text="🔗 Alterar URL", callback_data=f"admin:base_url:{index}")],
        [InlineKeyboardButton(text="🗑 Excluir base", callback_data=f"admin:base_delete:{index}")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:bases")],
    ])


def render_base_editor_text(base: dict) -> str:
    command = extract_command_name_from_base(base) or "não configurado"
    spec = build_base_command_spec(base, command) or API_COMMAND_LOOKUP.get(command)
    param = (base.get("param") or (spec or {}).get("param") or "não configurada")
    return (
        "<b>🗂 Editar base</b>\n\n"
        f"Nome: {render_custom_emoji_text(base.get('name', 'Base'))}\n"
        f"Comando: <code>/{html.escape(command)}</code>\n"
        f"Variável: <code>{html.escape(param)}</code>\n"
        f"Status: <code>{'online' if base.get('online') else 'offline'}</code>\n"
        f"URL: <code>{html.escape(base.get('url') or 'não configurada')}</code>\n\n"
        f"{format_base_usage(base)}"
    )


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
        buttons.append([InlineKeyboardButton(text="📣 Entrar (canal do bot)", url=f"https://t.me/{channel[1:]}")])
    buttons.append([InlineKeyboardButton(text="✅ Já entrei", callback_data="required:check")])
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
        "⚠️ Para usar este bot, você precisa entrar no canal/grupo obrigatório: "
        f"<b>{html.escape(channel or 'não configurado')}</b>\n\n"
        "Depois de entrar, toque em <b>Já entrei</b>.",
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


async def delete_command_message_now(message: Message) -> None:
    if is_private_chat(message.chat):
        return
    try:
        await message.bot.delete_message(message.chat.id, message.message_id)
    except TelegramBadRequest:
        pass


async def delete_last_bot_message(bot: Bot, chat_id: int) -> None:
    message_id = LAST_BOT_MESSAGE_BY_CHAT.pop(chat_id, None)
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramBadRequest:
        pass


def remember_last_bot_message(message: Message) -> None:
    LAST_BOT_MESSAGE_BY_CHAT[message.chat.id] = message.message_id


async def send_start(bot: Bot, chat_id: int, user) -> None:
    text, photo_file_id = await get_settings()
    buttons = await get_buttons()
    rendered = render_variables(text, user)
    reply_markup = public_buttons_keyboard(buttons)

    await delete_last_bot_message(bot, chat_id)
    if photo_file_id:
        sent_message = await bot.send_photo(
            chat_id=chat_id,
            photo=photo_file_id,
            caption=rendered,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
    else:
        sent_message = await bot.send_message(
            chat_id=chat_id,
            text=rendered,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
    remember_last_bot_message(sent_message)


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    is_new_user = await register_user(message)
    await delete_command_message_now(message)
    if is_new_user:
        await notify_new_user_reference(message.bot, message.from_user)
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("result_"):
        delivery = await get_private_result_delivery(parts[1][7:], message.from_user.id)
        if not delivery:
            await message.answer("⏳ Este resultado expirou ou não pertence a você. Faça uma nova consulta.")
            return
        result_text, photo = delivery
        private_keyboard = private_result_keyboard(message.from_user.id, message.message_id)
        if photo:
            await message.answer_photo(
                BufferedInputFile(photo, filename="foto-consulta.jpg"),
                caption="📷 Foto encontrada na consulta.",
                reply_markup=private_keyboard,
            )
        if len(result_text) <= 3900:
            await message.answer(
                f"<pre>{html.escape(result_text)}</pre>",
                reply_markup=private_keyboard,
            )
        else:
            await message.answer_document(
                BufferedInputFile(result_text.encode("utf-8"), filename="resultado-privado.txt"),
                caption="📄 Seu resultado foi enviado em arquivo.",
                reply_markup=private_keyboard,
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


@router.callback_query(F.data.startswith("admin:section_"))
async def admin_section_header_handler(query: CallbackQuery) -> None:
    await query.answer("Categoria do painel.")


@router.callback_query(F.data.startswith("start:button:"))
async def unconfigured_start_button_handler(query: CallbackQuery) -> None:
    await query.answer("Este botão ainda não tem um link. Configure-o no /admin.", show_alert=True)


@router.message(F.new_chat_members)
async def group_new_members_handler(message: Message) -> None:
    enabled, text, photo = await get_group_welcome_settings()
    if not enabled:
        return

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    for user in message.new_chat_members:
        if getattr(user, "is_bot", False):
            continue
        rendered = render_group_welcome(text, user, message.chat)
        try:
            if photo:
                await message.answer_photo(photo, caption=rendered, parse_mode=ParseMode.HTML)
            else:
                await message.answer(rendered, parse_mode=ParseMode.HTML)
        except TelegramBadRequest:
            logger.exception("Falha ao enviar boas-vindas no chat %s", message.chat.id)


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
    section_title = "🔐 Planos privados" if category == "user" else "👥 Planos para este grupo"
    context_hint = "Este acesso funciona no seu chat privado com o bot." if category == "user" else "Este acesso será liberado para este grupo após a confirmação do PIX."
    text = [f"<b>📦 {section_title}</b>", "", context_hint, "", "Escolha um plano para gerar seu PIX:"]
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
            "⚠️ Para comprar um plano, entre primeiro no canal/grupo obrigatório e toque em <b>Já entrei</b>.",
            reply_markup=required_channel_keyboard(channel),
        )
        return await query.answer("Entre no canal/grupo obrigatório primeiro.", show_alert=True)
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
        "Escolha uma área para configurar. Os botões estão separados por função:",
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
        "Adicione, edite comandos, URLs e status das bases.",
        reply_markup=bases_admin_keyboard(bases),
    )
    await query.answer()


@router.callback_query(F.data == "admin:base_add")
async def admin_base_add_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    bases = await get_bases()
    next_number = len(bases) + 1
    while any(extract_command_name_from_base(base) == f"base{next_number}" for base in bases):
        next_number += 1
    bases.append({
        "name": f"Nova base {next_number}",
        "online": False,
        "url": "",
        "command": f"base{next_number}",
        "param": "valor",
        "example": "VALOR",
    })
    await save_bases(bases)
    index = len(bases) - 1
    await state.clear()
    await query.message.edit_text(
        "✅ Base criada. Agora escolha nos botões o que deseja alterar.\n\n"
        f"{render_base_editor_text(bases[index])}",
        reply_markup=base_editor_keyboard(index, bases[index]),
    )
    await query.answer("Base criada.")


@router.callback_query(F.data.regexp(r"^admin:base:\d+$"))
async def admin_base_editor_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.clear()
    index = int(query.data.rsplit(":", 1)[1])
    bases = await get_bases()
    if not 0 <= index < len(bases):
        return await query.answer("Base não encontrada.", show_alert=True)

    base = bases[index]
    await query.message.edit_text(
        render_base_editor_text(base),
        reply_markup=base_editor_keyboard(index, base),
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
    base = bases[index]
    await query.message.edit_text(
        render_base_editor_text(base),
        reply_markup=base_editor_keyboard(index, base),
    )
    await query.answer("Status atualizado.")


async def ask_base_field(query: CallbackQuery, state: FSMContext, index: int, field: str, prompt: str) -> None:
    bases = await get_bases()
    if not 0 <= index < len(bases):
        return await query.answer("Base não encontrada.", show_alert=True)
    await state.update_data(base_index=index)
    state_map = {
        "name": AdminState.waiting_base_name,
        "command": AdminState.waiting_base_command,
        "param": AdminState.waiting_base_param,
        "url": AdminState.waiting_base_url,
    }
    await state.set_state(state_map[field])
    await query.message.answer(prompt, reply_markup=cancel_keyboard())
    await query.answer()


@router.callback_query(F.data.startswith("admin:base_name:"))
async def admin_base_name_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    index = int(query.data.rsplit(":", 1)[1])
    await ask_base_field(query, state, index, "name", "Envie apenas o novo nome da base.")


@router.message(AdminState.waiting_base_name, F.text)
async def receive_base_name_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    index = int(data.get("base_index", -1))
    bases = await get_bases()
    if not 0 <= index < len(bases):
        await state.clear()
        return await message.answer("❌ Base não encontrada.")
    name = text_with_custom_emoji_tags(message).strip()
    if not name:
        return await message.answer("❌ O nome não pode ficar vazio.", reply_markup=cancel_keyboard())
    emoji_error = validate_custom_emoji_html(name)
    if emoji_error:
        return await message.answer(f"❌ {html.escape(emoji_error)}", reply_markup=cancel_keyboard())
    bases[index]["name"] = name
    await save_bases(bases)
    await state.clear()
    await message.answer("✅ Nome da base salvo.", reply_markup=base_editor_keyboard(index, bases[index]))


@router.callback_query(F.data.startswith("admin:base_command:"))
async def admin_base_command_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    index = int(query.data.rsplit(":", 1)[1])
    await ask_base_field(
        query,
        state,
        index,
        "command",
        "Envie apenas o novo comando, sem barra.\n\nExemplo: <code>nomevip</code>",
    )


@router.message(AdminState.waiting_base_command, F.text)
async def receive_base_command_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    index = int(data.get("base_index", -1))
    bases = await get_bases()
    if not 0 <= index < len(bases):
        await state.clear()
        return await message.answer("❌ Base não encontrada.")
    command = normalize_command_name(message.text)
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]{1,31}$", command):
        return await message.answer("❌ Comando inválido. Use letras, números ou _.", reply_markup=cancel_keyboard())
    if any(i != index and extract_command_name_from_base(base) == command for i, base in enumerate(bases)):
        return await message.answer("❌ Já existe uma base usando esse comando.", reply_markup=cancel_keyboard())
    bases[index]["command"] = command
    await save_bases(bases)
    await state.clear()
    await message.answer("✅ Comando da base salvo.", reply_markup=base_editor_keyboard(index, bases[index]))


@router.callback_query(F.data.startswith("admin:base_param:"))
async def admin_base_param_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    index = int(query.data.rsplit(":", 1)[1])
    await ask_base_field(
        query,
        state,
        index,
        "param",
        "Envie apenas o nome da variável/parâmetro.\n\nExemplo: <code>nome</code>, <code>cpf</code>, <code>placa</code>",
    )


@router.message(AdminState.waiting_base_param, F.text)
async def receive_base_param_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    index = int(data.get("base_index", -1))
    bases = await get_bases()
    if not 0 <= index < len(bases):
        await state.clear()
        return await message.answer("❌ Base não encontrada.")
    param = message.text.strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_-]*$", param):
        return await message.answer("❌ Variável inválida.", reply_markup=cancel_keyboard())
    bases[index]["param"] = param
    await save_bases(bases)
    await state.clear()
    await message.answer("✅ Variável da base salva.", reply_markup=base_editor_keyboard(index, bases[index]))


@router.callback_query(F.data.startswith("admin:base_url:"))
async def admin_base_url_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    index = int(query.data.rsplit(":", 1)[1])
    bases = await get_bases()
    if not 0 <= index < len(bases):
        return await query.answer("Base não encontrada.", show_alert=True)

    await state.set_state(AdminState.waiting_base_url)
    await state.update_data(base_index=index)
    base = bases[index]
    await query.message.answer(
        "<b>🔗 Alterar URL da base</b>\n\n"
        f"Base: {render_custom_emoji_text(base.get('name', 'Base'))}\n"
        f"URL atual: <code>{html.escape(base.get('url') or 'não configurada')}</code>\n\n"
        "Envie a nova URL completa ou relativa.\n"
        "Exemplo: <code>https://api.site.com/busca?nome={nome}</code>\n"
        "Também pode usar <code>{cpf}</code>, <code>{placa}</code>, <code>{telefone}</code> etc.\n\n"
        "Envie <code>remover</code> para limpar a URL desta base.",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_base_url, F.text)
async def receive_base_url_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    index = int(data.get("base_index", -1))
    bases = await get_bases()
    if not 0 <= index < len(bases):
        await state.clear()
        return await message.answer("❌ Base não encontrada. Abra o /admin novamente.")

    url = message.text.strip()
    if url.lower() == "remover":
        url = ""
    elif not (re.match(r"^https?://", url, re.IGNORECASE) or re.match(r"^[^\s]+$", url)):
        return await message.answer(
            "❌ Envie uma URL completa ou uma rota relativa sem espaços.",
            reply_markup=cancel_keyboard(),
        )

    bases[index]["url"] = url
    await save_bases(bases)
    await state.clear()
    await message.answer(
        "✅ URL da base salva com sucesso.\n\n"
        f"Base: {render_custom_emoji_text(bases[index].get('name', 'Base'))}\n"
        f"URL: <code>{html.escape(url or 'não configurada')}</code>",
        reply_markup=base_editor_keyboard(index, bases[index]),
    )


@router.callback_query(F.data.startswith("admin:base_delete:"))
async def admin_base_delete_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    index = int(query.data.rsplit(":", 1)[1])
    bases = await get_bases()
    if not 0 <= index < len(bases):
        return await query.answer("Base não encontrada.", show_alert=True)

    removed = bases.pop(index)
    await save_bases(bases)
    await query.message.edit_text(
        f"✅ Base removida: {render_custom_emoji_text(removed.get('name', 'Base'))}\n\n"
        "Lista atualizada:",
        reply_markup=bases_admin_keyboard(bases),
    )
    await query.answer("Base removida.")


@router.callback_query(F.data == "admin:base_back")
async def admin_base_back_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await query.message.edit_text(
        "<b>⚙️ Painel administrativo</b>\n\nEscolha uma área para configurar:",
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
        "Mensagem inicial, imagem e botões públicos do bot.",
        reply_markup=start_keyboard(bool(photo_file_id)),
    )
    await query.answer()


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_menu_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.set_state(AdminState.waiting_broadcast_text)
    total_users = len(await get_registered_users())
    await query.message.answer(
        "<b>📢 Broadcast</b>\n\n"
        f"Usuários cadastrados: <code>{total_users}</code>\n\n"
        "Envie a mensagem HTML que será enviada para todos os usuários cadastrados.\n"
        "Variáveis: <code>{ID}</code>, <code>{NAME}</code>, <code>{USERNAME}</code>, <code>{MENTION}</code>.",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_broadcast_text, F.text)
async def receive_broadcast_text(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    users = await get_registered_users()
    if not users:
        await state.clear()
        return await message.answer("❌ Nenhum usuário cadastrado no banco.")

    sent = 0
    failed = 0
    status = await message.answer(f"⏳ Enviando broadcast para <code>{len(users)}</code> usuários...")
    for user_data in users:
        try:
            fake_user = type("BroadcastUser", (), {
                "id": user_data["id"],
                "first_name": user_data["first_name"],
                "last_name": user_data["last_name"],
                "username": user_data["username"],
            })()
            text = render_group_welcome(message.text, fake_user, message.chat)
            await message.bot.send_message(user_data["id"], text, parse_mode=ParseMode.HTML)
            sent += 1
        except Exception:
            failed += 1
        if (sent + failed) % 25 == 0:
            await asyncio.sleep(1)

    await state.clear()
    await status.edit_text(
        "<b>📢 Broadcast concluído</b>\n\n"
        f"✅ Enviadas: <code>{sent}</code>\n"
        f"⚠️ Falhas: <code>{failed}</code>"
    )


@router.callback_query(F.data == "admin:welcome")
async def group_welcome_menu_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.clear()
    enabled, text, photo = await get_group_welcome_settings()
    await query.message.edit_text(
        "<b>👋 Boas-vindas em grupos</b>\n\n"
        f"Status: <code>{'Ativo' if enabled else 'Desativado'}</code>\n"
        f"Imagem: <code>{'configurada' if photo else 'não configurada'}</code>\n\n"
        "Quando ativo, o bot apaga a mensagem automática de entrada e envia uma saudação personalizada.\n\n"
        "Variáveis: <code>{MENTION}</code>, <code>{NAME}</code>, <code>{USERNAME}</code>, "
        "<code>{ID}</code>, <code>{CHAT_TITLE}</code>, <code>{GRUPO}</code>.",
        reply_markup=group_welcome_keyboard(enabled, bool(photo)),
    )
    await query.answer()


@router.callback_query(F.data == "admin:welcome_toggle")
async def group_welcome_toggle_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    enabled, text, photo = await get_group_welcome_settings()
    await save_group_welcome_settings(not enabled, text, photo)
    await query.message.edit_reply_markup(reply_markup=group_welcome_keyboard(not enabled, bool(photo)))
    await query.answer("Boas-vindas atualizadas.")


@router.callback_query(F.data == "admin:welcome_text")
async def group_welcome_text_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.set_state(AdminState.waiting_group_welcome_text)
    await query.message.answer(
        "Envie o novo texto HTML das boas-vindas.\n\n"
        "Variáveis: <code>{MENTION}</code>, <code>{NAME}</code>, <code>{USERNAME}</code>, "
        "<code>{ID}</code>, <code>{CHAT_TITLE}</code>, <code>{GRUPO}</code>.",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_group_welcome_text, F.text)
async def receive_group_welcome_text(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    enabled, _, photo = await get_group_welcome_settings()
    error = validate_start_text(message.text, bool(photo))
    if error:
        return await message.answer(f"❌ {html.escape(error)}", reply_markup=cancel_keyboard())
    await save_group_welcome_settings(enabled, message.text, photo)
    await state.clear()
    await message.answer("✅ Texto de boas-vindas salvo.", reply_markup=group_welcome_keyboard(enabled, bool(photo)))


@router.callback_query(F.data == "admin:welcome_photo")
async def group_welcome_photo_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    enabled, text, photo = await get_group_welcome_settings()
    if photo:
        await save_group_welcome_settings(enabled, text, None)
        await query.message.edit_reply_markup(reply_markup=group_welcome_keyboard(enabled, False))
        return await query.answer("Imagem removida.")

    await state.set_state(AdminState.waiting_group_welcome_photo)
    await query.message.answer("Envie a imagem das boas-vindas como foto.", reply_markup=cancel_keyboard())
    await query.answer()


@router.message(AdminState.waiting_group_welcome_photo, F.photo)
async def receive_group_welcome_photo(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    enabled, text, _ = await get_group_welcome_settings()
    error = validate_start_text(text, True)
    if error:
        return await message.answer(f"❌ O texto atual não cabe com imagem: {html.escape(error)}", reply_markup=cancel_keyboard())
    await save_group_welcome_settings(enabled, text, message.photo[-1].file_id)
    await state.clear()
    await message.answer("✅ Imagem de boas-vindas salva.", reply_markup=group_welcome_keyboard(enabled, True))


@router.callback_query(F.data == "admin:back")
async def back_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)

    await state.clear()
    await query.message.edit_text(
        "<b>⚙️ Painel administrativo</b>\n\n"
        "Escolha uma área para configurar:",
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
    private_count = sum(plan[2] == "user" for plan in plans)
    group_count = sum(plan[2] == "group" for plan in plans)
    await query.message.edit_text(
        "<b>📦 Central de planos</b>\n\n"
        f"🔐 <b>Privados:</b> <code>{private_count}</code>\n"
        f"👥 <b>Grupos:</b> <code>{group_count}</code>\n\n"
        "Planos privados podem ser comprados no bot. Planos de grupo são destinados ao chat e podem ser liberados pelo ID.",
        reply_markup=plans_admin_keyboard(plans),
    )
    await query.answer()


@router.callback_query(F.data == "admin:plans_header")
async def admin_plans_header_handler(query: CallbackQuery) -> None:
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
        "Envie um plano por linha para criar vários de uma vez.\n\n"
        "Exemplo: <code>Mensal | plano | 30 | 19.90</code>",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_plan_create, F.text)
async def receive_plan_create_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    lines = [line.strip() for line in message.text.splitlines() if line.strip()]
    if not 1 <= len(lines) <= 20:
        return await message.answer("❌ Envie de 1 até 20 planos, um por linha.", reply_markup=cancel_keyboard())

    plans_to_create: list[tuple[str, str, int, float]] = []
    for line_number, line in enumerate(lines, start=1):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 4:
            return await message.answer(f"❌ Linha {line_number}: use <code>Nome | plano ou grupo | dias | valor</code>", reply_markup=cancel_keyboard())
        name, category_text, days_text, price_text = parts
        category = "user" if category_text.lower() in {"plano", "privado", "publico", "público", "user", "usuario", "usuário"} else "group" if category_text.lower() in {"grupo", "group"} else ""
        try:
            duration_days = int(days_text)
            price = float(price_text.replace(",", "."))
        except ValueError:
            return await message.answer(f"❌ Linha {line_number}: dias e valor precisam ser números válidos.", reply_markup=cancel_keyboard())
        if not name or not category or duration_days <= 0 or price <= 0:
            return await message.answer(f"❌ Linha {line_number}: informe nome, tipo válido, dias e valor maiores que zero.", reply_markup=cancel_keyboard())
        plans_to_create.append((name, category, duration_days, price))

    for name, category, duration_days, price in plans_to_create:
        await create_plan(name, category, duration_days, price)
    await state.clear()
    await message.answer(f"✅ {len(plans_to_create)} plano(s) criado(s).", reply_markup=plans_admin_keyboard(await get_plans()))


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


@router.callback_query(F.data.startswith("admin:plan_duration:"))
async def admin_plan_duration_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    plan = await get_plan(int(query.data.rsplit(":", 1)[1]))
    if not plan:
        return await query.answer("Plano não encontrado.", show_alert=True)
    await state.update_data(edit_plan_id=plan[0])
    await state.set_state(AdminState.waiting_plan_duration)
    await query.message.answer(
        f"Envie o novo tempo para <b>{html.escape(plan[1])}</b> em dias.\n\n"
        f"Atual: <code>{plan[3]} dias</code>",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_plan_duration, F.text)
async def receive_plan_duration_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    try:
        duration_days = int(message.text.strip())
    except ValueError:
        return await message.answer("❌ Envie apenas a quantidade de dias.", reply_markup=cancel_keyboard())
    if duration_days <= 0:
        return await message.answer("❌ O tempo precisa ser maior que zero.", reply_markup=cancel_keyboard())
    plan_id = (await state.get_data())["edit_plan_id"]
    await update_plan_duration(plan_id, duration_days)
    await state.clear()
    await message.answer("✅ Tempo atualizado.", reply_markup=plans_admin_keyboard(await get_plans()))


@router.callback_query(F.data.startswith("admin:plan_price:"))
async def admin_plan_price_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    plan = await get_plan(int(query.data.rsplit(":", 1)[1]))
    if not plan:
        return await query.answer("Plano não encontrado.", show_alert=True)
    await state.update_data(edit_plan_id=plan[0])
    await state.set_state(AdminState.waiting_plan_price)
    await query.message.answer(
        f"Envie o novo valor para <b>{html.escape(plan[1])}</b>.\n\n"
        f"Atual: <code>R$ {plan[4]:.2f}</code>",
        reply_markup=cancel_keyboard(),
    )
    await query.answer()


@router.message(AdminState.waiting_plan_price, F.text)
async def receive_plan_price_handler(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    try:
        price = float(message.text.strip().replace(",", "."))
    except ValueError:
        return await message.answer("❌ Envie apenas um valor numérico.", reply_markup=cancel_keyboard())
    if price <= 0:
        return await message.answer("❌ O valor precisa ser maior que zero.", reply_markup=cancel_keyboard())
    plan_id = (await state.get_data())["edit_plan_id"]
    await update_plan_price(plan_id, price)
    await state.clear()
    await message.answer("✅ Valor atualizado.", reply_markup=plans_admin_keyboard(await get_plans()))


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
        f"Canal/grupo obrigatório: <code>{html.escape(ref_channel or 'não configurado')}</code>\n"
        f"Entrada obrigatória: <code>{'Ativo' if force_join_enabled else 'Desativado'}</code>\n"
        f"Canal logs: <code>{html.escape(logs_channel or 'não configurado')}</code>\n\n"
        "Configure pagamentos, canal/grupo obrigatório e acompanhe as transações.",
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
        "Envie o canal ou grupo obrigatório.\n\n"
        "Aceita <code>@canal</code>, <code>https://t.me/canal</code> ou ID numérico.\n"
        "Para funcionar, deixe o bot como admin no canal/grupo.",
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
    _, enabled = await get_force_join_settings()
    await message.answer("✅ Canal/grupo obrigatório salvo.", reply_markup=misticpay_admin_keyboard(enabled))


@router.callback_query(F.data == "admin:force_join_toggle")
async def force_join_toggle_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    channel, enabled = await get_force_join_settings()
    if not channel:
        return await query.answer("Defina primeiro o canal/grupo obrigatório.", show_alert=True)
    await set_force_join_enabled(not enabled)
    misticpay_url, client_id, client_secret, ref_channel, logs_channel = await get_misticpay_settings()
    await query.answer("Obrigatoriedade atualizada.")
    await query.message.edit_text(
        "<b>💳 MisticPay</b>\n\n"
        f"URL atual: <code>{html.escape(misticpay_url)}</code>\n"
        f"Client ID: <code>{html.escape(client_id or 'não configurado')}</code>\n"
        f"Client Secret: <code>{html.escape('•' * min(len(client_secret), 12) if client_secret else 'não configurado')}</code>\n"
        f"Canal/grupo obrigatório: <code>{html.escape(ref_channel or 'não configurado')}</code>\n"
        f"Entrada obrigatória: <code>{'Ativo' if not enabled else 'Desativado'}</code>\n"
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


def new_user_reference_keyboard(photo_configured: bool, button_color: str) -> InlineKeyboardMarkup:
    photo_label = "🗑 Remover imagem" if photo_configured else "🖼 Definir imagem"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Texto", callback_data="admin:new_user_ref_text"),
            InlineKeyboardButton(text=photo_label, callback_data="admin:new_user_ref_photo"),
        ],
        [
            InlineKeyboardButton(text="🔘 Botão", callback_data="admin:new_user_ref_button_text"),
            InlineKeyboardButton(text="🔗 Link", callback_data="admin:new_user_ref_button_url"),
        ],
        [InlineKeyboardButton(text=f"{button_color} Cor", callback_data="admin:new_user_ref_button_color")],
        [InlineKeyboardButton(text="⬅️ Voltar", callback_data="admin:misticpay")],
    ])


@router.callback_query(F.data == "admin:new_user_reference")
async def new_user_reference_menu_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.clear()
    text, photo, button_text, button_url, button_color = await get_new_user_reference_settings()
    await query.message.edit_text(
        "<b>👤 Aviso de novo usuário</b>\n\n"
        "Este aviso é enviado ao canal de referência quando alguém usa <code>/start</code> pela primeira vez.\n\n"
        f"Imagem: <code>{'configurada' if photo else 'não configurada'}</code>\n"
        f"Botão: <code>{html.escape(button_text)}</code>\n"
        f"Link: <code>{html.escape(button_url or 'não configurado')}</code>\n"
        f"Cor visual: <code>{button_color}</code>\n\n"
        "Tags: <code>{ID}</code>, <code>{NAME}</code>, <code>{SURNAME}</code>, <code>{NAMESURNAME}</code>, "
        "<code>{LANG}</code>, <code>{DATE}</code>, <code>{TIME}</code>, <code>{WEEKDAY}</code>, "
        "<code>{MENTION}</code>, <code>{USERNAME}</code>.",
        reply_markup=new_user_reference_keyboard(bool(photo), button_color),
    )
    await query.answer()


@router.callback_query(F.data == "admin:new_user_ref_text")
async def new_user_reference_text_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.set_state(AdminState.waiting_new_user_reference_text)
    await query.message.answer("Envie o texto HTML do aviso. Use as tags exibidas no menu.", reply_markup=cancel_keyboard())
    await query.answer()


@router.message(AdminState.waiting_new_user_reference_text, F.text)
async def receive_new_user_reference_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    _, photo, button_text, button_url, button_color = await get_new_user_reference_settings()
    limit = 1024 if photo else 4096
    if not text or visible_length(text) > limit:
        return await message.answer(f"❌ Informe um texto de até {limit} caracteres.", reply_markup=cancel_keyboard())
    await save_new_user_reference_settings(text, photo, button_text, button_url, button_color)
    await state.clear()
    await message.answer("✅ Texto do aviso salvo.", reply_markup=new_user_reference_keyboard(bool(photo), button_color))


@router.callback_query(F.data == "admin:new_user_ref_photo")
async def new_user_reference_photo_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    _, photo, button_text, button_url, button_color = await get_new_user_reference_settings()
    if photo:
        text, _, _, _, _ = await get_new_user_reference_settings()
        await save_new_user_reference_settings(text, None, button_text, button_url, button_color)
        return await query.answer("Imagem removida.", show_alert=True)
    await state.set_state(AdminState.waiting_new_user_reference_photo)
    await query.message.answer("Envie a imagem do aviso de novo usuário.", reply_markup=cancel_keyboard())
    await query.answer()


@router.message(AdminState.waiting_new_user_reference_photo, F.photo)
async def receive_new_user_reference_photo(message: Message, state: FSMContext) -> None:
    text, _, button_text, button_url, button_color = await get_new_user_reference_settings()
    if visible_length(text) > 1024:
        return await message.answer("❌ O texto atual excede 1024 caracteres e não cabe com imagem.", reply_markup=cancel_keyboard())
    await save_new_user_reference_settings(text, message.photo[-1].file_id, button_text, button_url, button_color)
    await state.clear()
    await message.answer("✅ Imagem do aviso salva.", reply_markup=new_user_reference_keyboard(True, button_color))


@router.callback_query(F.data == "admin:new_user_ref_button_text")
async def new_user_reference_button_text_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.set_state(AdminState.waiting_new_user_reference_button_text)
    await query.message.answer("Envie o texto do botão, de 1 a 64 caracteres.", reply_markup=cancel_keyboard())
    await query.answer()


@router.message(AdminState.waiting_new_user_reference_button_text, F.text)
async def receive_new_user_reference_button_text(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if not 1 <= len(value) <= 64:
        return await message.answer("❌ Use entre 1 e 64 caracteres.", reply_markup=cancel_keyboard())
    text, photo, _, button_url, button_color = await get_new_user_reference_settings()
    await save_new_user_reference_settings(text, photo, value, button_url, button_color)
    await state.clear()
    await message.answer("✅ Texto do botão salvo.", reply_markup=new_user_reference_keyboard(bool(photo), button_color))


@router.callback_query(F.data == "admin:new_user_ref_button_url")
async def new_user_reference_button_url_handler(query: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    await state.set_state(AdminState.waiting_new_user_reference_button_url)
    await query.message.answer("Envie o link do botão com https:// ou tg://. Envie <code>remover</code> para ocultar o botão.", reply_markup=cancel_keyboard())
    await query.answer()


@router.message(AdminState.waiting_new_user_reference_button_url, F.text)
async def receive_new_user_reference_button_url(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if value.lower() == "remover":
        value = ""
    elif not re.match(r"^(https://|tg://)", value, re.IGNORECASE):
        return await message.answer("❌ O link deve começar com https:// ou tg://.", reply_markup=cancel_keyboard())
    text, photo, button_text, _, button_color = await get_new_user_reference_settings()
    await save_new_user_reference_settings(text, photo, button_text, value, button_color)
    await state.clear()
    await message.answer("✅ Link do botão salvo.", reply_markup=new_user_reference_keyboard(bool(photo), button_color))


@router.callback_query(F.data == "admin:new_user_ref_button_color")
async def new_user_reference_button_color_handler(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        return await query.answer("Sem permissão.", show_alert=True)
    text, photo, button_text, button_url, current = await get_new_user_reference_settings()
    color = REFERENCE_BUTTON_COLORS[(REFERENCE_BUTTON_COLORS.index(current) + 1) % len(REFERENCE_BUTTON_COLORS)]
    await save_new_user_reference_settings(text, photo, button_text, button_url, color)
    await query.message.edit_reply_markup(reply_markup=new_user_reference_keyboard(bool(photo), color))
    await query.answer("Cor visual alterada.")


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
    spec = await get_command_spec(command_name)
    if not spec:
        return
    await delete_command_message_now(message)

    if not await enforce_required_channel(message):
        return

    if not await has_active_access(message.chat.id, message.from_user.id, is_private_chat(message.chat)):
        await delete_last_bot_message(message.bot, message.chat.id)
        await send_inactive_access_message(message, command_name)
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

    await delete_last_bot_message(message.bot, message.chat.id)
    status_message = await message.answer("⏳ Processando sua consulta...")
    schedule_query_cleanup(message, status_message)
    try:
        data = await fetch_api_data_with_fallback(
            api_base_url,
            api_key,
            command_name,
            spec,
            value,
            status_message,
        )
    except urllib.error.HTTPError as error:
        detail = await asyncio.to_thread(error.read) if error.fp else b""
        body = detail.decode("utf-8", errors="replace") if detail else error.reason
        bot_me = await message.bot.get_me()
        parsed_body = parse_api_error_body(body)
        if error.code == 404:
            await send_error_log(message.bot, message, command_name, error.code, parsed_body)
            await status_message.edit_text(
                render_not_found_result(
                    spec["title"],
                    parsed_body,
                    message.from_user,
                    bot_me.username or "",
                ),
                reply_markup=result_keyboard(message.from_user.id, message.message_id),
            )
            remember_last_bot_message(status_message)
            return
        await send_error_log(message.bot, message, command_name, error.code, parsed_body)
        await status_message.edit_text(
            render_api_failure(spec["title"], error.code, message.from_user, bot_me.username or ""),
            reply_markup=result_keyboard(message.from_user.id, message.message_id),
        )
        remember_last_bot_message(status_message)
        return
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        await send_error_log(message.bot, message, command_name, 503, error)
        await status_message.edit_text(
            render_api_failure(spec["title"], 503, message.from_user, (await message.bot.get_me()).username or ""),
            reply_markup=result_keyboard(message.from_user.id, message.message_id),
        )
        remember_last_bot_message(status_message)
        return

    bot_me = await message.bot.get_me()
    result_text = render_api_result(spec["title"], data, message.from_user, bot_me.username or "")
    result_token = await create_result_delivery(
        message.from_user.id, result_text, extract_base64_photo(data)
    )
    result_message = await send_query_result(
        status_message,
        result_text,
        result_keyboard(message.from_user.id, message.message_id, result_token, bot_me.username or ""),
        query_result_filename(value),
        message.from_user,
        bot_me.username or "",
        delivery_only=bool(WEB_RESULTS_URL),
    )
    remember_last_bot_message(result_message)
    schedule_query_cleanup(message, result_message)


@router.message(Command("chassi"))
async def chassi_handler(message: Message) -> None:
    await delete_command_message_now(message)
    if not await enforce_required_channel(message):
        return
    if not await has_active_access(message.chat.id, message.from_user.id, is_private_chat(message.chat)):
        await delete_last_bot_message(message.bot, message.chat.id)
        await send_inactive_access_message(message, "chassi")
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

    await delete_last_bot_message(message.bot, message.chat.id)
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
            await send_error_log(message.bot, message, "chassi", error.code, parsed_body)
            await status_message.edit_text(
                render_not_found_result(
                    "Resultado do chassi",
                    parsed_body,
                    message.from_user,
                    bot_me.username or "",
                ),
                reply_markup=result_keyboard(message.from_user.id, message.message_id),
            )
            remember_last_bot_message(status_message)
            return
        await send_error_log(message.bot, message, "chassi", error.code, parsed_body)
        await status_message.edit_text(
            render_api_failure("Resultado do chassi", error.code, message.from_user, bot_me.username or ""),
            reply_markup=result_keyboard(message.from_user.id, message.message_id),
        )
        remember_last_bot_message(status_message)
        return
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        await send_error_log(message.bot, message, "chassi", 503, error)
        await status_message.edit_text(
            render_api_failure("Resultado do chassi", 503, message.from_user, (await message.bot.get_me()).username or ""),
            reply_markup=result_keyboard(message.from_user.id, message.message_id),
        )
        remember_last_bot_message(status_message)
        return

    bot_me = await message.bot.get_me()
    result_text = render_api_result("Resultado do chassi", data, message.from_user, bot_me.username or "")
    result_token = await create_result_delivery(
        message.from_user.id, result_text, extract_base64_photo(data)
    )
    result_message = await send_query_result(
        status_message,
        result_text,
        result_keyboard(message.from_user.id, message.message_id, result_token, bot_me.username or ""),
        query_result_filename(chassi),
        message.from_user,
        bot_me.username or "",
        delivery_only=bool(WEB_RESULTS_URL),
    )
    remember_last_bot_message(result_message)
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

async def run_bot() -> None:
    global BOT_USERNAME
    await setup_database()

    bot = Bot(
        BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    if not BOT_USERNAME:
        try:
            bot_me = await bot.get_me()
            BOT_USERNAME = bot_me.username or ""
        except TelegramBadRequest:
            BOT_USERNAME = ""
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


@web_app.on_event("startup")
async def start_bot_with_web_server() -> None:
    web_app.state.bot_task = asyncio.create_task(run_bot())


@web_app.on_event("shutdown")
async def stop_bot_with_web_server() -> None:
    task = getattr(web_app.state, "bot_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    uvicorn.run("main:web_app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
