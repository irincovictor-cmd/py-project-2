# Cafeteria Pre-Ordering and Pickup System

An offline, single-computer school cafeteria prototype made with Python Tkinter. It is separate from the Computer Laboratory Issue Reporting project.

## Requirements

- Python 3.10 or newer, with Tkinter support
- Windows or another system with Tkinter
- No database, network server, or third-party packages

## Start

From the project directory:

```powershell
python main.py
```

To run automated business-logic tests:

```powershell
python -m unittest discover -s tests -v
```

## Demo workflow

1. Open **Cafeteria Staff**; the first time, choose a numeric PIN of 4–12 digits and confirm it. Enter the PIN to access staff features.
2. Under **Food Menu Management**, create food items with prices, descriptions, and stock quantities.
3. Select **Switch to Student**. In **Food Menu & Cart**, select items, add quantities, adjust the cart, enter a name, and place an order. Note the generated order number.
4. In **Check Order Status**, look up that number.
5. Switch to **Cafeteria Staff** using the PIN. Select the order and advance from **Queued** to **Preparing** to **Ready for Pickup**.
6. Choose **Confirm Payment & Collection** after receiving payment and handing over the order. The order becomes **Collected** and **Paid**.
7. Switch to Student and check the same order number again.
8. Optional: Staff can cancel a **Queued** order and automatically restore reserved stock. Orders cannot be cancelled after preparation starts.

## Data storage and limitations

The system automatically creates `cafeteria_data.json` for menu, stock, and orders, and `settings.json` for a hashed staff PIN. These files are excluded from Git to avoid uploading local data. Do not delete them if you want to preserve menu items and orders. For transferring this project to another PC with its saved state, copy both JSON files privately.

Prices are held as integer centavos to avoid floating-point rounding. All foods in a cart are validated before a checkout updates both orders and stock in a single JSON write.

This is a **single-computer simulation**, not a website or real multi-device ordering service. It does not process real electronic payments. There are no product images or student accounts. It does not claim to measure queue-time reductions.

## Project files

- `main.py`: independent Student ordering and Cafeteria Staff workspaces
- `ordering.py`: cart, totals, food, stock, and order processing rules
- `storage.py`: local JSON persistence and staff PIN hashing
- `tests/test_ordering.py`: automated business-logic tests
- `requirements.txt`: no third-party dependencies