"""
Chat Warden Automation Handler for LeagueLoop.

Monitors champion select chat for toxicity and toxic keywords.
"""

from utils.logger import Logger
from core.events import EventBus

def handle_chat_warden(engine, session):
    chat_room = session.get("chatDetails", {}).get("chatRoomName")
    if not chat_room: return

    if engine._chat_warden_warned: return

    req = engine.lcu.request("GET", f"/lol-chat/v1/conversations/{chat_room}/messages", silent=True)
    if not req or req.status_code != 200: return

    msgs = req.json()
    for m in msgs:
        text = m.get("body", "").lower()
        for kw in engine._toxic_keywords:
            if kw in text:
                engine._chat_warden_warned = True
                engine._log(f"Toxicity detected in lobby: '{kw}'")
                EventBus.emit("show_toast", f"Toxicity Warning: A teammate typed '{kw}'", "⚠️", "error", False)
                return
