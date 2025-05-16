from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Initialize SQLAlchemy and Migrate
    db.init_app(app)
    migrate.init_app(app, db)

    # Import and register blueprints
    from .routes import main  # Ensure this import is not causing circular imports
    if not main.url_prefix:  # Check if the blueprint is already registered
        app.register_blueprint(main)

    return app