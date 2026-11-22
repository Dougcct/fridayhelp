"""Dispara o Manual Deploy / reinício do serviço Friday Help no Render via Deploy Hook oficial.

Como configurar:
1. No painel do Render, abra o seu Web Service -> Settings -> Build & Deploy -> Deploy Hook.
2. Copie a URL oficial (ex.: https://api.render.com/deploy/srv-xxxx?key=xxxx).
3. Adicione no arquivo .env na raiz do projeto (nunca commite o .env no GitHub):
   RENDER_DEPLOY_HOOK=https://api.render.com/deploy/srv-xxxx?key=xxxx

Como usar:
   python deploy_render.py
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


def _load_deploy_hook() -> str:
    """Lê RENDER_DEPLOY_HOOK das variáveis de ambiente ou do arquivo .env local."""
    hook = os.environ.get("RENDER_DEPLOY_HOOK", "").strip()
    if hook:
        return hook

    if ENV_FILE.exists():
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            if key.strip() == "RENDER_DEPLOY_HOOK":
                return val.strip().strip('"').strip("'")
    return ""


def trigger_render_deploy() -> int:
    """Envia uma requisição POST ao Deploy Hook oficial do Render."""
    hook_url = _load_deploy_hook()
    if not hook_url:
        print("RENDER_DEPLOY_HOOK não configurado.")
        print("Adicione no arquivo .env:")
        print("  RENDER_DEPLOY_HOOK=https://api.render.com/deploy/srv-xxxx?key=xxxx")
        return 1

    if not hook_url.startswith("https://api.render.com/deploy/"):
        print("URL inválida: o Deploy Hook deve começar com https://api.render.com/deploy/")
        return 1

    service_part = hook_url.split("?", 1)[0]
    print(f"Disparando deploy no Render ({service_part})...")

    req = urllib.request.Request(hook_url, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", "ignore").strip()
            print(f"OK (HTTP {resp.status}): deploy iniciado no Render.")
            if body:
                print(f"Resposta: {body[:200]}")
            return 0
    except urllib.error.HTTPError as exc:
        print(f"Erro HTTP {exc.code} ao acionar Deploy Hook: {exc.reason}")
        return 1
    except urllib.error.URLError as exc:
        print(f"Erro de conexão ao acionar Deploy Hook: {exc.reason}")
        return 1


if __name__ == "__main__":
    sys.exit(trigger_render_deploy())
