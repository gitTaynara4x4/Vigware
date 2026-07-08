from __future__ import annotations

import hashlib
import hmac
import json
import logging
import random
import re
import ssl
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests
import websocket

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover
    psycopg = None
    dict_row = None


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
STATE_DEFAULT_PATH = ROOT / "state.json"


@dataclass
class BridgeConfig:
    vigware_base_url: str

    # Fonte do evento:
    # database = produção segura: lê o PostgreSQL local do Active Net em modo somente leitura.
    # stomp = laboratório: tenta assinar o WebSocket interno da tela do Active Net.
    source_mode: str = "database"

    # Segurança do envio para o Vigware Cloud.
    auth_mode: str = "hmac"
    bridge_id: str = "activenet-matriz"
    bridge_secret: str = "TROQUE_ESTA_CHAVE_GRANDE"
    vigware_receiver_key: str = ""

    # Banco local do Active Net. Não escreve nada nesse banco.
    active_net_pg_host: str = "127.0.0.1"
    active_net_pg_port: int = 5433
    active_net_pg_database: str = "postgres"
    active_net_pg_user: str = "postgres"
    active_net_pg_password: str = ""
    active_net_pg_schema: str = "active_net"
    active_net_events_table: str = "eventos"
    active_net_last_id_file: str = "state.json"
    poll_seconds: float = 2.0
    batch_size: int = 100
    initial_position: str = "latest"  # latest = começa a copiar só eventos novos. beginning = importa tudo.

    # Sincronização segura de contas/clientes a partir do banco local.
    sync_accounts_on_start: bool = True
    sync_accounts_every_seconds: int = 600
    sync_accounts_limit: int = 5000

    # Compatibilidade com tentativa STOMP/WebSocket da interface do Active Net.
    active_net_base_url: str = "http://localhost:9081"
    active_net_verify_ssl: bool = False
    topics: list[str] | None = None
    send_remove_events: bool = False

    log_level: str = "INFO"
    reconnect_seconds: int = 5

    @classmethod
    def load(cls) -> "BridgeConfig":
        if not CONFIG_PATH.exists():
            raise SystemExit(
                f"Arquivo {CONFIG_PATH} não encontrado. Copie config.example.json para config.json e ajuste."
            )
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        data.setdefault("source_mode", "database")
        data.setdefault("topics", ["/topic/evento", "/topic/atualizar-evento"])
        data.setdefault("auth_mode", "hmac")
        data.setdefault("bridge_id", "activenet-matriz")
        data.setdefault("bridge_secret", "TROQUE_ESTA_CHAVE_GRANDE")
        data.setdefault("vigware_receiver_key", "")
        data.setdefault("active_net_pg_host", "127.0.0.1")
        data.setdefault("active_net_pg_port", 5433)
        data.setdefault("active_net_pg_database", "postgres")
        data.setdefault("active_net_pg_user", "postgres")
        data.setdefault("active_net_pg_password", "")
        data.setdefault("active_net_pg_schema", "active_net")
        data.setdefault("active_net_events_table", "eventos")
        data.setdefault("active_net_last_id_file", "state.json")
        data.setdefault("poll_seconds", 2)
        data.setdefault("batch_size", 100)
        data.setdefault("initial_position", "latest")
        data.setdefault("sync_accounts_on_start", True)
        data.setdefault("sync_accounts_every_seconds", 600)
        data.setdefault("sync_accounts_limit", 5000)
        return cls(**data)


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "---", "-", "null", "None"}:
        return None
    return re.sub(r"\s+", " ", text)


def normalize_account(value: Any) -> str | None:
    text = clean(value)
    if not text:
        return None
    return text.zfill(4) if text.isdigit() else text


def state_path(config: BridgeConfig) -> Path:
    path = Path(config.active_net_last_id_file)
    if not path.is_absolute():
        path = ROOT / path
    return path


def load_state(config: BridgeConfig) -> dict[str, Any]:
    path = state_path(config)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logging.warning("Não consegui ler %s. Vou iniciar estado vazio.", path)
        return {}


def save_state(config: BridgeConfig, state: dict[str, Any]) -> None:
    path = state_path(config)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def pg_connect(config: BridgeConfig):
    if psycopg is None:
        raise RuntimeError("Dependência psycopg não instalada. Rode .\\run_bridge.ps1 de novo.")

    kwargs = {
        "host": config.active_net_pg_host,
        "port": int(config.active_net_pg_port),
        "dbname": config.active_net_pg_database,
        "user": config.active_net_pg_user,
        "connect_timeout": 5,
        "row_factory": dict_row,
        # Proteção extra: qualquer transação criada por esta conexão nasce read-only.
        "options": "-c default_transaction_read_only=on -c statement_timeout=10000",
    }
    if config.active_net_pg_password:
        kwargs["password"] = config.active_net_pg_password
    return psycopg.connect(**kwargs)


