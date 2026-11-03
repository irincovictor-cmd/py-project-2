import json
import tempfile
import unittest
from pathlib import Path

from ordering import Cafeteria, CafeteriaError, money, parse_price
from storage import JsonRepository, StaffPin, StorageError


class CafeteriaTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "cafeteria_data.json"
        self.cafe = Cafeteria(JsonRepository(self.path))
        self.adobo = self.cafe.add_food("Chicken Adobo", "Chicken with rice", "65.50", "10")
        self.water = self.cafe.add_food("Water", "Bottled", "15", "5")

    def tearDown(self):
        self.directory.cleanup()

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
            self.cafe.place_order("Student", {self.adobo: 2, self.water: 99})
        self.assertEqual(self.cafe.menu[0]["stock"], 10)
        self.assertEqual(self.cafe.orders, [])

    def test_empty_cart_and_name(self):
        with self.assertRaises(CafeteriaError):
            self.cafe.place_order("Student", {})
        with self.assertRaises(CafeteriaError):
            self.cafe.place_order(" ", {self.adobo: 1})

    def test_checkout_reserves_stock(self):
        order_id = self.cafe.place_order("Student A", {self.adobo: 2})
        self.assertEqual(order_id, "ORD-0001")
        self.assertEqual(self.cafe.menu[0]["stock"], 8)
        self.assertEqual(self.cafe.get_order(order_id)["status"], "Queued")

    def test_sequence_and_payment(self):
        oid = self.cafe.place_order("Student", {self.adobo: 1})
        self.assertEqual(self.cafe.advance(oid), "Preparing")
        self.assertEqual(self.cafe.advance(oid), "Ready for Pickup")
        self.cafe.collect(oid)
        self.assertEqual(self.cafe.get_order(oid)["status"], "Collected")
        self.assertEqual(self.cafe.get_order(oid)["payment_status"], "Paid")

    def test_cannot_collect_early(self):
        oid = self.cafe.place_order("Student", {self.adobo: 1})
        with self.assertRaises(CafeteriaError):
            self.cafe.collect(oid)

    def test_cancel_restores_reserved_stock(self):
        oid = self.cafe.place_order("Student", {self.water: 3})
        self.cafe.cancel(oid)
        self.assertEqual(self.cafe._get_food(self.water)["stock"], 5)
        self.assertEqual(self.cafe.get_order(oid)["status"], "Cancelled")
        with self.assertRaises(CafeteriaError):
            self.cafe.cancel(oid)

    def test_no_cancel_after_preparing(self):
        oid = self.cafe.place_order("Student", {self.water: 1})
        self.cafe.advance(oid)
        with self.assertRaises(CafeteriaError):
            self.cafe.cancel(oid)

    def test_persistence(self):
        self.cafe.place_order("Student", {self.adobo: 1})
        other = Cafeteria(JsonRepository(self.path))
        self.assertEqual(len(other.orders), 1)
        self.assertEqual(other.menu[0]["stock"], 9)
        self.assertEqual(other.place_order("Second", {self.water: 1}), "ORD-0002")

    def test_menu_edit_does_not_change_order_snapshot(self):
        oid = self.cafe.place_order("Student", {self.adobo: 1})
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
        self.assertEqual(self.cafe.place_order("A", {self.adobo: 1}), "ORD-0001")
        self.assertEqual(self.cafe.place_order("B", {self.adobo: 1}), "ORD-0002")

    def test_invalid_cart_type(self):
        with self.assertRaises(CafeteriaError):
            self.cafe.place_order("Student", {self.adobo: 1.5})

    def test_failed_file_write_keeps_in_memory_data(self):
        from unittest.mock import patch
        before = json.dumps(self.cafe.data, sort_keys=True)
        with patch("storage.os.replace", side_effect=OSError("blocked")):
            with self.assertRaises(StorageError):
                self.cafe.place_order("Student", {self.adobo: 1})
        self.assertEqual(json.dumps(self.cafe.data, sort_keys=True), before)


if __name__ == "__main__":
    unittest.main()