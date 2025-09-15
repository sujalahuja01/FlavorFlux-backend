from chef.app.app import db

class Favourite(db.Model):
    __tablename__ = "fav_recipes"

    rid = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.uid"))
    title = db.Column(db.String(120))
    ingredients = db.Column(db.Text)
    cuisine = db.Column(db.String(50))
    youtube_link = db.Column(db.String(200))
    steps = db.Column(db.Text)
    time = db.Column(db.Text)

