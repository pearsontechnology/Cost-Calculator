import os
from argparse import ArgumentParser
import time
from datetime import datetime,timedelta
from influxdb import InfluxDBClient
import traceback

parser = ArgumentParser()
parser.add_argument('-dbp','--database_password',help="Influxdb password",type=str,default="mock")
args = parser.parse_args()

DEBUG = os.environ["DEBUG"] if "DEBUG" in os.environ else "true"
INFLUX_WRITE = os.environ["INFLUX_WRITE"] if "INFLUX_WRITE" in os.environ else "true"
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

def check_duplicates(influx_client):
    now = datetime.now()
    app_cost_date = now - timedelta(days=2)
    usage_duplicate = is_duplicate(influx_client,"namespace_resource_usage",now.strftime("%Y-%m-%d"),now.hour)
    cost_duplicate = is_duplicate(influx_client,"application_cost",app_cost_date.strftime("%Y-%m-%d"),"'"+str(app_cost_date.hour)+"'")
    return usage_duplicate,cost_duplicate

def is_duplicate(influx_client,measurement, calc_date,calc_hour,debug=True):
    result = None
    is_duplicate_insert = False
    try:
        query = "SELECT * FROM "+ measurement+" where calc_date = '" + calc_date + \
            "' AND calc_hour = " + str(calc_hour)
        result = influx_client.query(query)
    except:
        print(datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Read Error')
        if debug:
            print(traceback.format_exc())
    if result is not None and result.error is None:
        result_list = list(result.get_points(measurement=measurement))
        if len(result_list) > 0:
            is_duplicate_insert = True
    elif result is not None and result.error is not None:
        raise Exception("Influxdb Error :" + str(result.error))
    return is_duplicate_insert

def influxdb_connection_check(influx_client,retry_limit):
    print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +'Influxdb Availability Check Started')
    current_retry = 0
    while True:
        try:
            influx_client.ping()
            print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Influxdb Availability Check Ended')
            return True
        except:
            current_retry += 1
            print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),": Influxdb Connection Failed. Retrying in 60 Secounds")
            if current_retry > retry_limit:
                return False
            else:
                time.sleep(60)

print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Starting Cost Calculator')

if DEBUG_BOOL:
    print (HOST,PORT,USER,PASSWORD,DATABASE,ENVIRONMENT,REGION,ENVIRONMENT_TYPE)
    print ("Excluded Namespaces :" + str(EX_NS_ARR))
    print ("Operations Flag : DEBUG :" + str(DEBUG_BOOL))
    print ("Operations Flag : ALLOW INFLUXDB WRITE :" + str(INFLUX_WRITE_BOOL))

from application_cost import main_procedure

print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'No Import Errors -> Running Procedure')

influx_client = InfluxDBClient(HOST, PORT, USER, PASSWORD, DATABASE)
is_startup = True


while True:
    
    if is_startup:
        if influxdb_connection_check(influx_client,30):
            usage,cost = check_duplicates(influx_client)
            main_procedure(REGION,ENVIRONMENT,ENVIRONMENT_TYPE,EX_NS_ARR,influx_client,usage,cost,DEBUG_BOOL,INFLUX_WRITE_BOOL)
    else:
        if influxdb_connection_check(influx_client,30):
            main_procedure(REGION,ENVIRONMENT,ENVIRONMENT_TYPE,EX_NS_ARR,influx_client,False,False,DEBUG_BOOL,INFLUX_WRITE_BOOL)
    is_startup = False
    time.sleep(60*60)