def table_sql(config: BridgeConfig) -> str:
    # Nomes fixos vindos do config local. Mantém simples e evita interpolar valores vindos da internet.
    schema = re.sub(r"[^a-zA-Z0-9_]", "", config.active_net_pg_schema)
    table = re.sub(r"[^a-zA-Z0-9_]", "", config.active_net_events_table)
    return f'"{schema}"."{table}"'


def get_max_event_id(config: BridgeConfig) -> int:
    sql = f"SELECT COALESCE(MAX(id), 0) AS max_id FROM {table_sql(config)}"
    with pg_connect(config) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone() or {"max_id": 0}
            return int(row["max_id"] or 0)


def fetch_new_db_events(config: BridgeConfig, last_id: int) -> list[dict[str, Any]]:
    sql = f"""
        SELECT
            id,
            conta,
            evento,
            descricao,
            data_hora,
            data_hora_evento_gerado_central,
            enviado,
            numero,
            numero_serie,
            imei,
            mac,
            nome_cliente,
            particao_pgm,
            zona_usuario,
            nome_zona_usuario,
            tipo_campo_part_pgm,
            tipo_campo_zona_usuario,
            id_area,
            local_de_acesso,
            tipo_de_acesso,
            tipo_de_usuario,
            id_unico_usuario,
            location
        FROM {table_sql(config)}
        WHERE id > %s
        ORDER BY id ASC
        LIMIT %s
    """
    with pg_connect(config) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (last_id, int(config.batch_size)))
            return list(cur.fetchall())


def build_info_1(row: dict[str, Any]) -> str | None:
    parts: list[str] = []
    zona = clean(row.get("zona_usuario"))
    nome_zona = clean(row.get("nome_zona_usuario"))
    tipo_zona = clean(row.get("tipo_campo_zona_usuario"))

    if zona:
        label = tipo_zona or "Zona/Usuário"
        text = f"{label} {zona}"
        if nome_zona:
            text += f" - {nome_zona}"
        parts.append(text)

    usuario = clean(row.get("id_unico_usuario"))
    if usuario and not zona:
        parts.append(f"Usuário {usuario}")

    return " | ".join(parts) if parts else None


def build_info_2(row: dict[str, Any]) -> str | None:
    parts: list[str] = []
    particao = clean(row.get("particao_pgm"))
    tipo_particao = clean(row.get("tipo_campo_part_pgm"))
    if particao:
        label = tipo_particao or "Partição/PGM"
        parts.append(f"{label} {particao}")

    local = clean(row.get("local_de_acesso"))
    tipo = clean(row.get("tipo_de_acesso"))
    if local:
        parts.append(f"Local {local}")
    if tipo:
        parts.append(f"Acesso {tipo}")

    return " | ".join(parts) if parts else None


def normalize_event_from_db_row(row: dict[str, Any]) -> dict[str, Any] | None:
    account = normalize_account(row.get("conta"))
    event_code = clean(row.get("evento"))
    if not account or not event_code:
        return None

    event: dict[str, Any] = {
        "account_code": account,
        "event_code": event_code,
        "description": clean(row.get("descricao")),
        "info_1": build_info_1(row),
        "info_2": build_info_2(row),
        "date_time": clean(row.get("data_hora")) or clean(row.get("data_hora_evento_gerado_central")),
        "serial_number": clean(row.get("numero_serie")),
        "imei": clean(row.get("imei")),
        "mac": clean(row.get("mac")),
        "row": {
            "source": "active_net_db",
            **row,
        },
    }
    # Remove chaves vazias do nível normalizado, mas mantém row completo para auditoria no Vigware.
    return {k: v for k, v in event.items() if v is not None}


