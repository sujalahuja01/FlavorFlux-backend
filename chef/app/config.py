import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "devkey")

    SQLALCHEMY_DATABASE_URI =  os.environ.get("DATABASE_URL", "sqlite:///./testdb.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GOOGLE_CLIENT_ID=os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET=os.environ.get("GOOGLE_CLIENT_SECRET")

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")

    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = False