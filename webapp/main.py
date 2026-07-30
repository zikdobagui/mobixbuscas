import hmac
import os
import sqlite3

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


RESULTS_API_SECRET = os.getenv("RESULTS_API_SECRET", "").strip()
DB_PATH = os.getenv("WEB_DB_PATH", "web_results.db")

app = FastAPI()


class ResultPayload(BaseModel):
    token: str
    user_id: int
    result_text: str
    expires_at: str


def database() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def setup_database() -> None:
    with database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS results (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                result_text TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


@app.on_event("startup")
def startup() -> None:
    setup_database()


@app.post("/api/results")
def store_result(payload: ResultPayload, x_results_secret: str = Header(default="")) -> dict:
    if not RESULTS_API_SECRET or not hmac.compare_digest(x_results_secret, RESULTS_API_SECRET):
        raise HTTPException(status_code=401, detail="Sem permissão.")
    with database() as connection:
        connection.execute("DELETE FROM results WHERE expires_at <= CURRENT_TIMESTAMP")
        connection.execute(
            """
            INSERT INTO results (token, user_id, result_text, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
                user_id = excluded.user_id,
                result_text = excluded.result_text,
                expires_at = excluded.expires_at
            """,
            (payload.token, payload.user_id, payload.result_text, payload.expires_at),
        )
    return {"ok": True}


@app.get("/api/results/{token}")
def view_result(token: str) -> dict:
    with database() as connection:
        row = connection.execute(
            "SELECT result_text, expires_at FROM results WHERE token = ? AND expires_at > CURRENT_TIMESTAMP",
            (token,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Resultado expirado ou indisponível.")
    return {"result": row["result_text"], "expires_at": row["expires_at"]}


@app.get("/", response_class=HTMLResponse)
@app.get("/r/{token}", response_class=HTMLResponse)
def page(token: str = "") -> str:
    return """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Resultado da consulta</title>
<style>body{margin:0;background:#0d1824;color:#e8eef5;font:16px system-ui;padding:24px}main{max-width:760px;margin:auto;background:#162638;padding:24px;border-radius:16px}pre{white-space:pre-wrap;word-break:break-word;font:14px ui-monospace,monospace;color:#d7e4ef}#error{color:#ff9d9d}</style>
</head><body><main><h2>Resultado da consulta</h2><p id="status">Validando acesso...</p><pre id="result"></pre><p id="error"></p></main>
<script>
const token=location.pathname.split('/').pop();
fetch('/api/results/'+encodeURIComponent(token))
.then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.detail||'Resultado indisponível.');document.querySelector('#status').textContent='Resultado disponível até '+d.expires_at;document.querySelector('#result').textContent=d.result;})
.catch(e=>{document.querySelector('#status').textContent='';document.querySelector('#error').textContent=e.message;});
</script></body></html>"""