def build_auth_headers(config: BridgeConfig, body_bytes: bytes) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}

    mode = (config.auth_mode or "hmac").strip().lower()
    if mode in {"simple", "api_key", "key"}:
        if not config.vigware_receiver_key:
            raise RuntimeError("vigware_receiver_key não configurada para auth_mode=simple")
        headers["X-Vigware-Key"] = config.vigware_receiver_key
        return headers

    if mode != "hmac":
        raise RuntimeError(f"auth_mode inválido: {config.auth_mode}")

    if not config.bridge_id or not config.bridge_secret or config.bridge_secret == "TROQUE_ESTA_CHAVE_GRANDE":
        raise RuntimeError("bridge_id/bridge_secret não configurados para auth_mode=hmac")

    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    message = timestamp.encode("utf-8") + b"." + nonce.encode("utf-8") + b"." + body_bytes
    signature = "sha256=" + hmac.new(config.bridge_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    headers.update({
        "X-Vigware-Bridge-Id": config.bridge_id,
        "X-Vigware-Timestamp": timestamp,
        "X-Vigware-Nonce": nonce,
        "X-Vigware-Signature": signature,
    })
    return headers



def post_accounts_to_vigware(config: BridgeConfig, accounts: list[dict[str, Any]], source: str = "ACTIVENET_DB") -> None:
    if not accounts:
        return
    base = config.vigware_base_url.rstrip("/")
    url = f"{base}/api/receiver/activenet/accounts/batch"
    body = {"source": source, "accounts": accounts}
    body_bytes = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = build_auth_headers(config, body_bytes)
    response = requests.post(url, data=body_bytes, headers=headers, timeout=30)
    response.raise_for_status()
    logging.info("Contas enviadas para Vigware: %s | resposta=%s", len(accounts), response.text[:250])


def _first_value(row: dict[str, Any], names: list[str]) -> Any:
    lowered = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        if name.lower() in lowered and lowered[name.lower()] not in (None, "", "---"):
            return lowered[name.lower()]
    return None



def _json_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []

def normalize_account_from_any_row(row: dict[str, Any]) -> dict[str, Any] | None:
    account_code = normalize_account(_first_value(row, ["account_code", "conta", "codigo", "numero_conta"]))
    if not account_code:
        return None
    client_name = clean(_first_value(row, ["client_name", "nome_cliente", "nomecliente", "cliente", "nome", "nome_fantasia", "fantasia", "razao_social", "razao"]))
    if not client_name:
        client_name = f"Conta {account_code}"
    account_name = clean(_first_value(row, ["account_name", "nome_conta", "descricao", "local", "nome_local"])) or client_name
    partition = clean(_first_value(row, ["partition_number", "particao", "particao_pgm", "partition"])) or "001"
    if partition.isdigit():
        partition = partition.zfill(3)

    return {
        "account_code": account_code,
        "client_name": client_name,
        "account_name": account_name,
        "partition_number": partition,
        "phone": clean(_first_value(row, ["phone", "telefone", "telefone_dono", "celular", "fone"])),
        "email": clean(_first_value(row, ["email", "e_mail"])),
        "document": clean(_first_value(row, ["document", "documento", "cpf", "cnpj"])),
        "address": clean(_first_value(row, ["address", "endereco", "logradouro", "rua", "location", "localizacao"])),
        "notes": clean(_first_value(row, ["notes", "informacoes_do_local", "informações_do_local", "observacoes"])),
        "protocol_note": clean(_first_value(row, ["protocol_note", "regras_do_local", "como_atuar", "procedimento"])),
        "contacts": _json_list(row.get("contacts")),
        "zones": _json_list(row.get("zones")),
        "source_owner_id": clean(_first_value(row, ["source_owner_id", "dono_cliente_id", "owner_id"])),
        "source_client_id": clean(_first_value(row, ["source_client_id", "cliente_id", "clientes_id", "id_cliente"])),
        "source_account_id": clean(_first_value(row, ["source_account_id", "conta_id", "contas_id", "id_conta", "id"])),
        "row": row,
    }


def active_net_table(config: BridgeConfig, table_name: str) -> str:
    schema = re.sub(r"[^a-zA-Z0-9_]", "", config.active_net_pg_schema)
    table = re.sub(r"[^a-zA-Z0-9_]", "", table_name)
    return f'"{schema}"."{table}"'


def fetch_accounts_from_recent_events(config: BridgeConfig) -> list[dict[str, Any]]:
    # Produção segura: lê os cadastros reais do Active Net em modo somente leitura.
    # Dados usados agora:
    # contas -> cliente técnico/comunicador
    # clientes -> dados do módulo/comunicador
    # dono_cliente -> nome, telefone, endereço e regras do local
    # contato_cliente -> contatos do local
    # area -> áreas/zonas cadastradas do local
    contas_table = active_net_table(config, "contas")
    clientes_table = active_net_table(config, "clientes")
    dono_table = active_net_table(config, "dono_cliente")
    contato_table = active_net_table(config, "contato_cliente")
    area_table = active_net_table(config, "area")

    sql = f"""
        SELECT
            cta.id AS source_account_id,
            cta.conta AS conta,
            COALESCE(
                NULLIF(BTRIM(cta.nome_cliente), ''),
                NULLIF(BTRIM(cli.nome), ''),
                NULLIF(BTRIM(dono.nome), ''),
                'Conta ' || cta.conta
            ) AS client_name,
            COALESCE(
                NULLIF(BTRIM(cta.nome_cliente), ''),
                NULLIF(BTRIM(cli.nome), ''),
                NULLIF(BTRIM(dono.nome), ''),
                'Conta ' || cta.conta
            ) AS account_name,
            cta.particao AS particao,
            COALESCE(NULLIF(BTRIM(cta.telefone), ''), NULLIF(BTRIM(dono.telefone), '')) AS telefone,
            cta.clientes_id AS source_client_id,
            cli.id AS active_net_cliente_id,
            cli.numero_serie AS numero_serie,
            cli.imei AS imei,
            cli.mac AS mac,
            cli.dono_cliente_id AS dono_cliente_id,
            dono.nome AS dono_cliente_nome,
            dono.telefone AS telefone_dono,
            dono.endereco AS endereco,
            dono.informacoes_do_local AS informacoes_do_local,
            dono.regras_do_local AS regras_do_local,
            (
                SELECT COALESCE(json_agg(json_build_object(
                    'name', contato.nome,
                    'phone', contato.telefone,
                    'function', contato.funcao,
                    'priority', contato.id
                ) ORDER BY contato.id), '[]'::json)
                FROM {contato_table} contato
                WHERE contato.dono_cliente_id = dono.id
            ) AS contacts,
            (
                SELECT COALESCE(json_agg(json_build_object(
                    'zone_number', area.id::text,
                    'name', area.nome,
                    'area', area.nome
                ) ORDER BY area.id), '[]'::json)
                FROM {area_table} area
                WHERE area.dono_cliente_id = dono.id
            ) AS zones
        FROM {contas_table} cta
        LEFT JOIN {clientes_table} cli ON cli.id = cta.clientes_id
        LEFT JOIN {dono_table} dono ON dono.id = cli.dono_cliente_id
        WHERE cta.conta IS NOT NULL
          AND BTRIM(cta.conta) <> ''
        ORDER BY cta.conta ASC
        LIMIT %s
    """

    accounts: list[dict[str, Any]] = []
    with pg_connect(config) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (int(config.sync_accounts_limit),))
            for row in cur.fetchall():
                item = normalize_account_from_any_row(dict(row))
                if item:
                    accounts.append(item)
    return accounts

