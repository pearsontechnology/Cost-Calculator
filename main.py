import os
from argparse import ArgumentParser
import time
from datetime import datetime

parser = ArgumentParser()
parser.add_argument('-dbp','--database_password',help="Influxdb password",type=str,default="mock")
args = parser.parse_args()

DEBUG = os.environ["DEBUG"] if "DEBUG" in os.environ else "true"
INFLUX_WRITE = os.environ["INFLUX_WRITE"] if os.environ["INFLUX_WRITE"] in os.environ else "true"
HOST = os.environ['DATABASE_HOST'] if "DATABASE_HOST" in os.environ else "localhost"
PORT = os.environ['DATABASE_PORT'] if "DATABASE_PORT" in os.environ else 8086
USER = os.environ['DATABASE_USER'] if "DATABASE_USER" in os.environ else "cost_admin"
PASSWORD = args.database_password
DATABASE = os.environ['DATABASE_NAME'] if "DATABASE_NAME" in os.environ else "cost_db"
ENVIRONMENT = os.environ['ENVIRONMENT'] if "ENVIRONMENT" in os.environ else "devpaas"
ENVIRONMENT_TYPE = os.environ['ENVIRONMENT_TYPE'] if "ENVIRONMENT_TYPE" in os.environ else "dev"
REGION = os.environ['REGION'] if "REGION" in os.environ else "us-east-2"
EXCLUDE_NAMESPACE = os.environ['EXCLUDE_NAMESPACE'] if "EXCLUDE_NAMESPACE" in os.environ else "kube-system:default:cost:couchbase:healthcheck-app:helm-controller:proxy:logging:efs:jaeger"
EX_NS_ARR = EXCLUDE_NAMESPACE.split(":")
DEBUG_BOOL = DEBUG == "true"
INFLUX_WRITE_BOOL = INFLUX_WRITE == "true"

print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Starting Cost Calculator')

if DEBUG_BOOL:
    print (HOST,PORT,USER,PASSWORD,DATABASE,ENVIRONMENT,REGION,ENVIRONMENT_TYPE)
    print ("Excluded Namespaces :" + str(EX_NS_ARR))
    print ("Operations Flag : DEBUG :" + str(DEBUG_BOOL))
    print ("Operations Flag : ALLOW INFLUXDB WRITE :" + str(INFLUX_WRITE_BOOL))

from application_cost import main_procedure

print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'No Import Errors -> Running Procedure')

while True:
    main_procedure(REGION,ENVIRONMENT,ENVIRONMENT_TYPE,HOST,PORT,USER,PASSWORD,DATABASE,EX_NS_ARR,DEBUG_BOOL,INFLUX_WRITE_BOOL)
    time.sleep(60*60)
