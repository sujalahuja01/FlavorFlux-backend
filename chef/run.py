import os
from dotenv import load_dotenv
from chef.app.app import create_app

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

chef_app = create_app()

if __name__ == "__main__":
    chef_app.run()

# import os
# from dotenv import load_dotenv
# from chef.app.app import create_app
# from flask_migrate import upgrade
#
# dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
# load_dotenv(dotenv_path)
#
# chef_app = create_app()
#
# # Apply migrations automatically (one-time)
# with chef_app.app_context():
#     upgrade()
#
# if __name__ == "__main__":
#     chef_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