def sync_accounts_snapshot(config: BridgeConfig) -> None:
    try:
        accounts = fetch_accounts_from_recent_events(config)
        if accounts:
            post_accounts_to_vigware(config, accounts, source="ACTIVENET_DB_ACCOUNTS")
        else:
            logging.info("Sincronização de contas: nenhum cadastro encontrado em eventos recentes.")
    except Exception as exc:
        logging.warning("Falha ao sincronizar contas/clientes: %s", exc)


def post_to_vigware(config: BridgeConfig, events: list[dict[str, Any]], source: str = "ACTIVENET_DB") -> None:
    if not events:
        return
    base = config.vigware_base_url.rstrip("/")
    url = f"{base}/api/receiver/activenet/batch"
    body = {"source": source, "events": events}
    body_bytes = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = build_auth_headers(config, body_bytes)
    response = requests.post(url, data=body_bytes, headers=headers, timeout=20)
    response.raise_for_status()
    logging.info("Enviado para Vigware: %s eventos | resposta=%s", len(events), response.text[:250])


def run_database_bridge(config: BridgeConfig) -> None:
    logging.info("Modo banco ativo. Leitura somente SELECT em %s:%s/%s.%s.%s", config.active_net_pg_host, config.active_net_pg_port, config.active_net_pg_database, config.active_net_pg_schema, config.active_net_events_table)
    state = load_state(config)

    if "last_id" not in state:
        if (config.initial_position or "latest").lower() == "beginning":
            state["last_id"] = 0
            logging.warning("Primeira execução com initial_position=beginning. Vai importar eventos antigos.")
        else:
            state["last_id"] = get_max_event_id(config)
            logging.info("Primeira execução. Começando do último id atual: %s. Eventos antigos não serão enviados.", state["last_id"])
        save_state(config, state)

    if config.sync_accounts_on_start:
        logging.info("Sincronizando contas/clientes do Active Net para o Vigware antes de processar eventos...")
        sync_accounts_snapshot(config)
        state["last_account_sync_at"] = int(time.time())
        save_state(config, state)

    while True:
        try:
            now = int(time.time())
            every = int(config.sync_accounts_every_seconds or 0)
            if every > 0 and now - int(state.get("last_account_sync_at") or 0) >= every:
                sync_accounts_snapshot(config)
                state["last_account_sync_at"] = now
                save_state(config, state)

            last_id = int(state.get("last_id") or 0)
            rows = fetch_new_db_events(config, last_id)
            events: list[dict[str, Any]] = []
            max_seen = last_id

            for row in rows:
                row_id = int(row["id"])
                max_seen = max(max_seen, row_id)
                normalized = normalize_event_from_db_row(row)
                if normalized:
                    events.append(normalized)

            if events:
                post_to_vigware(config, events, source="ACTIVENET_DB")
                logging.info("Eventos DB enviados. ids %s -> %s", rows[0]["id"], max_seen)
            elif rows:
                logging.info("Linhas novas sem conta/evento foram ignoradas. Último id=%s", max_seen)

            if max_seen != last_id:
                state["last_id"] = max_seen
                state["updated_at"] = int(time.time())
                save_state(config, state)

        except KeyboardInterrupt:
            raise
        except Exception as exc:
            logging.warning("Falha no modo banco: %s", exc)

        time.sleep(float(config.poll_seconds))


