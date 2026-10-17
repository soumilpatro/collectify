# Collectify

A college mini project for buying, selling and reviewing collectible and vintage objects. The interface uses HTML, CSS, JavaScript and local Bootstrap; Flask handles the backend, and SQLAlchemy stores relational data. The supplied experiments are mapped in `REQUIREMENTS.md`.

## Start on Windows

Install Python 3.11 or newer with the Python launcher enabled. Extract the entire project, then double-click `start.bat`. On the first run it creates a virtual environment and installs packages, which requires internet access. Open **http://127.0.0.1:5000**. Keep the server window open while using the website.

Alternatively, from the project directory:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

On macOS/Linux use `python3 -m venv .venv`, then `.venv/bin/python -m pip install -r requirements.txt` and `.venv/bin/python app.py`.

All styles and images are local. After package installation, the demo does not require an internet connection. Stop the server with Ctrl+C.

## Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Buyer | buyer@collectify.demo | Collectify123! |
| Seller | seller@collectify.demo | Collectify123! |
| Admin | admin@collectify.demo | Collectify123! |

Demo buttons on the login screen fill these credentials. The database is seeded only when it contains no users. Catalog items and their provenance are fictional; the product artwork is illustrative. Uploaded photos replace the illustrations on seller listings.

## Suggested presentation walkthrough

1. Sign in as the buyer. Search “camera”, filter by condition and price, view an object, save it to the wishlist, message the seller, and request an authenticity review.
2. Add an object to the cart and choose **Simulate failed payment**. Show the failed order, retained cart and unchanged stock. Check out again with **Simulate successful payment**. Show confirmation and the order event history.
3. Sign out and sign in as the seller. Read the buyer message, reply, and open incoming orders. Accept an order, dispatch it with a sample tracking reference, and mark it delivered. Show the sales report and CSV export.
4. Return as the buyer to see updates and delivery tracking. Create/edit/delete a review. Open a dispute for an order.
5. Sign in as admin. Review authenticity requests and disputes, inspect users, verify sellers, approve/reject/remove listings, manage categories, and view the overall report.
6. Register a fresh seller account, submit shop/provenance details in Profile and create a listing. Verify the seller and approve the listing as admin. Show that edited listings need approval again.
7. For cancellation, make another purchase and cancel before shipment. Show the refund status, restored stock, and cancellation history. Shipped/delivered orders cannot be cancelled.

Buyer, seller and admin screens are based on the account role. Sign out before switching roles, or use separate browser profiles. New users can register as buyer or seller; public registration never creates an admin.

## Database options

The default **SQLite** database is `instance/collectify.db`, created automatically. This simplifies a local demo. Experiment 1 lists PostgreSQL/MySQL; either can be selected without changing the application models. Create an empty database and a database user first, then set `DATABASE_URL` before startup:

```powershell
# PostgreSQL — replace the placeholders and URL-encode password special characters.
$env:DATABASE_URL = 'postgresql+psycopg://USERNAME:PASSWORD@localhost:5432/collectify'
# Or MySQL:
$env:DATABASE_URL = 'mysql+pymysql://USERNAME:PASSWORD@localhost:3306/collectify?charset=utf8mb4'
.venv\Scripts\python.exe app.py
```

The project creates its tables on startup. SQLite flows were tested; an actual MySQL/PostgreSQL server was not available in this workspace, so verify your chosen server before your presentation. Initial table creation is provided; schema changes to existing databases require a migration or a fresh development database.

## Backups

Existing SQLite databases are backed up automatically on server startup, before writes. For a snapshot while the app is running:

```powershell
.venv\Scripts\python.exe manage.py backup
```

Snapshots go to `instance/backups/`; retain them on another device for protection against disk loss. To restore, stop the app, preserve the current database, then replace `instance/collectify.db` with a selected snapshot. PostgreSQL/MySQL use the database vendor’s backup utilities; the SQLite backup command does not back up those servers. Uploaded photos must be backed up separately with `static/uploads/`.

## Test

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The 15 integration tests cover role restrictions, CSRF, hashed passwords, search, wishlist persistence, failed payments, atomic multi-item stock rollback, order lifecycle guards, single refunds, private messages, moderation, review updates, verification, disputes, reports and image validation. Tests use a separate in-memory database and do not reset the demo database. They create and remove one temporary upload.

## Project structure

| File | Responsibility |
| --- | --- |
| `app.py` | Flask entry point, database sessions, security headers and errors |
| `models.py` | UML entities and relational storage |
| `controllers.py` | DFD processes, permissions, validation and transaction logic |
| `seed.py` | Fictional demo catalog and accounts |
| `static/index.html` | Shared frontend shell |
| `static/app.js` | Buyer, seller and admin views, forms and API calls |
| `static/style.css` | Responsive Collectify styling |
| `static/vendor/bootstrap.min.css` | Vendored Bootstrap 5.3.8 stylesheet, MIT license in its header |
| `manage.py` | SQLite backup utility |
| `tests/test_flows.py` | Backend behavioral integration tests |
| `REQUIREMENTS.md` | Experiment-to-implementation mapping and documented assumptions |
| `VERIFICATION.md` | Checks performed and limits |

Prices are stored as integer paise. All cart items are reserved in one transaction. A failed transaction rolls back the entire checkout. Removed products remain in the database to preserve order history. User passwords use Werkzeug scrypt hashing; signed sessions contain only a user ID and CSRF token.

## Demo boundaries

- The payment gateway is simulated and collects no financial data. Successful payments and cancellation refunds are database records, not real transactions.
- Shipping and tracking are seller-entered, with no courier API. Authenticity is an admin documentation review, without physical certification.
- Password recovery generates a single-use token valid for 15 minutes and prints it in the local server console. Paste it into the recovery form. Replace this local delivery adapter with email delivery before deployment.
- Notifications are stored in the application; there is no SMS or email notification service. Login failures are limited per browser session; a public deployment needs shared rate limiting.
- The app runs on localhost with Flask’s development server. Production hosting, HTTPS, production credentials, monitoring and load testing are outside this local college deliverable. Set `SECRET_KEY` and `HTTPS_ONLY=1` only when deploying behind HTTPS. Do not expose the demo accounts publicly.
- AI recommendations, auctions, cryptocurrency, international shipping and price prediction are excluded by Experiment 1.

Do not delete your real project data to reset a demo. If you need a fresh presentation database, stop the server and move `instance/collectify.db` to a backup filename, then restart. Keep your session key private and out of version control.
