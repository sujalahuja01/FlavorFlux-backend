import os
from dotenv import load_dotenv
from flask_migrate import upgrade, Migrate
from chef.app.app import create_app
from chef.app.app import db

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

chef_app = create_app()

with chef_app.app_context():
    Migrate(chef_app, db)
    try:
        upgrade()
        print("✅ Database upgraded successfully")
    except Exception as e:
        print("⚠️ Could not apply migrations:", e)

if __name__ == "__main__":
    chef_app.run(host="localhost", port=5000, debug=True)



    # chef.run:chef_app for render
#     Your entrypoint for Gunicorn or Render should be:
#
# text
# chef.run:chef_app
# Make sure you start from project root and use chef.run, NOT from inside chef/ or chef/app/.

