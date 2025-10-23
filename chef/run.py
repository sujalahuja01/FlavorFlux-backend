import os
from dotenv import load_dotenv
from chef.app.app import create_app

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

chef_app = create_app()

if __name__ == "__main__":
    chef_app.run()

