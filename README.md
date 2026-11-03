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
2. Under **Food Menu Management**, review the seven preloaded foods, snacks, and drinks, or add products with prices, descriptions, quantities, categories, and PNG/GIF photos.
3. Select **Switch to Student**. In **Food Menu & Cart**, select items, add quantities, adjust the cart, enter a Student ID (4–20 characters, letters/numbers/hyphens), and place an order. Note the generated order number.
4. In **Check Order Status**, look up that number together with the Student ID.
5. Switch to **Cafeteria Staff** using the PIN. Select the order and advance from **Queued** to **Preparing** to **Ready for Pickup**.
6. Choose **Confirm Payment & Collection** after receiving payment and handing over the order. The order becomes **Collected** and **Paid**.
7. Switch to Student and check the same order number again.
8. Optional: Staff can cancel a **Queued** order and automatically restore reserved stock. Orders cannot be cancelled after preparation starts.

## Data storage and limitations

The system automatically creates `cafeteria_data.json` for menu, stock, and orders, and `settings.json` for a hashed staff PIN. These files are excluded from Git to avoid uploading local data. Do not delete them if you want to preserve menu items and orders. For transferring this project to another PC with its saved state, copy both JSON files privately.

Prices are held as integer centavos to avoid floating-point rounding. All foods in a cart are validated before a checkout updates both orders and stock in a single JSON write.

This is a **single-computer simulation**, not a website or real multi-device ordering service. It does not process real electronic payments. Sample menu images are included as illustrations. Staff can select PNG/GIF files for custom products. Student IDs are identifiers, not verified school accounts. It does not claim to measure queue-time reductions.

## Project files

- `main.py`: independent Student ordering and Cafeteria Staff workspaces
- `sample_images.py`: bundled illustration assets, automatically restored if missing
- `ordering.py`: cart, totals, food, stock, and order processing rules
- `storage.py`: local JSON persistence and staff PIN hashing
- `tests/test_ordering.py`: automated business-logic tests
- `requirements.txt`: no third-party dependencies

## Version 1.1 — Starter menu and images

Seven sample products (meals, snacks and drinks) are available on a fresh installation. Their local illustration files are stored in `images/`, which must remain beside `main.py`. Use **Cafeteria Staff → Food Menu Management → Choose Image** to add or replace a food photo (PNG/GIF). Images selected by staff are copied into `images/` so they remain available after restarting. To clear an existing photo, select **Remove Image** and then **Save Selected Changes**. Product photo uploads must be at most 3000 × 3000 pixels.

Existing `cafeteria_data.json` files are preserved; starter products are created for new data stores. If you already have an empty saved menu, staff can click **Load Starter Menu (if empty)**. New orders use **Student ID**, not a name. Previously saved orders remain visible to cafeteria staff.

The ZIP includes the `images/` folder, and the GitHub source version can reconstruct the default illustrations from `sample_images.py` on first launch. User-selected custom photos are not backed up by that module.