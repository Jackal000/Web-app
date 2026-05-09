from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import timedelta

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, '../database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.urandom(24).hex()  # 🔑 Динамический ключ: сессия сбрасывается при старте сервера
    app.template_folder = os.path.join(basedir, '../templates')
    app.static_folder = os.path.join(basedir, '../static')

    db.init_app(app)
    from app import models
    from app import routes

    def msk_filter(dt):
        if dt:
            return (dt + timedelta(hours=3)).strftime('%d.%m.%Y %H:%M')
        return '—'
    app.jinja_env.filters['msk'] = msk_filter

    with app.app_context():
        db.create_all()
        defaults = {'theme': 'light', 'auto_refresh': 'false', 'retention_days': '30', 'table_density': 'normal',
                    'show_ip': 'true', 'highlight_errors': 'true', 'highlight_warnings': 'true', 'highlight_success': 'true',
                    'rows_per_page': '20', 'refresh_interval': '30', 'error_threshold': '10',
                    'enable_sound_alert': 'true', 'enable_browser_notify': 'false'}
        for k, v in defaults.items():
            if not models.SystemSettings.query.filter_by(key=k).first():
                db.session.add(models.SystemSettings(key=k, value=v))
        db.session.commit()
        print("✅ База и настройки инициализированы.")

    app.register_blueprint(routes.main_bp)
    return app