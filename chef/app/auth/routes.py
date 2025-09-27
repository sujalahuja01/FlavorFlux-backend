import logging
from flask_limiter.util import get_remote_address
from flask_mail import Message
from flask import Blueprint, request, jsonify, url_for, redirect, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from flask_limiter.errors import RateLimitExceeded
from urllib.parse import urlencode
from marshmallow import Schema, fields, validate, ValidationError
from chef.app.app import db, mail
from chef.app.auth.model import User
from chef.app.app import limiter, oauth
from itsdangerous import URLSafeTimedSerializer


# -------- Marshmallow Schemas for Validation --------
def no_admin(value):
    if value.lower() == "admin":
        raise validate.ValidationError("Username 'admin' is banned from the party 🚫🎉")

class SignupSchema(Schema):
    username = fields.Str(required=True, validate=[validate.Length(min=3, max=30, error="Too short, bestie 😭. Go for 3–30 letters."), no_admin])
    email = fields.Email(required=True, error_messages={"invalid": "Bruh, that doesn’t look like a valid email 🤨"})
    password = fields.Str(required=True, validate=validate.Length(min=8,
            error="Password’s gotta be 8+ characters, bestie 🔑"
))

class LoginSchema(Schema):
    identifier = fields.Str(required=True, validate=validate.Length(min=1, error="Yo, drop your username/email 👀"))
    password = fields.Str(required=True, validate=validate.Length(min=1,
            error="Don’t ghost me, type your password 😤"
))

class ChangePasswordSchema(Schema):
    new_password = fields.Str(required=True, data_key="password", validate=validate.Length(min=8,
            error="Think big. New Password’s gotta be 8+ 🧠💡"))
    confirm_password = fields.Str(required=True, validate=validate.Length(min=8), data_key="confirmPassword")

class DeleteAccountSchema(Schema):
    password = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1,
            error="Bruh, type the magic word or this account stays 🪄"
))

class PasswordResetSchema(Schema):
    password = fields.Str(required=True,  validate=validate.Length(min=8,
            error="Under 8 chars? Nah, we’re not doing that 😤🔒"))
    confirm_password = fields.Str(required=True, data_key="confirmPassword")


# -------- Utility functions  --------

def user_or_ip():
    if current_user.is_authenticated:
        return str(current_user.get_id())
    return get_remote_address()

def is_google_login(user):
    return getattr(user, "google_login", False)

def error_response(message, code):
    return jsonify({"success": False, "error": message}), code

def success_response(message, code):
    return jsonify({"success": True, "message": message}), code

def create_user(user):
    db.session.add(user)
    db.session.commit()
    logging.info(f"New user created and logged in: {user.username} (id: {user.uid})")

def update_user_pass(user, password):
    user.password_hash = generate_password_hash(password)
    db.session.commit()
    logging.info(f"User (id: {user.uid}) password updated. ")

def delete_user(user):
    uid = user.uid
    db.session.delete(user)
    db.session.commit()
    logout_user()
    logging.info(f"User account deleted: id {uid}")


#-------- Email verification --------

def get_serializer(secret_key):
    return URLSafeTimedSerializer(secret_key)

def generate_reset_token(email, secret_key, version, expires_sec=600):
    s = get_serializer(secret_key)
    return s.dumps({"email": email, "version":version }, salt="password-reset")

def verify_reset_token(token, secret_key, expires_sec=600):
    s = get_serializer(secret_key)
    try:
        data = s.loads(token, salt="password-reset", max_age=expires_sec)
        return data
    except Exception :
        return None


auth = Blueprint("auth", __name__)


#-------- Handlers --------

@auth.before_request
def require_json_global():
    if request.method in ["POST", "PUT", "PATCH"] and not request.is_json:
        return error_response("Expected JSON body", 400)

