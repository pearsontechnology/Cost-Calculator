import ConfigParser as cp
from influxdb import InfluxDBClient
import json
from kubernetes import client, config, watch
import os
from datetime import datetime
import schedule
import requests
import time
import kubernetes
from es_cost import es_cost_calc
from tpr import TPRCalculation


# Get Data From Config File
config_1 = cp.RawConfigParser()
config_1.read(os.path.dirname(os.path.abspath(__file__))+'/config.cfg')

# Assigning Config Data to the Variables
HOST = os.environ['DATABASE_HOST']
PORT = os.environ['DATABASE_PORT']
USER = os.environ['DATABASE_USER']
PASSWORD = os.environ['DATABASE_PASSWORD']
DATABASE = os.environ['DATABASE_NAME']
INSTANCE_TYPE = config_1.get('type', 'instance_type')
REGION = config_1.get('regions', 'default')
REGION_NAME = config_1.get('regions', REGION)

# Retrieving Data
client = InfluxDBClient(HOST, PORT, USER, PASSWORD, DATABASE)


# Write to File. This is helpful to write error logs and others
def writeToFile(filename, message):
    try:
        with open(filename, "a") as f:
            f.write(message+"\n")
    except:
        print "Error writing to file :" + filename + ", Message:" + message + "\n"


# Get the Price of Instance (OnDemand). Example: getEC2Prices('t2.nano', 'US East (N. Virginia)') - Price calculated for 1 day
def getEC2Pricing(instanceType, location):
    global pricing
    instanceType = instanceType.strip()
    location = location.strip()
    try:
        response = pricing.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'usageType', 'Value': 'BoxUsage:'+instanceType},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'operation', 'Value': 'RunInstances'},
            ]
        )
        response = json.loads(response['PriceList'][0])['terms']['OnDemand']
        key = response.keys()[0]
        response = response[key]['priceDimensions']
        key = response.keys()[0]
        response = response[key]['pricePerUnit']['USD']
        return float(response) * 24
    except:
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Calculating Price of the instance :' + instanceType + ', Region :' + location + ', OS :Linux'
        return 0


# Calculation function def
def per_unit_cost(runtime, cpu_limit, memory_limit, pod_id, COST):

    try:

        if cpu_limit == 0:
            cpu_limit = 1
        if memory_limit == 0:
            memory_limit = 2

        cost_per_cpu = (((float(COST) * 20) / 100) / 8)
        cost_per_gb = (((float(COST) * 80) / 100) / 32)

        cpu_cost = cost_per_cpu * cpu_limit
        memory_cost = cost_per_gb * 2 * memory_limit

        total_pod_cost = (cpu_cost + memory_cost) * runtime
        return total_pod_cost

    except:
        print 'err'
        writeToFile("error-calc.log", "Error with calculating value: " + str(pod_id))


# Inserting into final calculation table
def insertFinalPodCalc(timestamp, date, namespace, namespace_cost, TPR_cost, ES_cost, pod_count):
    global client
    data = [
        {
            "measurement": "final_pod_calculation",
            "tags": {
                "namespace": str(namespace),
                "date": date

            },
            "fields": {
                "pod_cost": namespace_cost,
                "TPR_cost": TPR_cost,
                "ES_cost": ES_cost,
                "pod_count": pod_count
                #"Cost": cost

            }
        }
    ]
    try:
        client.write_points(data)
        print 'inserted event record: ' + str(timestamp) + ', ' + namespace + ' cost: ' + str(namespace_cost)

    except:
        writeToFile("error-calc.log", "Error inserting data: " + str(namespace))


# Deleting calculated data
def deleteCalcData(timestamp, pod_id):
    try:
        #global client
        sql = 'DELETE FROM "filtered" WHERE time='+str(timestamp)+' AND pod_id =\'' + str(pod_id) + '\';'
        client.query(sql)
        print 'deleted record: ' + str(pod_id)

    except:
        writeToFile("error-calc.log", "Error deleting data: " + str(pod_id))


def mainProcedure():
    print 'Job started: Cost Calculation'

    tpr = TPRCalculation()

    today = datetime.utcnow()
    timestamp_today = time.mktime(today.timetuple())
    print today

    #config.read('cluster.cfg')
    config.load_kube_config()

    v1 = kubernetes.client.CoreV1Api()
    v1.list_node()
    w = watch.Watch()

    COST = getEC2Pricing(INSTANCE_TYPE, REGION_NAME)

    #streaming namespaces
    for event in w.stream(v1.list_namespace, timeout_seconds=60):
        name = event['object'].metadata.name
        print name
        pod_cost = 0

        try:
            tpr_cost = tpr[name]

        except:
            tpr_cost = 0

        sql = 'SELECT * FROM "filtered" WHERE namespace =\'' + str(name) + '\''
        pod_result = client.query(sql, epoch='ns')

        pod_result = list(pod_result.get_points(measurement="filtered"))

        namespace_cost = 0
        pod_count = 0
        es_cost = es_cost_calc(name)

        if len(pod_result) == 0:
            print('No pods in the namespace')
            continue
        else:
            # pods = json.loads(pod_result)
            # json_string = json.dump(pods)
            # pod_list = json.loads(json_string)

            for y in pod_result:
                pod_count = pod_count + 1
                pod_id = y['pod_id']
                print'filtered pod: ' + pod_id
                start_time = int(y['start_time'])
                end_time = int(y['end_time'])
                cpu_limit = int(y['cpu_limit'])
                memory_limit = int(y['memory_limit'])

                if end_time == 0:
                    total_runtime = 24

                else:
                    if start_time < timestamp_today:
                        new_start_time = timestamp_today - 24 * 60 * 60
                        total_runtime = (end_time - new_start_time) / 3600
                    else:
                        total_runtime = (end_time - start_time) / 3600

                pod_cost = per_unit_cost(total_runtime, cpu_limit, memory_limit, pod_id, COST)
                print pod_cost

                namespace_cost = namespace_cost + pod_cost

                if end_time != 0:
                    deleteCalcData(y['time'], pod_id)
                else:
                    print 'pod is still running'
        print pod_count

        insertFinalPodCalc(timestamp_today, today, name, namespace_cost, tpr_cost, es_cost, int(pod_count))


    # ---------------------------------------------------------------------------------------------------------------

    # schedule.every().day.at("00:15").do(mainProcedure())
    # while True:
    #   schedule.run_pending()
    #  time.sleep(60) # wait one minute
