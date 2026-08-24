# Bot Telegram — aiogram em um arquivo

Toda a lógica está em um único arquivo Python: `main.py`. O projeto usa aiogram, banco SQLite `bot.db` e painel dentro do Telegram pelo comando `/admin`.

No painel, a seção **Personalizar Start** permite editar texto, imagem e os botões da mensagem inicial. Cada botão aceita nome, link, emoji premium e cor; também é possível mudar a ordem e alternar a organização entre `2 + 2 + 1`, um botão por linha e `3 + 2`.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python main.py
```

Preencha `BOT_TOKEN` e `ADMIN_IDS` no `.env` antes de iniciar.

## Discloud

O projeto já inclui `discloud.config` para bot Python. Configure as variáveis `BOT_TOKEN` e `ADMIN_IDS` no ambiente da aplicação na Discloud e mantenha o arquivo `.env` fora do GitHub. O banco SQLite fica em `bot.db`; faça backup dele antes de atualizar ou recriar a aplicação para preservar usuários, planos e configurações.

## Retorno web

O projeto principal é um `site` na Discloud e inicia o bot e a página de resultados juntos. Registre o subdomínio `mobixretornoconsulta` no painel da Discloud e faça deploy da raiz do repositório. O link web é temporário e expira em 10 minutos.
