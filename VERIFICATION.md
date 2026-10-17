# Verification record

## Passed

- Read paragraph and table content from all five supplied DOCX documents and visually inspected all embedded Collectify diagrams, including the handwritten Level 2 DFDs, actual order statechart and class diagram.
- Ran 15 backend integration tests: all passed. The tests exercised an isolated in-memory SQLite database.
- Checked JavaScript syntax with Node: passed.
- Started the Flask application on localhost and verified the catalog and local styles/images in the browser.
- Signed in through the UI as buyer, seller and admin; each received the matching navigation and dashboard.
- Completed a browser purchase: item detail → cart → successful demo checkout → confirmation → seller processing → shipping with tracking → delivery. All ten lifecycle events appeared in the order history.
- Inspected the admin user/seller table and its verification, suspension and edit controls.
- Checked the homepage at desktop size and a 390 × 844 mobile viewport. No horizontal page overflow and no unloaded/broken images were observed. Inspected the mobile catalog/filter layout as well.
- Checked browser error/warning logs during verification: no entries observed.
- Verified a SQLite snapshot using the backup utility and the startup backup path.

Screenshots in `docs/screenshots/` record representative states from the original browser verification. Local databases are generated at first startup and may differ from those screenshots. Runtime state is excluded from the GitHub repository.

## Limits

The checks do not certify production security, uptime, a three-second performance SLA or load capacity. An actual MySQL/PostgreSQL instance, email provider, real payment gateway, courier API and other browser engines were not tested. Payment, recovery delivery and tracking are explicitly disclosed demo implementations. Packaging excludes session keys, databases, backups and generated uploads.

## GitHub preparation

The 15 integration tests passed again locally under Python 3.13 before publication. JavaScript syntax validation passed. A GitHub Actions workflow was added for Python 3.11 and 3.13 plus frontend syntax checks; its remote status is available in the repository Actions tab.
