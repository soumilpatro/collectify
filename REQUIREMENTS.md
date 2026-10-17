# Source review and implementation mapping

All five supplied DOCX files were read. Their embedded Collectify diagrams were extracted and visually inspected rather than relying on paragraph text alone. Classroom directions, submission instructions, quiz answers and unrelated examples are source material, not instructions to execute.

| Supplied document | Relevant content inspected |
| --- | --- |
| `b042_se_exp 1.docx` | Collectify problem statement; in/out of scope; functional and non-functional requirements; Python, Flask/Django, HTML/CSS/JS, Bootstrap, PostgreSQL/MySQL; ambiguities and incomplete integrations |
| `b042_se_exp 2.docx` | DFD context/Level 0, Level 1 and seven Level 2 process decompositions across five diagram images |
| `b042_se_exp 3 3.docx` | Collectify use case diagram, actors, relationships and UC-01 through UC-15 specifications |
| `b042_se_exp 5 1.docx` | Order state/transition table and actual Collectify statechart, including fulfillment, prepare/pack, notifications, payment failure and cancellation |
| `b042_se_exp 6.docx` | Actual class diagram; User/Buyer/Seller/Admin generalization; entity, boundary and control class tables; associations, aggregation and composition |

The hospital and food delivery diagrams in Experiment 3, and generic book/mail/polygon/state examples, are classroom examples outside Collectify. Experiment 6 actually contains a class diagram, despite the experiment index in Experiment 1 describing UI design. No dedicated UI mockup or ER diagram was present in these five documents. The database is derived from the class diagram and DFD data stores.

## DFD coverage

| DFD process | Subprocesses covered | Frontend and backend |
| --- | --- | --- |
| 1.0 User management | 1.1 register, 1.2 authenticate, 1.3 profile, 1.4 admin user management | Register/login/recovery/Profile/Admin Users; `/register`, `/login`, `/profile`, `/admin/users` |
| 2.0 Product management | 2.1 create listings, 2.2 upload images, 2.3 inventory, 2.4 edit product information | Seller Listings form and inventory column; `/products`, `/uploads`, `/seller/listings`; edited listings require moderation |
| 3.0 Search and browse | 3.1 search, 3.2 categories, 3.3 results, 3.4 item details | Explore filters and item detail; `/products?q=…`, `/categories`, `/products/<id>` |
| 4.0 Order management | 4.1 cart, 4.2 place order, 4.3 tracking, 4.4 cancellation, 4.5 payment | Cart/checkout/order history; `/cart`, `/checkout`, `/orders`, guarded cancellation and status endpoints |
| 5.0 Authentication and verification | 5.1 seller information, 5.2 product checks, 5.3 seller authentication, 5.4 order verification | Seller profile evidence; admin verification/moderation; buyer authenticity requests; server credential/availability/payment checks before confirmation |
| 6.0 Reviews and communication | 6.1 write review, 6.2 view reviews, 6.3 send message, 6.4 view messages | Item collector notes and private Messages; review create/update/delete; message participant restrictions |
| 7.0 Notifications and reports | 7.1 generate notifications, 7.2 send notifications, 7.3 generate reports, 7.4 view reports | In-app notification delivery, Updates screen, seller/admin reports and CSV export |

DFD DB1/DB2 are implemented as related table groups within one relational database. This preserves data flow without requiring two separate database servers.

## Use case coverage

| Use case | Implementation |
| --- | --- |
| UC-01 Register | Buyer/seller registration; validation, policy checkbox, hashed password; no public admin registration |
| UC-02 Login | Credential verification, suspension checks, session creation and role dashboard |
| UC-03 Manage Profile | Name, phone and address; seller shop/provenance evidence and resubmission |
| UC-04 Browse & Search Items | Keyword, category, condition, minimum/maximum price, authenticity filter and sorting |
| UC-05 View Item | Image, description, price, condition, year, availability, seller and reviews |
| UC-06 Manage Wishlist | Per-buyer persistent add/remove/list |
| UC-07 Place Order | Authenticated buyer, address, cart validation, atomic inventory reservation and order creation |
| UC-08 Make Payment | Explicit demo success/failure adapter; Payment entity, amount/status/method/reference recorded |
| UC-09 Order Confirmation | Confirmation event, visible order details and buyer/seller notifications |
| UC-10 Review Item | Buyer create/edit/delete rating and comment; visible alongside item. Viewed-item review permitted as specified; not represented as a verified purchase |
| UC-11 Request Authenticity Verification | Buyer request, pending queue, admin result and buyer status/notification |
| UC-12 Manage Listings | Seller create/edit/soft-remove, image upload and stock management; ownership checked |
| UC-13 Manage Orders | Seller incoming order view and sequential processing/shipping/delivery updates |
| UC-14 Verify Seller | Admin approve/reject pending seller with submitted evidence; public listing visibility requires verified active seller |
| UC-15 Manage Users | Admin view/edit name/suspend/restore non-admin accounts; admin accounts protected |

Additional Experiment 1 requirements are implemented: category create/rename/delete, listing approval/removal, sales and platform reports, buyer order disputes and administrator resolution, notifications, password recovery, and pre-shipment simulated refunds.

