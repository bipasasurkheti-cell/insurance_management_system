# InsureCare - Insurance Management System (starter)

## Run on Windows / VS Code

1. Extract/open this folder in VS Code.
2. In the terminal run:
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env`. Change `SECRET_KEY` to a long random value.
   The starter uses SQLite by default, so PostgreSQL is not required to run the first version.
4. Start the app:
   ```powershell
   python app.py
   ```
5. Open http://127.0.0.1:5000

## Features
- Customer registration with unique customer ID
- Hashed passwords and login sessions
- Sample policies
- Customer dashboard
- Demo-only payment flow and payment history
- Claim submission
- Admin dashboard and claim status updates

## Admin setup (local development only)
Register a normal account through the website, stop the app with Ctrl+C, then run:
```powershell
python
```
At the Python prompt, run:
```python
from app import app, db, User
with app.app_context():
    user = User.query.filter_by(username="YOUR_USERNAME").first()
    user.role = "admin"
    db.session.commit()
exit()
```
Replace `YOUR_USERNAME` with the account username. Restart with `python app.py`, then log in and visit `/admin`.
Do not expose an admin role change route in a public deployment.

## PostgreSQL later
Install/run PostgreSQL and create a database. Then change DATABASE_URL in `.env` to:
`postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/insurance_db`

## Important security and business limitations
- This is a learning/starter application, not production-ready insurance software.
- Payment is simulated and does not charge money. Connect a provider's official sandbox API and verify payments server-side before using real payments.
- Before public deployment, add CSRF protection (e.g. Flask-WTF), rate limiting, email/phone verification, password reset, migrations (Flask-Migrate/Alembic), automated tests, monitoring, backups, and a security review.
- Sample plans do not provide actual insurance coverage. Real insurance sales require appropriate insurer authorization and legal/compliance review.
- Use HTTPS and a strong secret key in deployment. Never commit `.env` to version control.
