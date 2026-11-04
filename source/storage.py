"""
JSON-file persistence for chat state (searches, filters, seen listings).

The file location is provided by the caller (read from STATE_FILE in .env).
Writes are atomic: data is written to a temporary file and then renamed, so a
crash mid-write cannot corrupt the existing state file.
"""

import json
import logging
import os
import tempfile
from typing import Dict

from chat_client import ChatClient


def load_state(path: str) -> Dict[int, ChatClient]:
    """
    Load persisted chat state from the given JSON file.

    Returns a mapping of chat_id -> ChatClient. If the file does not exist or
    cannot be parsed, an empty mapping is returned (and the error is logged).
    """
    if not path or not os.path.exists(path):
        logging.info("no state file at '%s', starting with empty state", path)
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logging.error("could not read state file '%s': %s", path, e)
        return {}

    clients: Dict[int, ChatClient] = {}
    for chat_data in data.get("chats", []):
        try:
            client = ChatClient.from_dict(chat_data)
            clients[client.id] = client
        except Exception as e:
            logging.error("skipping malformed chat entry in state file: %s", e)

    logging.info("loaded state for %d chat(s) from '%s'", len(clients), path)
    return clients


def save_state(path: str, clients: Dict[int, ChatClient]) -> None:
    """
    Persist the given chat state to the JSON file atomically.
    """
    if not path:
        logging.warning("no STATE_FILE configured, state will not be persisted")
        return

    payload = {"chats": [client.to_dict() for client in clients.values()]}

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    try:
        # Write to a temp file in the same directory, then atomically replace.
        fd, tmp_path = tempfile.mkstemp(dir=directory or ".", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except OSError as e:
        logging.error("could not write state file '%s': %s", path, e)
