import json
import tempfile
import unittest
from pathlib import Path

from ordering import Cafeteria, CafeteriaError, money, parse_price
from storage import JsonRepository, StaffPin, StorageError, DEFAULT_DATA, SAMPLE_MENU


class CafeteriaTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "cafeteria_data.json"
        JsonRepository(self.path).save({"menu": [], "orders": [], "next_food": 0, "next_order": 0})
        self.cafe = Cafeteria(JsonRepository(self.path))
        self.adobo = self.cafe.add_food("Chicken Adobo", "Chicken with rice", "65.50", "10")
        self.water = self.cafe.add_food("Water", "Bottled", "15", "5")

    def tearDown(self):
        self.directory.cleanup()

    def test_fresh_install_has_sample_food_and_images(self):
        fresh = Cafeteria(JsonRepository(Path(self.directory.name) / "fresh.json"))
        self.assertEqual(len(fresh.menu), 9)
        self.assertEqual({f["category"] for f in fresh.menu}, {"Meals", "Snacks", "Drinks"})
        for food in fresh.menu:
            self.assertTrue((Path(__file__).resolve().parents[1] / food["image"]).exists())

    def test_student_id_validation_and_lookup(self):
        oid = self.cafe.place_order("2026-0001", {self.adobo: 1})
        self.assertEqual(self.cafe.get_order(oid, "2026-0001")["student_id"], "2026-0001")
        with self.assertRaises(CafeteriaError):
            self.cafe.get_order(oid, "2026-0002")
        for identifier in ("", "abc", "Name Name", "X!Y!", "a" * 21):
            with self.subTest(identifier=identifier), self.assertRaises(CafeteriaError):
                self.cafe.place_order(identifier, {self.adobo: 1})

    def test_find_orders_by_student_id_without_order_number(self):
        first = self.cafe.place_order("2026-0001", {self.adobo: 1})
        other = self.cafe.place_order("2026-0002", {self.water: 1})
        newest = self.cafe.place_order("2026-0001", {self.water: 1})
        self.assertEqual([x["order_id"] for x in self.cafe.find_orders_by_student(" 2026-0001 ")], [newest, first])
        self.assertEqual([x["order_id"] for x in self.cafe.find_orders_by_student("2026-0002")], [other])
        self.assertEqual(self.cafe.find_orders_by_student("2026-9999"), [])
        with self.assertRaises(CafeteriaError):
            self.cafe.find_orders_by_student("??")
        reloaded = Cafeteria(JsonRepository(self.path))
        self.assertEqual(len(reloaded.find_orders_by_student("2026-0001")), 2)

    def test_upgrade_photos_preserves_history_and_removes_hotdog(self):
        from storage import SAMPLE_MENU
        repo = JsonRepository(Path(self.directory.name) / "prior_install.json")
        repo.save({"menu": [{"id": "F001", "name": "Hotdog", "description": "Fried", "price_cents": 1500, "stock": 47, "available": True, "category": "Snacks", "image": ""}], "orders": [], "next_food": 1, "next_order": 0})
        cafe = Cafeteria(repo)
        cafe.upgrade_photo_menu()
        self.assertEqual(len(cafe.menu), 9)
        self.assertEqual({f["name"] for f in cafe.menu}, {f["name"] for f in SAMPLE_MENU})
        self.assertTrue(all(f["image"].startswith("images/") for f in cafe.menu))
        cafe.upgrade_photo_menu()
        self.assertEqual(len(cafe.menu), 9)

    def test_add_and_edit_custom_image(self):
        fid = self.cafe.add_food("Mango Juice", "Cold", "35", "5", "Drinks", "images/water.png")
        self.assertEqual(self.cafe._get_food(fid)["image"], "images/water.png")
        self.cafe.edit_food(fid, "Mango", "", "30", "5", True, "Drinks", "")
        self.assertEqual(self.cafe._get_food(fid)["image"], "")

    def test_legacy_order_data_still_loads(self):
        old_order = {"order_id": "ORD-0001", "customer": "Previous Student", "items": [], "total_cents": 0,
                     "status": "Collected", "payment_status": "Paid", "created_at": "2026-01-01"}
        JsonRepository(self.path).save({"menu": [], "orders": [old_order], "next_food": 0, "next_order": 1})
        loaded = Cafeteria(JsonRepository(self.path))
        self.assertEqual(loaded.get_order("ORD-0001")["customer"], "Previous Student")

    def test_load_sample_menu_into_existing_empty_file(self):
        blank = Path(self.directory.name) / "old_blank.json"
        repo = JsonRepository(blank)
        repo.save({"menu": [], "orders": [], "next_food": 0, "next_order": 0})
        cafe = Cafeteria(repo)
        cafe.load_sample_menu()
        self.assertEqual(len(cafe.menu), 9)
        with self.assertRaises(CafeteriaError):
            cafe.load_sample_menu()

    def test_add_starter_menu_without_removing_existing_food(self):
        repo = JsonRepository(Path(self.directory.name) / "hotdog.json")
        repo.save({"menu": [{"id": "F001", "name": "Hotdog", "description": "Fried", "price_cents": 1500, "stock": 47, "available": True, "category": "Snacks", "image": ""}], "orders": [], "next_food": 1, "next_order": 0})
        cafe = Cafeteria(repo)
        self.assertEqual(cafe.load_sample_menu(), 7)
        self.assertEqual(len(cafe.menu), 8)
        self.assertEqual(cafe.menu[0]["name"], "Hotdog")
        self.assertEqual(len({food["id"] for food in cafe.menu}), 8)
        with self.assertRaises(CafeteriaError):
            cafe.load_sample_menu()

    def test_food_added(self):
        self.assertEqual(len(self.cafe.menu_for_student()), 2)
        self.assertEqual(self.cafe.menu[0]["price_cents"], 6550)

    def test_price_validation(self):
        for value in ("-1", "0", "12.123", "x", "", "1e3"):
            with self.subTest(value=value), self.assertRaises(CafeteriaError):
                parse_price(value)
        self.assertEqual(parse_price("1.5"), 150)

    def test_stock_validation(self):
        with self.assertRaises(CafeteriaError):
            self.cafe.add_food("Pancit", "", "20", "-1")

    def test_cart_totals(self):
        lines, total = self.cafe.validate_cart({self.adobo: 2, self.water: 1})
        self.assertEqual(total, 14600)
        self.assertEqual(lines[0]["subtotal_cents"], 13100)
        self.assertEqual(money(total), "₱146.00")

    def test_insufficient_stock_atomic(self):
        with self.assertRaises(CafeteriaError):
            self.cafe.place_order("2026-0001", {self.adobo: 2, self.water: 99})
        self.assertEqual(self.cafe.menu[0]["stock"], 10)
        self.assertEqual(self.cafe.orders, [])

    def test_empty_cart_and_student_id(self):
        with self.assertRaises(CafeteriaError):
            self.cafe.place_order("2026-0001", {})
        with self.assertRaises(CafeteriaError):
            self.cafe.place_order(" ", {self.adobo: 1})

    def test_checkout_reserves_stock(self):
        order_id = self.cafe.place_order("2026-0001", {self.adobo: 2})
        self.assertEqual(order_id, "ORD-0001")
        self.assertEqual(self.cafe.menu[0]["stock"], 8)
        self.assertEqual(self.cafe.get_order(order_id)["status"], "Queued")

    def test_sequence_and_payment(self):
        oid = self.cafe.place_order("2026-0001", {self.adobo: 1})
        self.assertEqual(self.cafe.advance(oid), "Preparing")
        self.assertEqual(self.cafe.advance(oid), "Ready for Pickup")
        self.cafe.collect(oid)
        self.assertEqual(self.cafe.get_order(oid)["status"], "Collected")
        self.assertEqual(self.cafe.get_order(oid)["payment_status"], "Paid")

    def test_cannot_collect_early(self):
        oid = self.cafe.place_order("2026-0001", {self.adobo: 1})
        with self.assertRaises(CafeteriaError):
            self.cafe.collect(oid)

    def test_cancel_restores_reserved_stock(self):
        oid = self.cafe.place_order("2026-0001", {self.water: 3})
        self.cafe.cancel(oid)
        self.assertEqual(self.cafe._get_food(self.water)["stock"], 5)
        self.assertEqual(self.cafe.get_order(oid)["status"], "Cancelled")
        with self.assertRaises(CafeteriaError):
            self.cafe.cancel(oid)

    def test_no_cancel_after_preparing(self):
        oid = self.cafe.place_order("2026-0001", {self.water: 1})
        self.cafe.advance(oid)
        with self.assertRaises(CafeteriaError):
            self.cafe.cancel(oid)

    def test_persistence(self):
        self.cafe.place_order("2026-0001", {self.adobo: 1})
        other = Cafeteria(JsonRepository(self.path))
        self.assertEqual(len(other.orders), 1)
        self.assertEqual(other.menu[0]["stock"], 9)
        self.assertEqual(other.place_order("2026-0002", {self.water: 1}), "ORD-0002")

    def test_menu_edit_does_not_change_order_snapshot(self):
        oid = self.cafe.place_order("2026-0001", {self.adobo: 1})
        self.cafe.edit_food(self.adobo, "Adobo Updated", "Changed", "75", "3", True)
        order = self.cafe.get_order(oid)
        self.assertEqual(order["total_cents"], 6550)
        self.assertEqual(order["items"][0]["name"], "Chicken Adobo")

    def test_disabled_or_zero_stock_not_visible(self):
        self.cafe.edit_food(self.water, "Water", "Bottled", "15", "5", False)
        self.assertEqual(len(self.cafe.menu_for_student()), 1)
        self.cafe.edit_food(self.adobo, "Adobo", "Chicken", "65.50", "0", True)
        self.assertEqual(self.cafe.menu_for_student(), [])

    def test_corrupt_json_detected(self):
        self.path.write_text("{not-valid", encoding="utf-8")
        with self.assertRaises(StorageError):
            Cafeteria(JsonRepository(self.path))

    def test_missing_order(self):
        with self.assertRaises(CafeteriaError):
            self.cafe.get_order("ORD-9999")

    def test_pin_setup_and_authentication(self):
        location = Path(self.directory.name) / "settings.json"
        pin = StaffPin(location)
        with self.assertRaises(StorageError):
            pin.setup("12")
        pin.setup("1234")
        reloaded = StaffPin(location)
        self.assertTrue(reloaded.verify("1234"))
        self.assertFalse(reloaded.verify("1235"))
        with self.assertRaises(StorageError):
            reloaded.setup("9876")

    def test_id_sequencing(self):
        self.assertEqual(self.cafe.add_food("New Food", "", "10", "1"), "F003")
        self.assertEqual(self.cafe.place_order("2026-0003", {self.adobo: 1}), "ORD-0001")
        self.assertEqual(self.cafe.place_order("2026-0004", {self.adobo: 1}), "ORD-0002")

    def test_invalid_cart_type(self):
        with self.assertRaises(CafeteriaError):
            self.cafe.place_order("2026-0001", {self.adobo: 1.5})

    def test_failed_file_write_keeps_in_memory_data(self):
        from unittest.mock import patch
        before = json.dumps(self.cafe.data, sort_keys=True)
        with patch("storage.os.replace", side_effect=OSError("blocked")):
            with self.assertRaises(StorageError):
                self.cafe.place_order("2026-0001", {self.adobo: 1})
        self.assertEqual(json.dumps(self.cafe.data, sort_keys=True), before)


if __name__ == "__main__":
    unittest.main()