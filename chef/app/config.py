import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "devkey")

    SQLALCHEMY_DATABASE_URI =  os.environ.get("DATABASE_URL", "sqlite:///./testdb.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GOOGLE_CLIENT_ID=os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET=os.environ.get("GOOGLE_CLIENT_SECRET")

    MAIL_SERVER = "smtp.sendgrid.net"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = "apikey"
    MAIL_PASSWORD = os.environ.get("SENDGRID_API_KEY")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "fromfluxflavor@gmail.com")

    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True