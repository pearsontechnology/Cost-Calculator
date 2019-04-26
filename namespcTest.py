import ConfigParser as cp
from influxdb import InfluxDBClient
import json
from kubernetes import client, config, watch
import os
from datetime import datetime
import schedule
import requests
import time


# Get Data From Config File
config = cp.RawConfigParser()
config.read(os.path.dirname(os.path.abspath(__file__))+'/config.cfg')

# Assigning Config Data to the Variables
HOST = config.get('database', 'host')
PORT = config.get('database', 'port')
USER = config.get('database', 'user')
PASSWORD = config.get('database', 'password')
DATABASE = config.get('database', 'name')
COST = config.get('type', 'm4.2xlarge')

# Retrieving Data
client = InfluxDBClient(HOST, PORT, USER, PASSWORD, DATABASE)


# Write to File. This is helpful to write error logs and others
def writeToFile(filename, message):
    try:
        with open(filename, "a") as f:
            f.write(message+"\n")
    except:
        print "Error writing to file :" + filename + ", Message:" + message + "\n"


# Calculation function def
def per_unit_cost(runtime, cpu_limit, memory_limit, pod_id):

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
                "cost": namespace_cost,
                "TPR_cost": TPR_cost,
                "ES_cost": ES_cost,
                "pod_count": pod_count

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
    print 'Job started'

    today = datetime.today()
    timestamp_today = time.mktime(today.timetuple())
    print today

    # Get namespaces
    result = requests.get('http://localhost:8001/api/v1/namespaces')
    sresult = result.json()

    for x in sresult['items']:
        name = x['metadata']['name']
        print name
        pod_cost = 0
        sql = 'SELECT * FROM "filtered" WHERE namespace =\'' + str(name) + '\''
        pod_result = client.query(sql, epoch='ns')

        pod_result = list(pod_result.get_points(measurement="filtered"))
        pod_count = 0
        namespace_cost = 0

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

                pod_cost = per_unit_cost(total_runtime, cpu_limit, memory_limit, pod_id)
                print pod_cost

                namespace_cost = namespace_cost + pod_cost

                if end_time != 0:
                    deleteCalcData(y['time'], pod_id)
                else:
                    print 'pod is still running'
        print 'pod count =' + str(pod_count)

        insertFinalPodCalc(timestamp_today, today, name, namespace_cost, 0, 0, pod_count)

#---------------------------------------------------------------------------------------------------------------

mainProcedure()

#schedule.every().day.at("00:15").do(mainProcedure())
#while True:
 #   schedule.run_pending()
  #  time.sleep(60) # wait one minute
