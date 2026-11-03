"""Cafeteria business logic independent of the graphical interface."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from typing import Any


class CafeteriaError(ValueError):
    pass


STATUSES = ("Queued", "Preparing", "Ready for Pickup", "Collected", "Cancelled")


def money(cents: int) -> str:
    return f"₱{cents / 100:,.2f}"


def parse_price(value: str) -> int:
    raw = value.strip()
    if not raw or raw.count(".") > 1:
        raise CafeteriaError("Enter a valid price (e.g., 65 or 65.50).")
    parts = raw.split(".")
    if not all(p.isascii() and p.isdigit() for p in parts) or (len(parts) == 2 and len(parts[1]) > 2):
        raise CafeteriaError("Enter a valid price with at most two decimal places.")
    cents = int(parts[0]) * 100 + (int(parts[1].ljust(2, "0")) if len(parts) == 2 else 0)
    if cents <= 0 or cents > 1_000_000:
        raise CafeteriaError("Price must be between ₱0.01 and ₱10,000.00.")
    return cents


def positive_int(value: str, label: str, allow_zero: bool = False) -> int:
    raw = str(value).strip()
    if not raw.isascii() or not raw.isdigit():
        raise CafeteriaError(f"{label} must be a whole number.")
    number = int(raw)
    if number < (0 if allow_zero else 1) or number > 10000:
        raise CafeteriaError(f"{label} must be between {0 if allow_zero else 1} and 10,000.")
    return number


class Cafeteria:
    def __init__(self, repository):
        self.repository = repository
        self.data = repository.load()

    @property
    def menu(self) -> list[dict[str, Any]]:
        return self.data["menu"]

    @property
    def orders(self) -> list[dict[str, Any]]:
        return self.data["orders"]

    def _commit(self, updated: dict[str, Any]) -> None:
        self.repository.save(updated)
        self.data = updated

    def _get_food(self, food_id: str, data: dict | None = None) -> dict:
        for item in (data or self.data)["menu"]:
            if item["id"] == food_id:
                return item
        raise CafeteriaError("This menu item no longer exists.")

    def load_sample_menu(self) -> None:
        if self.menu:
            raise CafeteriaError("Sample menu can be loaded only when the menu is empty.")
        from storage import SAMPLE_MENU
        data = deepcopy(self.data)
        for sample in SAMPLE_MENU:
            data["next_food"] += 1
            food = deepcopy(sample)
            food["id"] = f"F{data['next_food']:03d}"
            data["menu"].append(food)
        self._commit(data)

    def add_food(self, name: str, description: str, price: str, stock: str, category: str = "Meals", image: str = "") -> str:
        name, description = name.strip(), description.strip()
        if not name or len(name) > 60:
            raise CafeteriaError("Food name is required (maximum 60 characters).")
        if len(description) > 180:
            raise CafeteriaError("Description must be 180 characters or fewer.")
        cents = parse_price(price)
        count = positive_int(stock, "Stock", allow_zero=True)
        data = deepcopy(self.data)
        data["next_food"] += 1
        food_id = f"F{data['next_food']:03d}"
        if category not in ("Meals", "Snacks", "Drinks"):
            raise CafeteriaError("Select a valid category.")
        data["menu"].append({"id": food_id, "name": name, "description": description,
                             "price_cents": cents, "stock": count, "available": True,
                             "category": category, "image": image})
        self._commit(data)
        return food_id

    def edit_food(self, food_id: str, name: str, description: str, price: str, stock: str, available: bool, category: str | None = None, image: str | None = None) -> None:
        name, description = name.strip(), description.strip()
        if not name or len(name) > 60:
            raise CafeteriaError("Food name is required (maximum 60 characters).")
        if len(description) > 180:
            raise CafeteriaError("Description must be 180 characters or fewer.")
        cents = parse_price(price)
        count = positive_int(stock, "Stock", allow_zero=True)
        data = deepcopy(self.data)
        food = self._get_food(food_id, data)
        if category is not None and category not in ("Meals", "Snacks", "Drinks"):
            raise CafeteriaError("Select a valid category.")
        food.update(name=name, description=description, price_cents=cents,
                    stock=count, available=bool(available))
        if category is not None:
            food["category"] = category
        if image is not None:
            food["image"] = image
        self._commit(data)

    def menu_for_student(self) -> list[dict]:
        return [deepcopy(food) for food in self.menu if food["available"] and food["stock"] > 0]

    def validate_cart(self, cart: dict[str, int]) -> tuple[list[dict], int]:
        if not cart:
            raise CafeteriaError("Add at least one food item to the cart.")
        lines = []
        total = 0
        for food_id, qty in cart.items():
            if type(qty) is not int or not 1 <= qty <= 10000:
                raise CafeteriaError("Cart quantities must be positive whole numbers.")
            food = self._get_food(food_id)
            if not food["available"] or qty > food["stock"]:
                raise CafeteriaError(f"Insufficient stock for {food['name']} (available: {food['stock']}).")
            line = {"food_id": food_id, "name": food["name"], "quantity": qty,
                    "unit_price_cents": food["price_cents"], "subtotal_cents": food["price_cents"] * qty}
            lines.append(line)
            total += line["subtotal_cents"]
        return lines, total

    def place_order(self, student_id: str, cart: dict[str, int]) -> str:
        student_id = student_id.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{3,19}", student_id):
            raise CafeteriaError("Student ID must be 4–20 letters, numbers, or hyphens (no spaces).")
        lines, total = self.validate_cart(cart)
        data = deepcopy(self.data)
        for line in lines:
            self._get_food(line["food_id"], data)["stock"] -= line["quantity"]
        data["next_order"] += 1
        order_id = f"ORD-{data['next_order']:04d}"
        data["orders"].append({"order_id": order_id, "student_id": student_id,
                               "items": lines, "total_cents": total, "status": "Queued",
                               "payment_status": "Unpaid", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                               "completed_at": ""})
        self._commit(data)
        return order_id

    def get_order(self, order_id: str, student_id: str | None = None) -> dict:
        for order in self.orders:
            if order["order_id"].casefold() == order_id.strip().casefold():
                if student_id is not None and order.get("student_id", "").casefold() != student_id.strip().casefold():
                    raise CafeteriaError("Order number and Student ID do not match.")
                return deepcopy(order)
        raise CafeteriaError("Order number not found.")

    def advance(self, order_id: str) -> str:
        transitions = {"Queued": "Preparing", "Preparing": "Ready for Pickup"}
        data = deepcopy(self.data)
        order = next((o for o in data["orders"] if o["order_id"] == order_id), None)
        if order is None:
            raise CafeteriaError("Select an existing order.")
        if order["status"] not in transitions:
            raise CafeteriaError("This order cannot advance further with this action.")
        order["status"] = transitions[order["status"]]
        self._commit(data)
        return order["status"]

    def collect(self, order_id: str) -> None:
        data = deepcopy(self.data)
        order = next((o for o in data["orders"] if o["order_id"] == order_id), None)
        if order is None or order["status"] != "Ready for Pickup":
            raise CafeteriaError("Only Ready for Pickup orders can be collected.")
        order["status"] = "Collected"
        order["payment_status"] = "Paid"
        order["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._commit(data)

    def cancel(self, order_id: str) -> None:
        data = deepcopy(self.data)
        order = next((o for o in data["orders"] if o["order_id"] == order_id), None)
        if order is None or order["status"] != "Queued":
            raise CafeteriaError("Only Queued orders can be cancelled.")
        for line in order["items"]:
            self._get_food(line["food_id"], data)["stock"] += line["quantity"]
        order["status"] = "Cancelled"
        self._commit(data)