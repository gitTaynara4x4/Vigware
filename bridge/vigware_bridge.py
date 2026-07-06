from __future__ import annotations

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


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"


@dataclass
class BridgeConfig:
    vigware_base_url: str
    vigware_receiver_key: str
    active_net_base_url: str = "https://localhost:9081"
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
        data.setdefault("topics", ["/topic/evento", "/topic/atualizar-evento"])
        return cls(**data)


def build_ws_candidates(base_url: str) -> list[tuple[str, bool]]:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    host = parsed.netloc
    prefix = parsed.path.rstrip("")
    if prefix.endswith("/"):
        prefix = prefix[:-1]

    session = uuid.uuid4().hex[:12]
    server = str(random.randint(100, 999))

    # bool = usa envelope SockJS JSON array.
    candidates = [
        (urlunparse((scheme, host, f"{prefix}/active-net-websocket/websocket", "", "", "")), False),
        (urlunparse((scheme, host, f"{prefix}/active-net-websocket/{server}/{session}/websocket", "", "", "")), True),
    ]
    # remove duplicados mantendo ordem
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

    if message == "o":
        return []
    if message == "h":
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


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "---", "-", "null", "None"}:
        return None
    return re.sub(r"\s+", " ", text)


def normalize_event_from_body(body: str) -> list[dict[str, Any]]:
    """Transforma a mensagem do Active Net em payloads aceitos pelo Vigware.

    O Active Net pode mandar objeto, array, objeto dentro de 'evento' ou string.
    O mapeamento é tolerante para a primeira integração real.
    """
    if not body:
        return []

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return [{"row": {"raw": body}}]

    items: list[Any]
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

        # Só envia para o Vigware quando tiver pelo menos conta e evento.
        if payload.get("account_code") and payload.get("event_code"):
            output.append(payload)
        else:
            logging.debug("Mensagem ignorada sem conta/evento: %s", item)

    return output


def post_to_vigware(config: BridgeConfig, events: list[dict[str, Any]]) -> None:
    if not events:
        return
    base = config.vigware_base_url.rstrip("/")
    url = f"{base}/api/receiver/activenet/batch"
    headers = {
        "X-Vigware-Key": config.vigware_receiver_key,
        "Content-Type": "application/json",
    }
    body = {"source": "ACTIVENET_STOMP", "events": events}
    response = requests.post(url, json=body, headers=headers, timeout=15)
    response.raise_for_status()
    logging.info("Enviado para Vigware: %s eventos | resposta=%s", len(events), response.text[:250])


def run_once(config: BridgeConfig, ws_url: str, sockjs: bool) -> None:
    sslopt = {}
    if ws_url.startswith("wss") and not config.active_net_verify_ssl:
        sslopt = {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}

    logging.info("Conectando Active Net: %s | sockjs=%s", ws_url, sockjs)
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
                        frame = stomp_frame(
                            "SUBSCRIBE",
                            {
                                "id": f"vigware-{index}",
                                "destination": topic,
                                "ack": "auto",
                            },
                        )
                        send_frame(ws, frame, sockjs)
                        logging.info("Assinado tópico: %s", topic)
                    subscribed = True

                if command == "MESSAGE":
                    destination = headers.get("destination", "")
                    logging.info("Mensagem STOMP recebida de %s", destination)
                    events = normalize_event_from_body(body)
                    post_to_vigware(config, events)
    finally:
        try:
            ws.close()
        except Exception:
            pass


def run_forever(config: BridgeConfig) -> None:
    candidates = build_ws_candidates(config.active_net_base_url)
    while True:
        for ws_url, sockjs in candidates:
            try:
                run_once(config, ws_url, sockjs)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                logging.warning("Falha no bridge usando %s: %s", ws_url, exc)
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
    logging.info("Active Net: %s", config.active_net_base_url)
    run_forever(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
