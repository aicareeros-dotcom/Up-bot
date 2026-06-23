import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional, List
from vars import OWNER_ID, ADMINS
import colorama
from colorama import Fore, Style

colorama.init()

DB_FILE = os.path.join(os.path.dirname(__file__), "bot_data.json")


def _load() -> dict:
    if not os.path.exists(DB_FILE):
        return {"users": [], "settings": {}}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"users": [], "settings": {}}


def _save(data: dict):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


class Database:
    def __init__(self, max_retries: int = 3, retry_delay: float = 2.0):
        self._print_startup_message()
        print(f"{Fore.GREEN}✓ Using local JSON database (no MongoDB required){Style.RESET_ALL}\n")

    def _print_startup_message(self):
        print(f"\n{Fore.CYAN}{'='*50}")
        print(f"{Fore.CYAN}🚀 ITsGOLU_UPLOADER Bot - Database Initialization")
        print(f"{'='*50}{Style.RESET_ALL}\n")

    # ── user helpers ──────────────────────────────────────────────────────────

    def get_user(self, user_id: int, bot_username: str = "ITsGOLU_UPLOADER") -> Optional[dict]:
        data = _load()
        for u in data["users"]:
            if u["user_id"] == user_id and u.get("bot_username") == bot_username:
                return u
        return None

    def is_user_authorized(self, user_id: int, bot_username: str = "ITsGOLU_UPLOADER") -> bool:
        if user_id == OWNER_ID or user_id in ADMINS:
            return True
        user = self.get_user(user_id, bot_username)
        if not user:
            return False
        expiry = user.get("expiry_date")
        if not expiry:
            return False
        if isinstance(expiry, str):
            try:
                expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                expiry = datetime.fromisoformat(expiry)
        return expiry > datetime.now()

    def add_user(self, user_id: int, name: str, days: int,
                 bot_username: str = "ITsGOLU_UPLOADER"):
        data = _load()
        expiry_date = datetime.now() + timedelta(days=days)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")

        for u in data["users"]:
            if u["user_id"] == user_id and u.get("bot_username") == bot_username:
                u["name"] = name
                u["expiry_date"] = expiry_str
                u["last_updated"] = now_str
                _save(data)
                return True, expiry_date

        data["users"].append({
            "user_id": user_id,
            "bot_username": bot_username,
            "name": name,
            "expiry_date": expiry_str,
            "added_date": now_str,
            "last_updated": now_str,
        })
        _save(data)
        return True, expiry_date

    def remove_user(self, user_id: int, bot_username: str = "ITsGOLU_UPLOADER") -> bool:
        data = _load()
        before = len(data["users"])
        data["users"] = [
            u for u in data["users"]
            if not (u["user_id"] == user_id and u.get("bot_username") == bot_username)
        ]
        _save(data)
        return len(data["users"]) < before

    def list_users(self, bot_username: str = "ITsGOLU_UPLOADER") -> List[dict]:
        data = _load()
        return [
            {"name": u.get("name"), "user_id": u["user_id"], "expiry_date": u.get("expiry_date")}
            for u in data["users"]
            if u.get("bot_username") == bot_username
        ]

    def is_admin(self, user_id: int) -> bool:
        result = user_id == OWNER_ID or user_id in ADMINS
        if result:
            print(f"{Fore.GREEN}✓ Admin/Owner {user_id} verified{Style.RESET_ALL}")
        return result

    # ── settings helpers ──────────────────────────────────────────────────────

    def get_log_channel(self, bot_username: str) -> Optional[int]:
        data = _load()
        return data.get("settings", {}).get(bot_username, {}).get("log_channel")

    def set_log_channel(self, bot_username: str, channel_id: int) -> bool:
        data = _load()
        if "settings" not in data:
            data["settings"] = {}
        if bot_username not in data["settings"]:
            data["settings"][bot_username] = {}
        data["settings"][bot_username]["log_channel"] = channel_id
        _save(data)
        return True

    def list_bot_usernames(self) -> List[str]:
        data = _load()
        names = list({u.get("bot_username", "ITsGOLU_UPLOADER") for u in data["users"]})
        return names or ["ITsGOLU_UPLOADER"]

    # ── cleanup ───────────────────────────────────────────────────────────────

    async def cleanup_expired_users(self, bot) -> int:
        data = _load()
        current_time = datetime.now()
        removed = 0
        kept = []
        for u in data["users"]:
            expiry = u.get("expiry_date")
            if expiry:
                if isinstance(expiry, str):
                    try:
                        expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        expiry = datetime.fromisoformat(expiry)
                if expiry < current_time and u["user_id"] not in ([OWNER_ID] + ADMINS):
                    try:
                        await bot.send_message(
                            u["user_id"],
                            "**⚠️ Your subscription has expired!**\n\nContact admin to renew."
                        )
                    except Exception:
                        pass
                    removed += 1
                    continue
            kept.append(u)
        data["users"] = kept
        _save(data)
        return removed

    def get_user_expiry_info(self, user_id: int, bot_username: str = "ITsGOLU_UPLOADER") -> Optional[dict]:
        user = self.get_user(user_id, bot_username)
        if not user:
            return None
        expiry = user.get("expiry_date")
        if not expiry:
            return None
        if isinstance(expiry, str):
            try:
                expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                expiry = datetime.fromisoformat(expiry)
        days_left = (expiry - datetime.now()).days
        return {
            "name": user.get("name", "Unknown"),
            "user_id": user_id,
            "expiry_date": expiry.strftime("%d-%m-%Y"),
            "days_left": days_left,
            "added_date": user.get("added_date", "Unknown"),
            "is_active": days_left > 0,
        }

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ── startup ───────────────────────────────────────────────────────────────────

print(f"\n{Fore.CYAN}{'='*50}")
print(f"🤖 Initializing ONeX_UPLOADER Bot Database")
print(f"{'='*50}{Style.RESET_ALL}\n")

db = Database()
