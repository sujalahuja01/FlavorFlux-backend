import time
import logging
from flask_limiter.errors import RateLimitExceeded
from chef.app.auth.routes import user_or_ip
from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user
from chef.app.recipes.model import Favourite
from chef.app.app import db, limiter
from chef.app.recipes.ai import call_ai


#-------- Utility functions --------

def error_response(message, code):
    return jsonify({"success": False, "error": message}), code

def success_response(message, code):
    return jsonify({"success": True, "message": message}), code


recipes = Blueprint("recipes", __name__)


# -------- Recipe generation  --------

@recipes.route("/generate", methods=["POST"])
@login_required
@limiter.limit("8 per hour", key_func=user_or_ip)
def generate_recipe():
    data = request.get_json()

    ingredients = data.get("ingredients")
    cuisine = data.get("cuisine") or None

    if not isinstance(ingredients, list) or not ingredients:
        return error_response("Ingredients must be a non-empty list", 400)

    ingredients = list({i.strip().lower() for i in ingredients if isinstance(i, str) and i.strip()})

    if not ingredients:
        return error_response("Ingredients are required", 400)

    ingredients = list(set([i.strip().lower() for i in ingredients]))

    try:
        recipe = call_ai(ingredients, cuisine)
    except Exception as e :
        return error_response("Could not generate recipe right now. Please try again", 500)

    session["last_ingredients"] = ingredients
    session["last_cuisine"] = cuisine
    session["last_recipe"] = recipe

    return success_response(recipe, 200)


# -------- Refreshing recipe  --------

@recipes.route("/refresh", methods=["POST"])
@login_required
@limiter.limit("5 per hour", key_func=user_or_ip)
def refresh_recipe():
    tries = 3
    ingredients = session.get("last_ingredients")
    cuisine = session.get("last_cuisine")
    old_recipe = session.get("last_recipe")
    previous_title = old_recipe.get("title") if isinstance(old_recipe, dict) else None

    if not ingredients:
        return error_response("No previous ingredients", 400)

    for _ in range(tries):
        try:
            new_recipe = call_ai(ingredients, cuisine, previous_title)
            if new_recipe != old_recipe:
                session["last_recipe"] = new_recipe
                return success_response(new_recipe, 200)
        except Exception as e:
            logging.error(f"Error during refresh {e}")
            time.sleep(2)

    if old_recipe:
        return success_response(old_recipe, 200)
    else:
        return error_response("could not generate a new recipe", 500)


# -------- Saving recipe  --------

@recipes.errorhandler(RateLimitExceeded)
def recipe_limit_handler(e):
    return error_response("Chill chef 🧑‍🍳, too many recipes too fast!", 429)


# -------- Saving recipe  --------

@recipes.route("/save", methods=["POST"])
@login_required
def save_recipe():
    data = request.get_json()
    recipe_data = data.get("message", {})

    required_fields = ["title", "ingredients", "cuisine", "steps"]
    if not all(field in recipe_data for field in required_fields):
        return error_response("Missing fields", 400)

    fav = Favourite(
        user_id = current_user.uid,
        title = recipe_data["title"],
        ingredients = recipe_data["ingredients"],
        cuisine = recipe_data["cuisine"],
        youtube_link = recipe_data.get("youtube_link"),
        steps = recipe_data["steps"],
        time = recipe_data["time"]
    )

    existing_fav = Favourite.query.filter_by(user_id=current_user.uid, title=recipe_data["title"]).first()
    if existing_fav:
        return error_response("Recipe already saved", 409)


    count = Favourite.query.filter_by(user_id=current_user.uid).count()
    if count < 15:
        try:
            db.session.add(fav)
            db.session.commit()
            count += 1
        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to save recipe for user {current_user.uid}: {e}")
            return error_response("Failed to save recipe", 500)

        return jsonify({"success": True, "message": "Recipe saved", "total_recipe": count}), 201

    else :
        return jsonify({"success": False, "error": "Already reached the saving limit", "total_recipe": count}), 403


# -------- Favourite recipe --------

@recipes.route("/favourite", methods=["GET"])
@login_required
def get_favourite():
    user = current_user
    favs = user.favourites

    return jsonify({
        "success": True,
        "count": len(favs),
        "message": [
            {
                "title": f.title,
                "ingredients": f.ingredients,
                "cuisine": f.cuisine,
                "youtube_link": f.youtube_link,
                "steps": f.steps,
                "id": f.rid,
                "time": f.time

            } for f in favs
        ]
    }), 200


# -------- Deleting recipe --------

@recipes.route("/favourite/<int:rid>", methods=["DELETE"])
@login_required
def delete_favourite(rid):
    fav = Favourite.query.get(rid)
    if not fav:
        return error_response("Recipe not found", 404)
    if fav.user_id != current_user.uid:
        return error_response("Unauthorized", 401)

    try:
        db.session.delete(fav)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to delete recipe for user {current_user.uid}: {e}")
        return error_response("Failed to delete recipe", 500)

    return success_response("Recipe deleted", 200)



