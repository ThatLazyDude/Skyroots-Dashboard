import os # module to interact with the operating system (think terminal)
from dotenv import load_dotenv # library to load environment variable from .env file into env. 'conda install python-dotenv'. Most secure way to keep sensitive data from source code.

load_dotenv() # This loads the variables from .env

API_KEY = os.environ.get('SEVDESK_API_KEY')
API_BASE_URL = os.environ.get('SEVDESK_BASE_URL')
DASHBOARD_USER = os.environ.get('DASHBOARD_USER')
DASHBOARD_PW = os.environ.get('DASHBOARD_PW')