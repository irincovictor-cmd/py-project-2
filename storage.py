"""Local JSON persistence and staff PIN verification."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path


class StorageError(ValueError):
    pass


SAMPLE_MENU = [
    {"id": "F001", "name": "Chicken Adobo Rice", "description": "Savory chicken with steamed rice", "price_cents": 6500, "stock": 20, "available": True, "category": "Meals", "image": "images/adobo.png"},
    {"id": "F002", "name": "Siomai Rice", "description": "Four siomai pieces served with rice", "price_cents": 5000, "stock": 20, "available": True, "category": "Meals", "image": "images/siomai.png"},
    {"id": "F003", "name": "Pancit Canton", "description": "Stir-fried noodles with vegetables", "price_cents": 3500, "stock": 15, "available": True, "category": "Meals", "image": "images/pancit.png"},
    {"id": "F004", "name": "Cheese Sandwich", "description": "Toasted sandwich with melted cheese", "price_cents": 3000, "stock": 16, "available": True, "category": "Snacks", "image": "images/sandwich.png"},
    {"id": "F005", "name": "Banana Turon", "description": "Crispy caramelized banana roll", "price_cents": 2000, "stock": 18, "available": True, "category": "Snacks", "image": "images/turon.png"},
    {"id": "F006", "name": "Iced Tea", "description": "Chilled refreshing iced tea", "price_cents": 2500, "stock": 25, "available": True, "category": "Drinks", "image": "images/iced_tea.png"},
    {"id": "F007", "name": "Bottled Water", "description": "Cold purified drinking water", "price_cents": 1500, "stock": 30, "available": True, "category": "Drinks", "image": "images/water.png"},
]

DEFAULT_DATA = {"menu": SAMPLE_MENU, "orders": [], "next_food": 7, "next_order": 0}


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".cafeteria-", suffix=".tmp", delete=False) as handle:
            temp = Path(handle.name)
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temp, path)
    except OSError as exc:
        raise StorageError(f"Unable to save {path.name}: {exc}") from exc
    finally:
        if temp and temp.exists():
            temp.unlink(missing_ok=True)


class JsonRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return json.loads(json.dumps(DEFAULT_DATA))
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not all(k in data for k in DEFAULT_DATA):
                raise ValueError("Missing required fields.")
            if not isinstance(data["menu"], list) or not isinstance(data["orders"], list):
                raise ValueError("Menu and orders must be lists.")
            if any(type(data[k]) is not int or data[k] < 0 for k in ("next_food", "next_order")):
                raise ValueError("Invalid ID counters.")
            for f in data["menu"]:
                if not isinstance(f, dict) or not all(k in f for k in ("id", "name", "description", "price_cents", "stock", "available")):
                    raise ValueError("Invalid menu item.")
                if type(f["price_cents"]) is not int or f["price_cents"] <= 0 or type(f["stock"]) is not int or f["stock"] < 0:
                    raise ValueError("Invalid menu price or stock.")
                if not isinstance(f.get("image", ""), str) or not isinstance(f.get("category", "Meals"), str):
                    raise ValueError("Invalid image or category for menu item.")
            for o in data["orders"]:
                if not isinstance(o, dict) or not all(k in o for k in ("order_id", "items", "total_cents", "status", "payment_status", "created_at")):
                    raise ValueError("Invalid order entry.")
                if not isinstance(o.get("student_id", o.get("customer")), str):
                    raise ValueError("Order must include a student ID or a legacy customer field.")
            if len({f["id"] for f in data["menu"]}) != len(data["menu"]):
                raise ValueError("Duplicate menu IDs.")
            if len({o["order_id"] for o in data["orders"]}) != len(data["orders"]):
                raise ValueError("Duplicate order IDs.")
            return data
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
            raise StorageError(f"Cannot load {self.path.name}: {exc}. Restore a valid backup before proceeding.") from exc

    def save(self, data: dict) -> None:
        atomic_json(self.path, data)


class StaffPin:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.settings = None
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or not all(isinstance(data.get(k), str) for k in ("salt", "hash")):
                    raise ValueError("Invalid settings.")
                bytes.fromhex(data["salt"])
                bytes.fromhex(data["hash"])
                self.settings = data
            except (OSError, UnicodeError, ValueError) as exc:
                raise StorageError(f"Cannot load staff settings: {exc}") from exc

    @staticmethod
    def digest(pin: str, salt: bytes) -> str:
        return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 200000).hex()

    def setup(self, pin: str) -> None:
        if self.settings is not None:
            raise StorageError("The staff PIN has already been configured.")
        if len(pin) < 4 or len(pin) > 12 or not pin.isascii() or not pin.isdigit():
            raise StorageError("Use a numeric PIN containing 4 to 12 digits.")
        salt = os.urandom(16)
        settings = {"salt": salt.hex(), "hash": self.digest(pin, salt)}
        atomic_json(self.path, settings)
        self.settings = settings

    def verify(self, pin: str) -> bool:
        if self.settings is None:
            return False
        return hmac.compare_digest(self.digest(pin, bytes.fromhex(self.settings["salt"])), self.settings["hash"])