import os

HOST = os.environ['DATABASE_HOST'] if "DATABASE_HOST" in os.environ else "localhost"
PORT = os.environ['DATABASE_PORT'] if "DATABASE_PORT" in os.environ else 8086
USER = os.environ['DATABASE_USER'] if "DATABASE_USER" in os.environ else "cost_admin"
PASSWORD = os.environ['DATABASE_PASSWORD'] if "DATABASE_PASSWORD" in os.environ else ""
DATABASE = os.environ['DATABASE_NAME'] if "DATABASE_NAME" in os.environ else "cost_db"
ENVIRONMENT = os.environ['ENVIRONMENT']
ENVIRONMENT_TYPE = os.environ['ENVIRONMENT_TYPE']
REGION = os.environ['REGION']

print (HOST,PORT,USER,PASSWORD,DATABASE,ENVIRONMENT,REGION,ENVIRONMENT_TYPE)
import time
from datetime import datetime
from application_cost import main_procedure

print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'No Import Errors -> Running Procedure'

while True:
    main_procedure()
    time.sleep(60*60)
