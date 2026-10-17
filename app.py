"""Flask entry point. Run locally with python app.py."""
import os, secrets
from pathlib import Path
from flask import Flask, g, jsonify, request, session
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from models import Base, User

ROOT = Path(__file__).resolve().parent

def create_app(database_url=None, testing=False):
    app = Flask(__name__, static_folder='static')
    state = ROOT / 'instance'
    state.mkdir(exist_ok=True)
    secret_file = state / 'session.key'
    if not secret_file.exists():
        secret_file.write_text(secrets.token_hex(32))
    app.config.update(SECRET_KEY=os.getenv('SECRET_KEY') or secret_file.read_text(),
        TESTING=testing, MAX_CONTENT_LENGTH=5*1024*1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('HTTPS_ONLY') == '1',
        DATABASE_URL=database_url or os.getenv('DATABASE_URL', 'sqlite:///' + str(state/'collectify.db')))
    engine = create_engine(app.config['DATABASE_URL'])
    if not testing and engine.dialect.name == 'sqlite' and engine.url.database != ':memory:' and Path(engine.url.database).exists():
        from manage import backup
        backup(engine.url.database)
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine, 'connect')
        def sqlite_pragmas(conn, record):
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA busy_timeout=10000')
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    app.extensions['db_factory'] = factory
    app.extensions['engine'] = engine

    @app.before_request
    def prepare():
        g.db = factory()
        g.user = g.db.get(User, session.get('uid')) if session.get('uid') else None
        if g.user and not g.user.active:
            session.clear()
            g.user = None
        if request.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
            if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''), session.get('csrf','INVALID')):
                return jsonify(error='Please refresh the page and try again.'), 403

    @app.teardown_request
    def close(error):
        if hasattr(g, 'db'):
            g.db.rollback()
            g.db.close()

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'self'; frame-ancestors 'none'"
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(IntegrityError)
    def conflict(error):
        g.db.rollback()
        return jsonify(error='This record already exists or conflicts with an existing record.'), 409

    @app.get('/')
    def index():
        return app.send_static_file('index.html')

    from controllers import api
    app.register_blueprint(api)
    return app

if __name__ == '__main__':
    app = create_app()
    from seed import seed
    with app.extensions['db_factory']() as db:
        seed(db)
    app.run(host='127.0.0.1', port=int(os.getenv('PORT','5000')), debug=False)
