"""Carrega credenciais HubSoft de um tenant a partir do DB Hubtrix.

Le `IntegracaoAPI` (tipo=hubsoft, ativa=TRUE) do tenant via psycopg2,
decripta `username` e `password` (Fernet/SECRET_KEY) e devolve um dict
com tudo o que o bot Selenium precisa pra logar e operar.

Replica `apps.sistema.encrypted_fields._get_key()` localmente — assim o
bot nao precisa importar Django, so a biblioteca `cryptography`.

Env vars esperadas (em .env.hubtrix):
  HUBTRIX_DB_HOST, HUBTRIX_DB_PORT, HUBTRIX_DB_NAME,
  HUBTRIX_DB_USER, HUBTRIX_DB_PASSWORD
  SECRET_KEY          # mesma SECRET_KEY do Django, usada pra decrypt
  FIELD_ENCRYPTION_KEY (opcional, override)
"""
from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass

import psycopg2
from cryptography.fernet import Fernet, InvalidToken


@dataclass
class ConfigTenant:
    tenant_id: int
    tenant_slug: str
    integracao_id: int
    base_url_api: str
    url_ui_login: str
    username: str
    password: str
    vendedor_id_padrao: int | None
    id_origem_padrao: int | None


def _get_key() -> bytes:
    """Mesma logica de apps/sistema/encrypted_fields.py:_get_key()."""
    raw = os.environ.get('FIELD_ENCRYPTION_KEY') or os.environ.get('SECRET_KEY')
    if not raw:
        raise RuntimeError(
            'SECRET_KEY (ou FIELD_ENCRYPTION_KEY) precisa estar no env pra decryptar credenciais.'
        )
    if isinstance(raw, str):
        raw = raw.encode()
    try:
        Fernet(raw)
        return raw
    except Exception:
        pass
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())


def _decrypt(value: str) -> str:
    if not value:
        return value
    try:
        f = Fernet(_get_key())
        return f.decrypt(value.encode()).decode()
    except InvalidToken:
        raise RuntimeError(
            'Falha ao decryptar credencial: SECRET_KEY do .env.hubtrix difere da que salvou no DB.'
        )


def _base_url_ui(base_url_api: str) -> str:
    """https://api.artelecom.hubsoft.com.br/ -> https://artelecom.hubsoft.com.br/login"""
    u = (base_url_api or '').rstrip('/')
    if u.startswith('https://api.'):
        u = 'https://' + u[len('https://api.'):]
    elif u.startswith('http://api.'):
        u = 'http://' + u[len('http://api.'):]
    return u + '/login'


def carregar_config(tenant_slug: str) -> ConfigTenant:
    db_cfg = {
        'host': os.environ['HUBTRIX_DB_HOST'],
        'port': int(os.environ.get('HUBTRIX_DB_PORT', '5432')),
        'database': os.environ['HUBTRIX_DB_NAME'],
        'user': os.environ['HUBTRIX_DB_USER'],
        'password': os.environ['HUBTRIX_DB_PASSWORD'],
    }
    conn = psycopg2.connect(**db_cfg, connect_timeout=10)
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT t.id, t.slug, i.id, i.base_url, i.username, i.password, i.configuracoes_extras
            FROM integracoes_api i JOIN sistema_tenant t ON t.id=i.tenant_id
            WHERE t.slug=%s AND i.tipo='hubsoft' AND i.ativa=TRUE AND t.ativo=TRUE
            LIMIT 1""",
            [tenant_slug],
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f'IntegracaoAPI hubsoft ativa nao encontrada para tenant={tenant_slug!r}')
        tenant_id, slug, integracao_id, base_url, user_enc, pass_enc, extras = row
        extras = extras or {}
        # IntegracaoAPI: username e CharField plain text; password e EncryptedCharField (Fernet).
        return ConfigTenant(
            tenant_id=tenant_id,
            tenant_slug=slug,
            integracao_id=integracao_id,
            base_url_api=base_url,
            url_ui_login=_base_url_ui(base_url),
            username=user_enc or '',
            password=_decrypt(pass_enc),
            vendedor_id_padrao=extras.get('vendedor_id_padrao'),
            id_origem_padrao=extras.get('id_origem_padrao'),
        )
    finally:
        conn.close()


def hubtrix_db_config() -> dict:
    """Retorna config psycopg2 pro DB Hubtrix — pra `prospectos`, `leads_prospectos`, etc."""
    return {
        'host': os.environ['HUBTRIX_DB_HOST'],
        'port': int(os.environ.get('HUBTRIX_DB_PORT', '5432')),
        'database': os.environ['HUBTRIX_DB_NAME'],
        'user': os.environ['HUBTRIX_DB_USER'],
        'password': os.environ['HUBTRIX_DB_PASSWORD'],
    }


if __name__ == '__main__':
    # Smoke test: carrega .env.hubtrix do diretorio atual e imprime config (sem senha)
    import sys
    from pathlib import Path
    env_file = Path(__file__).parent / '.env.hubtrix'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    slug = sys.argv[1] if len(sys.argv) > 1 else 'nuvyon'
    cfg = carregar_config(slug)
    print(f'Config carregada pra tenant={cfg.tenant_slug}:')
    print(f'  integracao_id : {cfg.integracao_id}')
    print(f'  base_url_api  : {cfg.base_url_api}')
    print(f'  url_ui_login  : {cfg.url_ui_login}')
    print(f'  username      : {cfg.username}')
    print(f'  password      : {"***" if cfg.password else "(vazio)"} (len={len(cfg.password)})')
    print(f'  vendedor_pad  : {cfg.vendedor_id_padrao}')
    print(f'  id_origem_pad : {cfg.id_origem_padrao}')