# ===== Modo STOMP antigo/experimental =====

def build_ws_candidates(base_url: str) -> list[tuple[str, bool]]:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    host = parsed.netloc
    prefix = parsed.path.rstrip("")
    if prefix.endswith("/"):
        prefix = prefix[:-1]

    session = uuid.uuid4().hex[:12]
    server = str(random.randint(100, 999))

    candidates = [
        (urlunparse((scheme, host, f"{prefix}/active-net-websocket/websocket", "", "", "")), False),
        (urlunparse((scheme, host, f"{prefix}/active-net-websocket/{server}/{session}/websocket", "", "", "")), True),
    ]
    seen = set()
    result = []
    for item in candidates:
        if item[0] not in seen:
            seen.add(item[0])
            result.append(item)
    return result


def stomp_frame(command: str, headers: dict[str, str] | None = None, body: str = "") -> str:
    headers = headers or {}
    lines = [command]
    for key, value in headers.items():
        lines.append(f"{key}:{value}")
    lines.append("")
    lines.append(body)
    return "\n".join(lines) + "\x00"


def send_frame(ws: websocket.WebSocket, frame: str, sockjs: bool) -> None:
    if sockjs:
        ws.send(json.dumps([frame]))
    else:
        ws.send(frame)


def decode_sockjs_message(message: str, sockjs: bool) -> list[str]:
    if not sockjs:
        return [message]
    if message in {"o", "h"}:
        return []
    if message.startswith("c"):
        raise ConnectionError(f"SockJS fechou conexão: {message}")
    if message.startswith("a"):
        payload = json.loads(message[1:])
        if isinstance(payload, list):
            return [str(x) for x in payload]
    return []


def parse_stomp_frame(frame: str) -> tuple[str, dict[str, str], str]:
    frame = frame.replace("\x00", "")
    parts = frame.split("\n\n", 1)
    head = parts[0]
    body = parts[1] if len(parts) > 1 else ""
    lines = head.splitlines()
    command = lines[0].strip() if lines else ""
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()
    return command, headers, body.strip()


def deep_find(obj: Any, names: list[str]) -> Any:
    lower = {n.lower() for n in names}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in lower and value not in (None, "", "---"):
                return value
        for value in obj.values():
            found = deep_find(value, names)
            if found not in (None, "", "---"):
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = deep_find(item, names)
            if found not in (None, "", "---"):
                return found
    return None