## Statechart coverage and guards

| State/transition | Behavior |
| --- | --- |
| Initial → Order Initiated | Catalog browsing begins the buyer journey. Recorded as the first event on checkout |
| Order Initiated → User Authenticated | Successful login; checkout rejects unauthenticated/non-buyer callers |
| User Authenticated → Item Selected | Item details and cart selection; selections revalidated at checkout |
| Item Selected → Order Placed | One order per selected product with quantity, buyer, seller, total and address |
| Order Placed → Payment Processing | Demo payment starts; event stored |
| Payment Processing → Payment Successful | Payment record successful; stock reduced atomically |
| Payment Processing → Payment Failed | Failed order preserved; stock unchanged; cart retained. Statechart terminal failure respected: retry creates a new checkout/order |
| Payment Successful → Order Confirmed | Confirmation event and in-app notifications |
| Order Confirmed → Order Processing | Owning seller accepts; buyer notified. Preparation/packing are represented by the Processing phase, not an invented extra order state |
| Order Processing → Order Shipped | Owning seller provides tracking reference; dispatch event and buyer notification saved in the same transaction |
| Order Shipped → Order Delivered | Owning seller confirms delivery; buyer notification |
| Order Placed/Confirmed/Processing → Order Cancelled | Buyer owns order, cancellation allowed before shipment, successful demo payment refunded, stock restored once |
| Shipped/Delivered/Cancelled/Failed | Cancellation rejected; skipped fulfillment states rejected |

The diagram’s parallel prepare/pack and notify actions are represented by fulfillment preparation and notification within a transaction. They are not implemented as concurrent workers because the mini project has no physical warehouse. The textual transition table includes processing cancellation while the drawing explicitly shows placed cancellation; the implementation follows the pre-shipment guard and supports confirmed/processing cancellation. Every actual order state is retained in `OrderEvent` history, even where payment states complete within one local request.

## Class diagram mapping

| Diagram element | Implementation |
| --- | --- |
| User, Buyer, Seller, Admin | User table with `role` discriminator; common attributes stored once and role-specific controller permissions. The roles implement the diagram’s specialization without duplicating user credentials across tables |
| Product | Seller/category foreign keys, name/description/price/condition/year/image/stock; availability derived from stock and approved visibility |
| Order | Buyer/seller/product links, created date, total, quantity, status, address and tracking |
| Payment | Unique order foreign key; amount/status/date/method/reference; one payment per order |
| Review | Buyer/product links; one mutable review per buyer/product, rating/comment/date |
| Wishlist | Buyer/product links and created date. Rows represent membership in a buyer’s logical wishlist |
| AuthenticityVerification | Buyer/product links; request date, status and result |
| LoginUI, ProductUI, OrderUI, PaymentUI | Named auth, catalog/detail, order dashboard and demo checkout views in `static/app.js` |
| UserController, ProductController, OrderController, PaymentController, VerificationController | Corresponding grouped controller operations in `controllers.py` |

Additional persistent entities are Category, Cart, OrderEvent, Message, Notification, Dispute and ResetToken, required by Experiment 1 and DFD subprocesses. Product removal preserves records rather than cascading historical orders; the order-payment one-to-one relationship is enforced by a unique key.

## Non-functional requirements and assumptions

| Requirement | Implementation or validation limit |
| --- | --- |
| Encrypted password storage | Passwords are one-way scrypt hashes (safer than reversible encryption) |
| Secure authentication / role access / privacy | Signed HttpOnly/SameSite sessions, CSRF tokens, server-side roles, ownership and message visibility, parameterized ORM, output escaping, image decoding/re-encoding, security headers |
| Reliable transactions | Integer paise, atomic checkout and stock reservation, conditional cancellation/status updates and rollback on failure |
| Regular backup | Automatic SQLite snapshot at server restart plus safe manual backup command. External database and uploaded-image backups are documented |
| Responsive and usable UI | Desktop/mobile layouts, shared navigation, labelled controls, keyboard focus, concise feedback and reversible edit/cancel actions |
| Fast pages/search | Local assets and filtered database queries; a small college dataset. No formal three-second SLA or load-testing claim |
| Availability/scalability | Flask/SQLAlchemy application can use MySQL/PostgreSQL; uptime and concurrency capacity depend on hosting and are not certified by a local demo |
| Maintainability | Separated models/controllers/frontend, behavioral tests, setup guide and this mapping |
| Modern browser compatibility | Browser verification performed using the available Chromium-based browser; other browser engines were not tested |

SQLite is an explicitly documented convenience default; MySQL/PostgreSQL connection support preserves the specified stack option, but neither external database was exercised here. Bootstrap is vendored locally. Payment, recovery-token delivery, in-app notifications and manual tracking are disclosed demo adapters. Vintage is treated as at least 20 years old; newer collectibles remain permitted. No unsupported rarity score is invented. Requests use admin documentation review, since physical certification is excluded. Post-shipment returns are handled as disputes, without an automated return/refund policy that the source never specified.

Excluded: live auctions, cryptocurrency, international shipping management, physical inspection/certification, AI recommendations and AI price prediction.
