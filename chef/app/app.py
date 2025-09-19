import logging
from flask import Flask, jsonify
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from chef.app.config import Config
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail, Message
import os

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
oauth = OAuth()
mail = Mail()

limiter = Limiter(
    key_func=lambda: str(current_user.get_id()) if current_user.is_authenticated else get_remote_address()
)

def create_app():
    app = Flask(__name__)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s'
    )
    CORS(app, supports_credentials = True, resources={
        r"/auth/*": {"origins": "https://flavorflux.onrender.com"},
        r"/recipes/*": {"origins": "https://flavorflux.onrender.com"}
    })
    app.config.from_object(Config)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        "DATABASE_URL",
        app.config.get("SQLALCHEMY_DATABASE_URI", "sqlite:///testdb.db")
    )

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page"
    limiter.init_app(app)
    oauth.init_app(app)
    mail.init_app(app)

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"}
    )

    from chef.app.auth.model import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from chef.app.auth.routes import auth
    app.register_blueprint(auth, url_prefix="/auth")

    from chef.app.recipes.routes import recipes
    app.register_blueprint(recipes, url_prefix="/recipes")


    return app

# $env:FLASK_APP="chef.app.app:create_app"