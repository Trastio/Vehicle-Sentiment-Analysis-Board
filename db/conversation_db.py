# -*- coding: utf-8 -*-
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
from db.database import execute_query, execute_update


def create_conversation(title: str = "", car_model: str = "") -> Dict[str, Any]:
    conv_id = uuid.uuid4().hex[:16]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute_update(
        "INSERT INTO conversations (id, title, car_model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (conv_id, title, car_model, now, now),
    )
    return {"id": conv_id, "title": title, "car_model": car_model, "created_at": now, "updated_at": now}


def get_conversation(conv_id: str) -> Optional[Dict[str, Any]]:
    rows = execute_query("SELECT * FROM conversations WHERE id = ?", (conv_id,))
    return rows[0] if rows else None


def list_conversations(limit: int = 20) -> List[Dict[str, Any]]:
    return execute_query(
        "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)
    )


def update_conversation(conv_id: str, title: str = None, car_model: str = None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sets = ["updated_at = ?"]
    params = [now]
    if title is not None:
        sets.append("title = ?")
        params.append(title)
    if car_model is not None:
        sets.append("car_model = ?")
        params.append(car_model)
    params.append(conv_id)
    execute_update(f"UPDATE conversations SET {', '.join(sets)} WHERE id = ?", tuple(params))


def delete_conversation(conv_id: str):
    execute_update("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    execute_update("DELETE FROM conversations WHERE id = ?", (conv_id,))


def add_message(conv_id: str, role: str, content: str, message_type: str = "text", metadata: Dict = None) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_str = json.dumps(metadata or {}, ensure_ascii=False)
    msg_id = execute_update(
        "INSERT INTO messages (conversation_id, role, content, message_type, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, role, content, message_type, meta_str, now),
    )
    execute_update("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
    return msg_id


def get_messages(conv_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    return execute_query(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
        (conv_id, limit),
    )


def get_recent_messages(conv_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    rows = execute_query(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
        (conv_id, limit),
    )
    return list(reversed(rows))


def get_or_create_conversation(conv_id: str = None) -> Dict[str, Any]:
    if conv_id:
        conv = get_conversation(conv_id)
        if conv:
            return conv
    return create_conversation("新对话")