def normalize_event_from_body(body: str) -> list[dict[str, Any]]:
    if not body:
        return []
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return [{"row": {"raw": body}}]

    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        if isinstance(parsed.get("eventos"), list):
            items = parsed["eventos"]
        elif isinstance(parsed.get("events"), list):
            items = parsed["events"]
        elif isinstance(parsed.get("data"), list):
            items = parsed["data"]
        elif isinstance(parsed.get("evento"), dict):
            items = [parsed["evento"]]
        elif isinstance(parsed.get("event"), dict):
            items = [parsed["event"]]
        else:
            items = [parsed]
    else:
        return []

    output = []
    for item in items:
        if not isinstance(item, dict):
            continue
        account = clean(deep_find(item, ["Conta", "conta", "account", "accountCode", "account_code", "codigoConta"]))
        event_code = clean(deep_find(item, ["Evento", "evento", "eventCode", "event_code", "code", "codigoEvento"]))
        description = clean(deep_find(item, ["Descrição", "Descricao", "description", "descricao", "mensagem", "message"]))
        info_1 = clean(deep_find(item, ["Informação 1", "Informacao 1", "info1", "info_1", "informacao1"]))
        info_2 = clean(deep_find(item, ["Informação 2", "Informacao 2", "info2", "info_2", "informacao2"]))
        date_time = clean(deep_find(item, ["Data e hora", "dataHora", "dateTime", "date_time", "datetime", "data"]))
        serial = clean(deep_find(item, ["Número de série", "Numero de serie", "serial", "serialNumber", "numeroSerie"]))
        imei = clean(deep_find(item, ["IMEI", "imei"]))
        mac = clean(deep_find(item, ["MAC", "mac"]))

        payload: dict[str, Any] = {"row": item}
        if account:
            payload["account_code"] = account.zfill(4) if account.isdigit() else account
        if event_code:
            payload["event_code"] = event_code
        if description:
            payload["description"] = description
        if info_1:
            payload["info_1"] = info_1
        if info_2:
            payload["info_2"] = info_2
        if date_time:
            payload["date_time"] = date_time
        if serial:
            payload["serial_number"] = serial
        if imei:
            payload["imei"] = imei
        if mac:
            payload["mac"] = mac
        if payload.get("account_code") and payload.get("event_code"):
            output.append(payload)
    return output


def run_stomp_once(config: BridgeConfig, ws_url: str, sockjs: bool) -> None:
    sslopt = {}
    if ws_url.startswith("wss") and not config.active_net_verify_ssl:
        sslopt = {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}

    logging.info("Conectando Active Net STOMP: %s | sockjs=%s", ws_url, sockjs)
    ws = websocket.create_connection(ws_url, timeout=20, sslopt=sslopt)
    try:
        connect = stomp_frame("CONNECT", {"accept-version": "1.1,1.0", "heart-beat": "0,0"})
        send_frame(ws, connect, sockjs)
        connected = False
        subscribed = False
        while True:
            raw_message = ws.recv()
            for frame_text in decode_sockjs_message(str(raw_message), sockjs):
                command, headers, body = parse_stomp_frame(frame_text)
                if command == "CONNECTED":
                    connected = True
                    logging.info("STOMP conectado: %s", headers)
                if connected and not subscribed:
                    topics = config.topics or ["/topic/evento", "/topic/atualizar-evento"]
                    if config.send_remove_events:
                        topics.append("/topic/remover-evento")
                    for index, topic in enumerate(topics):
                        send_frame(ws, stomp_frame("SUBSCRIBE", {"id": f"vigware-{index}", "destination": topic, "ack": "auto"}), sockjs)
                        logging.info("Assinado tópico: %s", topic)
                    subscribed = True
                if command == "MESSAGE":
                    events = normalize_event_from_body(body)
                    post_to_vigware(config, events, source="ACTIVENET_STOMP")
    finally:
        try:
            ws.close()
        except Exception:
            pass


def run_stomp_forever(config: BridgeConfig) -> None:
    candidates = build_ws_candidates(config.active_net_base_url)
    while True:
        for ws_url, sockjs in candidates:
            try:
                run_stomp_once(config, ws_url, sockjs)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                logging.warning("Falha no bridge STOMP usando %s: %s", ws_url, exc)
        logging.info("Reconectando em %s segundos...", config.reconnect_seconds)
        time.sleep(config.reconnect_seconds)


def main() -> int:
    config = BridgeConfig.load()
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logging.info("Vigware Bridge Active Net iniciado")
    logging.info("Vigware Cloud: %s", config.vigware_base_url)
    logging.info("Fonte: %s", config.source_mode)

    if (config.source_mode or "database").lower() in {"database", "db", "postgres", "postgresql"}:
        run_database_bridge(config)
    else:
        logging.warning("Modo STOMP é experimental; prefira source_mode=database para produção.")
        logging.info("Active Net Web: %s", config.active_net_base_url)
        run_stomp_forever(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