# -------- Google-login redirect  --------
@auth.route("/google-login")
def google_login():
    redirect_uri = url_for("auth.authorize", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


# -------- Google-authorization --------
@auth.route("/authorize")
def authorize():
    try:
        token = oauth.google.authorize_access_token()
        if not token:
            return error_response("Google said ‘nah’, run it back 🚫", 400)
        user_info = token.get("userinfo")
        if not user_info:
            return error_response("Failed to retrieve user info", 400)
        email = user_info.get("email")
        if not email:
            return error_response("Email not provided by Google OAuth", 400)
        email = email.lower().strip()

        basename = user_info.get("given_name", "user").strip()
        username = basename.lower() or "user"


        user = User.query.filter_by(email=email).first()
        if not user:
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{username}{counter}"
                counter += 1

            new_user = User(username=username.lower(), email=email)
            new_user.set_password("oauth-unusable-password")
            new_user.google_login = True

            try:
                create_user(new_user)
                login_user(new_user)
                session.permanent = True
                logging.info(f"Created new Google OAuth user: {username} ({email})")
            except Exception as e:
                logging.error(f"Error creating OAuth user {username}: {e}")
                return error_response("The server’s having a whole meltdown 😵‍💫", 500)

            next_url = "https://flavorflux.vercel.app/generate"

            return redirect(next_url)

        login_user(user)
        session.permanent = True
        next_url = "https://flavorflux.vercel.app/generate"

        return redirect(next_url)
    except Exception as e:
        logging.error(f"Exception during Google OAuth authorize: {e}")

        error_message = "Authentication failed. Please try again later."
        params = {"error": "oauth_failed", "message": error_message}

        next_url = "https://flavorflux.vercel.app/login"

        url_with_params = f"{next_url}?{urlencode(params)}"

        return redirect(url_with_params)


# -------- Signup --------
@auth.route("/signup", methods=["POST"])
def signup():
    try:
        data = SignupSchema().load(request.get_json())
    except ValidationError as err:
        return error_response(message=err.messages, code=400)

    username = data.get("username", "").strip().lower()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    if not username or not email or not password:
        return error_response("Fill in the blanks, bestie ✍️", 400)

    if User.query.filter((User.username == username)).first():
        return error_response("Bro thinks he’s the first 💀, username taken.", 409)

    if User.query.filter((User.email == email)).first():
        return error_response("Bro thinks he’s the first 💀, email taken.", 409)

    new_user = User(username=username, email=email)
    new_user.set_password(password)

    try:
        create_user(new_user)
    except Exception as e:
        logging.error(f"Error creating user: {e}")
        return error_response("Backend said ‘nope’ and dipped 🚪, try again", 500)

    return jsonify({
        "success":True,
        "message": "Slayed it 🚀 You’re all signed up, fam!",
        "user": {
            "id": new_user.uid,
            "name": new_user.username,
            "email": new_user.email
        }
    }), 201


# -------- Login --------
@auth.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    try:
        data = LoginSchema().load(request.get_json())
    except ValidationError as err:
        return error_response(message=err.messages, code=400)

    identifier = data.get("identifier", "").strip().lower()
    password = data.get("password", "").strip()

    if not identifier:
        return error_response("Yo, drop your username/email 👀", 400)

    user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

    if not user:
        logging.warning(f"Failed logging attempt with unknown identifier: {identifier}")
        return error_response("Nah fam, that username ain’t on the list 🚫", 401)

    DUMMY_OAUTH_PASSWORD = "oauth-unusable-password"

    if is_google_login(user):
        if user.check_password(DUMMY_OAUTH_PASSWORD) :
            logging.info(f"Google OAuth login attempt via password for username: {user.username}")
            return jsonify({
                "success":False,
                "error": "You signed up with Google, remember? Use that 🔗",
                "google_login": True
            }), 403

        if not password or password.strip() == "":
            return error_response("Don’t ghost me, type your password 😤", 400)

        if password and user.check_password(password):
            login_user(user)
            session.permanent = True
            return success_response("You’re in, rizzler 🔑✨", 200)
        return error_response("Password flopped harder than a failed TikTok 💀. Retry or hit reset?", 401)

    if not password or password.strip() == "":
        return error_response("Don’t ghost me, type your password 😤", 400)

    if user.check_password(password):
        login_user(user)
        session.permanent = True
        return success_response("You’re in, rizzler 🔑✨", 200)

    logging.warning(f"Failed login attempt for user: {user.username}")
    return error_response("Your Password flopped harder than a failed TikTok 💀. Retry or hit reset?", 401)


# -------- current logged-in user --------
@auth.route("/user")
@login_required
def logged_user():
    return jsonify({
        "success": True,
        "authenticated": True,
        "user": {
            "name": current_user.username,
            "email": current_user.email,
            "google_login": current_user.google_login
        }
    }), 200


# -------- Logout --------
@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    return success_response("Session yeeted, go touch grass 🌱🚶", 200)


# -------- Change password --------
@auth.route("/change_password", methods=["POST"])
@login_required
@limiter.limit("10 per hour", key_func=user_or_ip)
def change_password():
    try:
        data = ChangePasswordSchema().load(request.get_json())
    except ValidationError as err:
        return error_response(message=err.messages, code=400)

    current_password = request.json.get("currentPassword", "").strip()
    new_password = data.get("new_password", "").strip()
    confirm_password = data.get("confirm_password", "").strip()
    user = current_user

    if confirm_password != new_password:
        return error_response("Those passwords ain’t twins 💔", 400)

    if is_google_login(user):

        if check_password_hash(user.password_hash, new_password):
            return error_response("New password gotta be fresh, not the same old one 🔄", 400)

        update_user_pass(user, new_password)
        return success_response("Password leveled up 💪✨", 200)

    if not current_password:
        return error_response("Password field looking emptier than my bank account 💸🙃", 400)

    if check_password_hash(user.password_hash, new_password):
        return error_response("New password gotta be fresh, not the same old one 🔄", 400)

    if not check_password_hash(user.password_hash, current_password):
        return error_response("That old password ain't it chief ❌", 403)

    update_user_pass(user, new_password)
    return success_response("Password leveled up 💪✨", 200)


#-------- Limiter --------
@auth.errorhandler(RateLimitExceeded)
def rate_limit_handler(e):
    return error_response("Slow down, speedster 🚦 Too many tries, chill a bit.", 429)


# -------- Delete account --------
@auth.route("/delete", methods=["DELETE"])
@login_required
def del_user():
    try:
        data = DeleteAccountSchema().load(request.get_json())
    except ValidationError as err:
        return error_response(message=err.messages, code=400)

    user = current_user
    password = data.get("password", "").strip()

    if is_google_login(user):
        try:
            delete_user(user)
        except Exception as e:
            logging.error(f"Error deleting user {user.username}: {e}")
            return error_response("System just crashed, try again later 💥🖥️", 500)

        return success_response("Poof 💨 your account just got Thanos-snapped.", 200)

    if not password:
        return error_response("Need your password to delete, no cap 🔒", 400)

    if not check_password_hash(user.password_hash, password):
        return error_response("That password ain't it chief ❌", 403)

    try:
        delete_user(user)
    except Exception as e:
        logging.error(f"Error deleting user {user.username}: {e}")
        return error_response("System just crashed, try again later 💥🖥️", 500)

    return success_response("Your account just packed its bags and left 🧳💨", 200)


#-------- Forgot-password --------
@auth.route("/forgot_password", methods=["POST"])
def forgot_password():
    email = request.json.get("email", "").strip().lower()
    if not email:
        return error_response("Email field looking a lil empty rn 👀", 400)

    user = User.query.filter_by(email=email).first()
    if not user:
        return success_response("If we know that email, the reset link’s sliding into your inbox 📬", 200)
    token = generate_reset_token(user.email, current_app.config["SECRET_KEY"], user.reset_token_version)
    reset_url = f"http://localhost:5173/reset-password/{token}"

    msg = Message("Password Reset Request",
                 recipients=[user.email],
                 body=f"Reset your password using this link (Valid for 10 minutes): {reset_url}")
    try:
        mail.send(msg)
    except Exception as e:
        logging.error(f"Mail send failed: {e}")
        return error_response("Couldn't send reset mail rn, try later",500)
    return success_response("If we know that email, the reset link’s sliding into your inbox 📬", 200)


#-------- Reset-password --------

@auth.route("/reset_password/<token>", methods=["POST"])
def reset_password(token):
    try:
        data = PasswordResetSchema().load(request.get_json())
    except ValidationError as err:
        return error_response(message=err.messages, code=400)

    new_password = data.get("password", "").strip()
    confirm_password = data.get("confirm_password", "").strip()

    if not new_password or not confirm_password :
        return error_response("Fill in the blanks, bestie ✍️", 400)

    if confirm_password != new_password:
        return error_response("Those passwords ain’t twins 💔", 400)

    email_data = verify_reset_token(token, current_app.config["SECRET_KEY"])
    if not email_data:
        return error_response("Reset link’s sus or expired ⏳", 400)
    user = User.query.filter_by(email=email_data["email"]).first()
    if not user :
        return error_response("No user with that email 👻", 404)
    if user.reset_token_version != email_data["version"]:
        return error_response("Reset link’s been played out already 🎮❌", 400)

    user.set_password(new_password)
    user.reset_token_version += 1
    db.session.commit()
    return success_response("Password reset — you’re back in the game 🎮✨", 200)

