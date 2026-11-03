"""Single-computer Cafeteria Pre-Ordering and Pickup prototype."""
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from ordering import Cafeteria, CafeteriaError, money, positive_int
from storage import JsonRepository, StaffPin, StorageError

BASE = Path(__file__).resolve().parent


class CafeteriaApp:
    def __init__(self, root):
        self.root = root
        root.title("Cafeteria Pre-Ordering and Pickup")
        root.geometry("1140x730")
        root.minsize(930, 610)
        self.engine = Cafeteria(JsonRepository(BASE / "cafeteria_data.json"))
        self.staff_pin = StaffPin(BASE / "settings.json")
        self.cart = {}
        self.workspace = "student"
        self.build_student()

    def clear(self):
        for item in self.root.winfo_children():
            item.destroy()

    def heading(self, parent, title, subtitle, button_label, command):
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 15))
        heading = ttk.Frame(bar)
        heading.pack(side="left")
        ttk.Label(heading, text=title, font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(heading, text=subtitle).pack(anchor="w", pady=(4, 0))
        ttk.Button(bar, text=button_label, command=command).pack(side="right", padx=(10, 0))

    def error(self, error):
        messagebox.showerror("Action Not Completed", str(error), parent=self.root)

    def switch_to_staff(self):
        if self.staff_pin.settings is None:
            new_pin = simpledialog.askstring("Staff Setup", "Set a staff PIN (4-12 digits):", show="*", parent=self.root)
            if new_pin is None:
                return
            repeat = simpledialog.askstring("Confirm PIN", "Repeat the PIN:", show="*", parent=self.root)
            if repeat is None:
                return
            if repeat != new_pin:
                self.error("PINs do not match.")
                return
            try:
                self.staff_pin.setup(new_pin)
            except StorageError as exc:
                self.error(exc)
                return
            messagebox.showinfo("Configured", "Staff PIN saved. Enter it to open the kitchen workspace.", parent=self.root)
        pin = simpledialog.askstring("Staff Access", "Enter staff PIN:", show="*", parent=self.root)
        if pin is None:
            return
        if not self.staff_pin.verify(pin):
            self.error("Incorrect staff PIN.")
            return
        self.workspace = "staff"
        self.build_staff()

    def switch_to_student(self):
        self.workspace = "student"
        self.cart = {}
        self.build_student()

    def build_student(self):
        self.clear()
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        self.heading(outer, "Cafeteria Pre-Order", "Choose food, review your cart, and pay when you pick up.",
                     "Cafeteria Staff", self.switch_to_staff)
        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        ordering = ttk.Frame(notebook, padding=10)
        tracking = ttk.Frame(notebook, padding=16)
        notebook.add(ordering, text="Food Menu & Cart")
        notebook.add(tracking, text="Check Order Status")

        left = ttk.LabelFrame(ordering, text="Available Food", padding=10)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.food_tree = ttk.Treeview(left, columns=("name", "details", "price", "stock"), show="headings", selectmode="browse", height=12)
        for key, label, size in (("name", "Food", 180), ("details", "Description", 210),
                                 ("price", "Price", 85), ("stock", "Available", 80)):
            self.food_tree.heading(key, text=label)
            self.food_tree.column(key, width=size, minwidth=60)
        self.food_tree.pack(fill="both", expand=True)
        row = ttk.Frame(left)
        row.pack(fill="x", pady=(10, 0))
        ttk.Label(row, text="Quantity").pack(side="left")
        self.quantity = tk.StringVar(value="1")
        ttk.Spinbox(row, from_=1, to=10000, width=7, textvariable=self.quantity).pack(side="left", padx=7)
        ttk.Button(row, text="Add Selected to Cart", command=self.add_to_cart).pack(side="left", padx=5)
        ttk.Button(row, text="Refresh Menu", command=self.refresh_student).pack(side="left")

        right = ttk.LabelFrame(ordering, text="Shopping Cart", padding=10)
        right.pack(side="right", fill="both", expand=True)
        self.cart_tree = ttk.Treeview(right, columns=("name", "qty", "subtotal"), show="headings", height=12)
        for key, label, size in (("name", "Food", 180), ("qty", "Qty", 55), ("subtotal", "Subtotal", 110)):
            self.cart_tree.heading(key, text=label)
            self.cart_tree.column(key, width=size, minwidth=50)
        self.cart_tree.pack(fill="both", expand=True)
        controls = ttk.Frame(right)
        controls.pack(fill="x", pady=9)
        ttk.Button(controls, text="+1", command=lambda: self.change_cart(1)).pack(side="left", padx=(0, 4))
        ttk.Button(controls, text="-1", command=lambda: self.change_cart(-1)).pack(side="left", padx=4)
        ttk.Button(controls, text="Remove", command=self.remove_cart).pack(side="left", padx=4)
        ttk.Button(controls, text="Clear Cart", command=self.clear_cart).pack(side="left", padx=4)
        self.total_var = tk.StringVar(value=money(0))
        ttk.Label(right, text="Total: ", font=("Segoe UI", 13)).pack(anchor="e")
        ttk.Label(right, textvariable=self.total_var, font=("Segoe UI", 18, "bold")).pack(anchor="e")
        ttk.Label(right, text="Student name / nickname").pack(anchor="w", pady=(8, 3))
        self.customer = ttk.Entry(right)
        self.customer.pack(fill="x", pady=(0, 9))
        ttk.Button(right, text="Place Order (Pay at Pickup)", command=self.checkout).pack(fill="x")

        ttk.Label(tracking, text="Enter an order number to check its current status.").pack(anchor="w")
        searchbar = ttk.Frame(tracking)
        searchbar.pack(fill="x", pady=12)
        self.order_number = tk.StringVar()
        ttk.Entry(searchbar, textvariable=self.order_number, width=26).pack(side="left")
        ttk.Button(searchbar, text="Check Status", command=self.check_status).pack(side="left", padx=8)
        self.tracking_output = tk.Text(tracking, height=10, state="disabled", wrap="word")
        self.tracking_output.pack(fill="both", expand=True)
        self.refresh_student()

    def refresh_student(self):
        for row in self.food_tree.get_children():
            self.food_tree.delete(row)
        for food in self.engine.menu_for_student():
            self.food_tree.insert("", "end", iid=food["id"],
                                  values=(food["name"], food["description"], money(food["price_cents"]), food["stock"]))
        self.refresh_cart()

    def refresh_cart(self):
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)
        total = 0
        for food_id, qty in self.cart.items():
            try:
                food = self.engine._get_food(food_id)
            except CafeteriaError:
                continue
            sub = qty * food["price_cents"]
            total += sub
            self.cart_tree.insert("", "end", iid=food_id,
                                  values=(food["name"], qty, money(sub)))
        self.total_var.set(money(total))

    def add_to_cart(self):
        selection = self.food_tree.selection()
        if not selection:
            self.error("Select a food item first.")
            return
        try:
            qty = positive_int(self.quantity.get(), "Quantity")
            food_id = selection[0]
            food = self.engine._get_food(food_id)
            new_qty = self.cart.get(food_id, 0) + qty
            if new_qty > food["stock"]:
                raise CafeteriaError(f"Only {food['stock']} portion(s) are currently available.")
            self.cart[food_id] = new_qty
            self.refresh_cart()
        except CafeteriaError as exc:
            self.error(exc)

    def change_cart(self, change):
        selected = self.cart_tree.selection()
        if not selected:
            self.error("Select an item in the cart first.")
            return
        food_id = selected[0]
        next_qty = self.cart[food_id] + change
        if next_qty <= 0:
            self.cart.pop(food_id)
        else:
            food = self.engine._get_food(food_id)
            if next_qty > food["stock"]:
                self.error("Cannot exceed available stock.")
                return
            self.cart[food_id] = next_qty
        self.refresh_cart()

    def remove_cart(self):
        selected = self.cart_tree.selection()
        if selected:
            self.cart.pop(selected[0], None)
            self.refresh_cart()

    def clear_cart(self):
        self.cart.clear()
        self.refresh_cart()

    def checkout(self):
        try:
            order_id = self.engine.place_order(self.customer.get(), self.cart)
        except (CafeteriaError, StorageError) as exc:
            self.error(exc)
            return
        self.cart.clear()
        self.customer.delete(0, "end")
        self.order_number.set(order_id)
        self.refresh_student()
        messagebox.showinfo("Order Confirmed", f"Your pickup number is {order_id}.\nPay upon pickup at the cafeteria counter.", parent=self.root)

    def check_status(self):
        try:
            order = self.engine.get_order(self.order_number.get())
        except CafeteriaError as exc:
            self.error(exc)
            return
        text = (f"Order: {order['order_id']}\nName: {order['customer']}\n"
                f"Status: {order['status']}\nPayment: {order['payment_status']}\n"
                f"Total: {money(order['total_cents'])}\n\nItems:\n")
        for item in order["items"]:
            text += f"  {item['quantity']} × {item['name']} — {money(item['subtotal_cents'])}\n"
        self.tracking_output.configure(state="normal")
        self.tracking_output.delete("1.0", "end")
        self.tracking_output.insert("1.0", text)
        self.tracking_output.configure(state="disabled")

    def build_staff(self):
        self.clear()
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        self.heading(outer, "Cafeteria Kitchen & Orders", "Manage incoming orders and food availability.",
                     "Switch to Student", self.switch_to_student)
        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        queue = ttk.Frame(notebook, padding=10)
        menu = ttk.Frame(notebook, padding=10)
        notebook.add(queue, text="Kitchen Queue")
        notebook.add(menu, text="Food Menu Management")
        self.queue_tree = ttk.Treeview(queue, columns=("customer", "status", "total", "time", "payment"),
                                       show="tree headings", selectmode="browse")
        self.queue_tree.heading("#0", text="Order ID")
        self.queue_tree.column("#0", width=110, stretch=False)
        for key, label, width in (("customer", "Customer", 170), ("status", "Status", 140),
                                  ("total", "Total", 100), ("time", "Placed At", 160), ("payment", "Payment", 100)):
            self.queue_tree.heading(key, text=label)
            self.queue_tree.column(key, width=width)
        self.queue_tree.pack(fill="both", expand=True)
        self.queue_tree.bind("<<TreeviewSelect>>", lambda _: self.display_order())
        self.order_details = tk.Text(queue, height=6, state="disabled")
        self.order_details.pack(fill="x", pady=8)
        buttons = ttk.Frame(queue)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Advance Status", command=self.advance_order).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Confirm Payment & Collection", command=self.collect_order).pack(side="left", padx=8)
        ttk.Button(buttons, text="Cancel Queued Order", command=self.cancel_order).pack(side="left", padx=8)
        ttk.Button(buttons, text="Refresh", command=self.refresh_staff).pack(side="right")
        self.staff_menu = ttk.Treeview(menu, columns=("name", "details", "price", "stock", "active"), show="tree headings")
        self.staff_menu.heading("#0", text="ID")
        self.staff_menu.column("#0", width=80, stretch=False)
        for key, label, width in (("name", "Food Name", 190), ("details", "Description", 270),
                                  ("price", "Price", 105), ("stock", "Stock", 90), ("active", "Enabled", 90)):
            self.staff_menu.heading(key, text=label)
            self.staff_menu.column(key, width=width)
        self.staff_menu.pack(fill="both", expand=True)
        self.staff_menu.bind("<<TreeviewSelect>>", lambda _: self.load_food())
        form = ttk.LabelFrame(menu, text="Food Item Details", padding=10)
        form.pack(fill="x", pady=10)
        self.food_name = tk.StringVar()
        self.food_desc = tk.StringVar()
        self.food_price = tk.StringVar()
        self.food_stock = tk.StringVar(value="0")
        self.food_enabled = tk.BooleanVar(value=True)
        fields = (("Name", self.food_name, 0, 20), ("Description", self.food_desc, 1, 35),
                  ("Price (₱)", self.food_price, 2, 14), ("Stock", self.food_stock, 3, 10))
        for label, variable, col, width in fields:
            ttk.Label(form, text=label).grid(row=0, column=col, sticky="w", padx=(0, 8))
            ttk.Entry(form, textvariable=variable, width=width).grid(row=1, column=col, sticky="ew", padx=(0, 8), pady=4)
        ttk.Checkbutton(form, text="Enabled", variable=self.food_enabled).grid(row=1, column=4, sticky="w")
        actions = ttk.Frame(menu)
        actions.pack(fill="x")
        ttk.Button(actions, text="Add New Food", command=self.add_food).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Save Selected Changes", command=self.edit_food).pack(side="left", padx=8)
        ttk.Button(actions, text="Clear Form", command=self.clear_food_form).pack(side="left", padx=8)
        self.refresh_staff()

    def refresh_staff(self):
        current = self.queue_tree.selection()
        for row in self.queue_tree.get_children():
            self.queue_tree.delete(row)
        for order in reversed(self.engine.orders):
            self.queue_tree.insert("", "end", iid=order["order_id"], text=order["order_id"],
                                   values=(order["customer"], order["status"], money(order["total_cents"]),
                                           order["created_at"], order["payment_status"]))
        if current and self.queue_tree.exists(current[0]):
            self.queue_tree.selection_set(current[0])
        self.display_order()
        for row in self.staff_menu.get_children():
            self.staff_menu.delete(row)
        for food in self.engine.menu:
            self.staff_menu.insert("", "end", iid=food["id"], text=food["id"],
                                   values=(food["name"], food["description"], money(food["price_cents"]),
                                           food["stock"], "Yes" if food["available"] else "No"))

    def selected_order(self):
        selection = self.queue_tree.selection()
        if not selection:
            self.error("Select an order first.")
            return None
        return selection[0]

    def display_order(self):
        selected = self.queue_tree.selection()
        content = "Select an order to view its items."
        if selected:
            order = self.engine.get_order(selected[0])
            lines = [f"{order['order_id']} — {order['customer']} — {order['status']}"]
            lines += [f"{item['quantity']} × {item['name']} ({money(item['unit_price_cents'])} each)" for item in order["items"]]
            content = "\n".join(lines)
        self.order_details.configure(state="normal")
        self.order_details.delete("1.0", "end")
        self.order_details.insert("1.0", content)
        self.order_details.configure(state="disabled")

    def advance_order(self):
        selected = self.selected_order()
        if not selected:
            return
        try:
            next_status = self.engine.advance(selected)
        except (CafeteriaError, StorageError) as exc:
            self.error(exc)
            return
        self.refresh_staff()
        messagebox.showinfo("Updated", f"{selected}: {next_status}", parent=self.root)

    def collect_order(self):
        selected = self.selected_order()
        if not selected:
            return
        if not messagebox.askyesno("Confirm Payment", "Confirm payment was received and food was collected?", parent=self.root):
            return
        try:
            self.engine.collect(selected)
        except (CafeteriaError, StorageError) as exc:
            self.error(exc)
            return
        self.refresh_staff()

    def cancel_order(self):
        selected = self.selected_order()
        if not selected:
            return
        if not messagebox.askyesno("Cancel Order", "Cancel this queued order and restore its stock?", parent=self.root):
            return
        try:
            self.engine.cancel(selected)
        except (CafeteriaError, StorageError) as exc:
            self.error(exc)
            return
        self.refresh_staff()

    def load_food(self):
        selection = self.staff_menu.selection()
        if not selection:
            return
        food = self.engine._get_food(selection[0])
        self.food_name.set(food["name"])
        self.food_desc.set(food["description"])
        self.food_price.set(f"{food['price_cents'] / 100:.2f}")
        self.food_stock.set(str(food["stock"]))
        self.food_enabled.set(food["available"])

    def clear_food_form(self):
        for variable in (self.food_name, self.food_desc, self.food_price):
            variable.set("")
        self.food_stock.set("0")
        self.food_enabled.set(True)
        self.staff_menu.selection_remove(self.staff_menu.selection())

    def add_food(self):
        try:
            food_id = self.engine.add_food(self.food_name.get(), self.food_desc.get(),
                                           self.food_price.get(), self.food_stock.get())
            if not self.food_enabled.get():
                self.engine.edit_food(food_id, self.food_name.get(), self.food_desc.get(),
                                      self.food_price.get(), self.food_stock.get(), False)
        except (CafeteriaError, StorageError) as exc:
            self.error(exc)
            return
        self.clear_food_form()
        self.refresh_staff()

    def edit_food(self):
        selected = self.staff_menu.selection()
        if not selected:
            self.error("Select a food item to edit.")
            return
        try:
            self.engine.edit_food(selected[0], self.food_name.get(), self.food_desc.get(),
                                  self.food_price.get(), self.food_stock.get(), self.food_enabled.get())
        except (CafeteriaError, StorageError) as exc:
            self.error(exc)
            return
        self.refresh_staff()


def main():
    root = tk.Tk()
    try:
        CafeteriaApp(root)
    except (StorageError, CafeteriaError) as exc:
        messagebox.showerror("Unable to Start", str(exc), parent=root)
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()