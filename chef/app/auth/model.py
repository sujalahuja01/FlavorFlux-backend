from email.policy import default

from chef.app.app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    __tablename__ = "users"

    uid = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String,unique=True, nullable=False)
    email = db.Column(db.String, nullable=False)
    password_hash = db.Column(db.String, nullable=False)
    google_login = db.Column(db.Boolean, default=False)
    favourites = db.relationship('Favourite', backref='user', lazy=True, cascade="all, delete-orphan")
    reset_token_version = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"USER: {self.username}"

    def get_id(self):
        return str(self.uid)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

