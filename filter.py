"""
    This script is used to filter event data.
    Before running this script if already some pods are running on the cluster you have to
    delete the [application] section in config.cfg
"""
import traceback
import ConfigParser as cp
import kubernetes
from influxdb import InfluxDBClient
import json
import os
import time
from datetime import datetime
from kubernetes import client
from dateutil import parser

influxClient = None
config_file = os.path.dirname(os.path.abspath(__file__))+'/config.cfg'

def configureAll():
    global influxClient, config_file
    #####Get Data From Config File#####
    kubernetes.config.load_kube_config()
    config = cp.RawConfigParser()
    config.read(config_file)

    #####Assigning Config Data to the Variables#####
    HOST = os.environ.get('DATABASE_HOST')
    PORT = os.environ.get('DATABASE_PORT')
    USER =os.environ.get('DATABASE_USER')
    PASSWORD = os.environ.get('DATABASE_PASSWORD')
    DATABASE = os.environ.get('DATABASE_NAME')

    #####Creating Connection#####
    influxClient = InfluxDBClient(HOST, PORT, USER, PASSWORD, DATABASE)

#####Function for Filtering Data#####
def filter(timestamp, value):
    try:
        global influxClient
        data = json.loads(value)
        namespace = data['involvedObject']['namespace']
        podid = data['involvedObject']['uid']
        podname = data['involvedObject']['name']
        event = data['reason']
        if event == "Scheduled":
            cpu = getCPU(podname)
            memory = getMemory(podname)
            insertFilteredData(timestamp, podid, podname, namespace, (timestamp)/(10**9), cpu, memory) #inserting
        elif event == "Killing":
            updateFilteredData(timestamp, podid, namespace, (timestamp)/(10**9)) #Updating with end time
        elif event == "BackOff": #If its back off
            print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'BackOff Event Found for POD: ' + str(podid) + ', ' + namespace
            backOff(timestamp, podid, namespace)
        else:
            deleteEventRecord(timestamp, podid) #if other life events then delete it
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + "Error with Filtering value: "+str(value)

#####If there is an back off event data, then do the needful#####
def backOff(timestamp, podid, namespace):
    try:
        global influxClient
        sql = 'SELECT * FROM "filtered" WHERE pod_id=\''+str(podid)+'\' AND namespace=\''+str(namespace)+'\';'
        result = influxClient.query(sql, epoch='ns')
        result = list(result.get_points(measurement="filtered"))
        if len(result) == 1:
            data = [
                {
                    "measurement": "filtered-backoff",
                    "tags": {
                        "pod_id": str(podid),
                        "namespace": str(namespace),
                    },
                    "time": long(result[0]['time']),
                    "fields": {
                        "pod_name": str(result[0]['pod_name']),
                        "start_time": str(result[0]['start_time']),
                        "end_time": str(result[0]['end_time']),
                        "cpu_limit": float(result[0]['cpu_limit']),
                        "memory_limit": float(result[0]['memory_limit'])
                    }
                }
            ]
            influxClient.write_points(data)
            print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Inserted BackOff Event Data To Filtered-BackOff ' + str(podid) + ', ' + namespace
            influxClient.query('DELETE FROM "filtered" WHERE pod_id=\''+str(podid)+'\' AND namespace=\''+str(namespace)+'\'')  # DELETING FROM FILTER
            print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Deleted BackOff Event Data From Filtered ' + str(podid) + ', ' + namespace
        elif len(result) == 0:
            print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + "Error Handling BackOff Event Data. Zero results returned instead of 1(Maybe Backoff Event Data Already Deleted and Updated to filtered-backoff) " + str(podid) + ", " + str(namespace)

        deleteEventRecord(timestamp, podid) # Deleting event from the logs
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + "Got Exception While Handling BackOff Event Data: "+ str(podid) + ", " + str(namespace)

#####Function for getting CPU limit
def getCPU(pod_name):
    global influxClient
    result = influxClient.query('SELECT value FROM "cpu/limit" WHERE pod_name=\''+str(pod_name)+'\' AND type=\'pod\' ORDER BY time DESC LIMIT 1;')
    result = list(result.get_points(measurement="cpu/limit"))
    if len(result) == 0:
        return 0
    else:
        return float(result[0]['value'])/(1000)

#####Function for getting MEMORY limit in MB
def getMemory(pod_name):
    global influxClient
    result = influxClient.query('SELECT value FROM "memory/limit" WHERE pod_name=\''+str(pod_name)+'\' AND type=\'pod\' ORDER BY time DESC LIMIT 1;')
    result = list(result.get_points(measurement="memory/limit"))
    if len(result) == 0:
        return 0
    else:
        return float(result[0]['value'])/(1000**3)

#####Deleting event after processing data.#####
def deleteEventRecord(timestamp, pod_id):
    try:
        global influxClient
        sql = 'DELETE FROM "log/events" WHERE time='+str(timestamp)+' AND pod_id=\''+str(pod_id)+'\';'
        influxClient.query(sql)
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'deleted event record: ' + str(timestamp) + ', ' + pod_id
    except:
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + "Error Deleting Event Record "+ str(timestamp) + ", " + str(pod_id)

#####Delete Event Record if pod_id is null, Delete memory and cpu limit record when they are set to zero#####
def deleteUnwantedData():
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Clearing Unwanted Data...'
    global influxClient
    try:
        influxClient.query('DELETE FROM "cpu/limit" WHERE time <= now()- 2h;')  # CPU
        influxClient.query('DELETE FROM "cpu/limit" WHERE type= \'pod_container\' or type= \'ns\' or type= \'cluster\' or type= \'node\';') #CPU
        influxClient.query('DELETE FROM "memory/limit" WHERE time <= now()- 2h;')  # MEMORY
        influxClient.query('DELETE FROM "memory/limit" WHERE type= \'pod_container\' or type= \'ns\' or type= \'cluster\' or type= \'node\';') #MEMORY
        influxClient.query('DELETE FROM "log/events" WHERE pod_id=\'\';') #EVENTS

        #Delete unwanted measurements
        influxClient.query('DROP MEASUREMENT "cpu/node_allocatable";')
        influxClient.query('DROP MEASUREMENT "cpu/node_reservation";')
        influxClient.query('DROP MEASUREMENT "cpu/node_capacity";')
        influxClient.query('DROP MEASUREMENT "cpu/node_utilization";')
        influxClient.query('DROP MEASUREMENT "cpu/request";')
        influxClient.query('DROP MEASUREMENT "cpu/usage";')
        influxClient.query('DROP MEASUREMENT "cpu/usage_rate";')
        influxClient.query('DROP MEASUREMENT "disk/io_read_bytes";')
        influxClient.query('DROP MEASUREMENT "disk/io_read_bytes_rate";')
        influxClient.query('DROP MEASUREMENT "disk/io_write_bytes";')
        influxClient.query('DROP MEASUREMENT "disk/io_write_bytes_rate";')
        influxClient.query('DROP MEASUREMENT "filesystem/available";')
        influxClient.query('DROP MEASUREMENT "filesystem/inodes";')
        influxClient.query('DROP MEASUREMENT "filesystem/inodes_free";')
        influxClient.query('DROP MEASUREMENT "filesystem/limit";')
        influxClient.query('DROP MEASUREMENT "filesystem/usage";')
        influxClient.query('DROP MEASUREMENT "memory/major_page_faults";')
        influxClient.query('DROP MEASUREMENT "memory/cache";')
        influxClient.query('DROP MEASUREMENT "memory/major_page_faults_rate";')
        influxClient.query('DROP MEASUREMENT "memory/node_allocatable";')
        influxClient.query('DROP MEASUREMENT "memory/node_capacity";')
        influxClient.query('DROP MEASUREMENT "memory/node_reservation";')
        influxClient.query('DROP MEASUREMENT "memory/node_utilization";')
        influxClient.query('DROP MEASUREMENT "memory/page_faults";')
        influxClient.query('DROP MEASUREMENT "memory/page_faults_rate";')
        influxClient.query('DROP MEASUREMENT "memory/request";')
        influxClient.query('DROP MEASUREMENT "memory/rss";')
        influxClient.query('DROP MEASUREMENT "memory/usage";')
        influxClient.query('DROP MEASUREMENT "memory/working_set";')
        influxClient.query('DROP MEASUREMENT "network/rx";')
        influxClient.query('DROP MEASUREMENT "network/rx_errors";')
        influxClient.query('DROP MEASUREMENT "network/rx_errors_rate";')
        influxClient.query('DROP MEASUREMENT "network/rx_rate";')
        influxClient.query('DROP MEASUREMENT "network/tx";')
        influxClient.query('DROP MEASUREMENT "network/tx_errors";')
        influxClient.query('DROP MEASUREMENT "network/tx_errors_rate";')
        influxClient.query('DROP MEASUREMENT "network/tx_rate";')
        influxClient.query('DROP MEASUREMENT "restart_count";')
        influxClient.query('DROP MEASUREMENT "uptime";')

        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Unwanted Data Cleared'
    except:
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + "Error Deleting Null Event Record"

#####Insert filtered data After the successfull insertion it will delete data#####
def insertFilteredData(timestamp, pod_id, pod_name, namespace, start_time, cpu_limit, memory_limit):
    global influxClient
    data = [
        {
            "measurement": "filtered",
            "tags": {
                "pod_id": str(pod_id),
                "namespace": str(namespace)
            },
            "time": long(start_time)*1000000000,
            "fields": {
                "start_time": str(start_time),
                "pod_name": str(pod_name),
                "end_time": "0",
                "cpu_limit": float(cpu_limit),
                "memory_limit": float(memory_limit)
            }
        }
    ]
    try:
        influxClient.write_points(data)
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Inserted Event Record: ' + str(timestamp) + ', ' + pod_id
        deleteEventRecord(timestamp, pod_id)
    except:
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + "Error Inserting Data:" +str(pod_id)+", "+str(namespace)+", "+str(start_time)+", "+str(cpu_limit)+", "+str(memory_limit)

#####Updating event data with end time#####
def updateFilteredData(timestamp, pod_id, namespace, end_time):
    try:
        global influxClient
        #Get already stored event data(we need time to update, since influxdb does not suppport update
        sql = 'SELECT * FROM "filtered" WHERE pod_id=\''+str(pod_id)+'\' AND namespace=\''+str(namespace)+'\'; '
        result = influxClient.query(sql, epoch='ns')
        result = list(result.get_points(measurement="filtered"))
        keytime = 0
        if len(result) == 1:
            keytime = result[0]['time']
            data = [
                {
                    "measurement": "filtered",
                    "tags": {
                        "pod_id": str(pod_id),
                        "namespace": str(namespace)
                    },
                    "time": long(keytime),
                    "fields": {
                        "end_time": str(end_time)
                    }
                }
            ]
            influxClient.write_points(data)
            deleteEventRecord(timestamp, pod_id)
            print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'updated event record: ' + str(keytime) + ', ' + pod_id
        elif len(result) == 0:
            result = influxClient.query('SELECT * FROM "filtered-backoff" WHERE pod_id=\''+str(pod_id)+'\' AND namespace=\''+str(namespace)+'\'; ', epoch='ns')
            result = list(result.get_points(measurement="filtered-backoff"))
            if len(result) == 1:
                data = [
                    {
                        "measurement": "filtered",
                        "tags": {
                            "pod_id": str(pod_id),
                            "namespace": str(namespace),
                        },
                        "time": long(result[0]['time']),
                        "fields": {
                            "pod_name": str(result[0]['pod_name']),
                            "start_time": str(result[0]['start_time']),
                            "end_time": str(end_time),
                            "cpu_limit": float(result[0]['cpu_limit']),
                            "memory_limit": float(result[0]['memory_limit'])
                        }
                    }
                ]
                influxClient.write_points(data)
                print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + "Successfully Restored Data from filtered-off to filtered " + str(pod_id) + ", " + str(namespace)
            else: ### else result will be mostly zero, unless there is an error in the script
                print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + "Error updating event data(filtered-backoff) "+str(len(result))+" results returned instead of 1 while updating.(Maybe there are no event in filtered-backoff or you forgot to run startup script) " + str( pod_id) + ", " + str(namespace)
            influxClient.query('DELETE FROM "filtered-backoff" WHERE pod_id=\'' + str(pod_id) + '\' AND namespace=\'' + str(namespace) + '\'')  # DELETING FROM FILTERED-BACKOFF
        else:
            print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + "Error updating event data-More than one results returned while updating.Not going to delete this event record from logs" + str(pod_id) + ", " + str(namespace) + ", " + str(end_time)

        deleteEventRecord(timestamp, pod_id)
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + "Error updating event data: "+ str(pod_id) + ", " + str(namespace) +", " + str(end_time)

#####Convert Memory to Bytes#####
def convertMemory(memory):
    memory = str(memory)
    if len(memory) > 0: #Ensures blank input
        try:
            float(memory) #Checking specified value is Number
            return memory
        except: #if Not Number
            try:
                if memory[-2].isdigit(): #Last letter may contain measurement value
                    measure = memory[-1]
                    value = memory[:-1]
                else: # Last two letters may contain measurement value
                    measure = memory[-2:]
                    value = memory[:-2]
                value = float(value)
                if measure == 'E':
                    return value * (1000 ** 6)
                elif measure == 'Ei':
                    return value * (1024 ** 6)
                elif measure == 'P':
                    return value * (1000 ** 5)
                elif measure == 'Pi':
                    return value * (1024 ** 5)
                elif measure == 'T':
                    return value * (1000 ** 4)
                elif measure == 'Ti':
                    return value * (1024 ** 4)
                elif measure == 'G':
                    return value * (1000 ** 3)
                elif measure == 'Gi':
                    return value * (1024 ** 3)
                elif measure == 'M':
                    return value * (1000 ** 2)
                elif measure == 'Mi':
                    return value * (1024 ** 2)
                elif measure == 'K':
                    return value * (1000)
                elif measure == 'Ki':
                    return value * (1024)
                else:
                    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Not a correct measurement: ' + memory
                    return 0
            except:
                print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Not a correct value: ' + memory
                return 0
    else: #Blank input... what to do? log an error to a file
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Memory input is not greater than zero : '+ memory
        return 0

#####Convert CPU Units#####
def convertCPU(cpu):
    cpu = str(cpu)
    try:
        if cpu[-1].isdigit():
            return float(cpu)
        elif cpu[-1] == 'm':
            return (float(cpu[:-1]))/1000
        else:
            print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Memory input is not greater than zero : ' + cpu
            return 0
    except:
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Memory input is not greater than zero : ' + cpu
        return 0

##### Insert Data without deleting event data. #####
def insertData(pod_id, pod_name, namespace, start_time, cpu_limit, memory_limit):
    try:
        global influxClient
        data = [
            {
                'measurement': 'filtered',
                'tags': {
                    'pod_id': str(pod_id),
                    'namespace': str(namespace)
                },
                'time': long(start_time)*1000000000,
                'fields': {
                    'pod_name': str(pod_name),
                    'start_time': str(start_time),
                    'end_time': '0',
                    'cpu_limit': float(cpu_limit),
                    'memory_limit': float(memory_limit)
                }
            }
        ]
        influxClient.write_points(data)
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +'Inserted/Updated Event Record: ' + ', ' + str(pod_id)+', '+str(namespace)+', '+str(start_time)+', '+str(cpu_limit)+', '+str(memory_limit)
    except:
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Error Inserting/Updating Data :' +str(pod_id)+', '+str(namespace)+', '+str(start_time)+', '+str(cpu_limit)+', '+str(memory_limit)

#####This will filter the data for currently running pods. This will be executed only once# #####
def filterFirstTime():
    global influxClient
    configureAll()
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Fresh Run Started.'

    #####Gets Data#####
    v1 = client.CoreV1Api()
    data = v1.list_pod_for_all_namespaces(watch=False)

    #####Loop Through Each Item & Insert/Update Data#####
    for pod in data.items:
        id = pod.metadata.uid
        namespace = pod.metadata.namespace
        name = pod.metadata.name
        phase = pod.status.phase
        if phase == "Pending": #POD Is In PENDING Status. So there will be no Start Time when getting data from the api(Because we got start_time as None)
            continue
        start_time = int((parser.parse(str(pod.status.start_time)) - parser.parse('1970-01-01 00:00:00+00:00')).total_seconds())
        cpu = 0
        memory = 0
        status = pod.status.conditions[1].status
        for x in pod.spec.containers:
            try:
                cpu = cpu + convertCPU(x.resources.limits['cpu'])
                memory = memory + convertMemory(x.resources.limits['memory'])
            except:
                pass
        if status == 'True':  #Means pod is running without any error
            insertData(id, name, namespace, start_time, cpu, (memory / (1000 ** 3)))
        else: #Means pod is in error state. Something like CrashLoopBackOff or ImagePullBackOff, Then put it to BackOff Table
            data = [
                {
                    "measurement": "filtered-backoff",
                    "tags": {
                        "pod_id": str(id),
                        "namespace": str(namespace),
                    },
                    "time": long(start_time)*1000000000,
                    "fields": {
                        "pod_name": str(name),
                        "start_time": str(start_time),
                        "end_time": "0",
                        "cpu_limit": float(cpu),
                        "memory_limit": float(memory / (1000 ** 3))
                    }
                }
            ]
            influxClient.write_points(data)
            print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Added POD ' + str(id) + ', To Filtered-BackOff. Reason: ' + str(pod.status.conditions[1].reason)

    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Added Running POD Data'

##### This will run all other parts #####
def filteringJOB():
    global influxClient, config_file
    configureAll()
    start = time.time()
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Job Started: Filtering'

    #Check whether this is a fresh run. If it's a fresh run we have to gather data for already running pods
    config = cp.RawConfigParser()
    config.read(config_file)

    if not config.has_section('application'):
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'This is Fresh RUN'

        filterFirstTime() #running this function for first time. & we have to disable first-run in config file

        #Setting First RUN  to False in the config file
        config = cp.RawConfigParser()
        config.add_section('application')
        config.set('application', 'first-run', 'Delete This Section To Run Fresh Time Function')
        with open(config_file, 'a') as configfile:
            configfile.write('\n\n')
            config.write(configfile)
    else:
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'This Is Not a Fresh Run. Skipping Fresh Run Function'

    deleteUnwantedData()
    #####Getting Events#####
    result = influxClient.query('SELECT * FROM "log/events"', epoch='ns')
    result = list(result.get_points(measurement="log/events"))
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Processing ' + str(len(result)) + " Results from Events Data"
    for pod in result:
        filter(pod['time'], pod['value'])

    end = time.time()
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Total Execution Time: ' +str(end-start) + ' Seconds'

#####Cleans the datas on filtered-backoff table#####
def cleanupFilteredBackOff():
    configureAll()
    global influxClient
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Started Cleaning Filtered-BackOff Measurement '
    result = influxClient.query('SELECT * FROM "filtered-backoff" ', epoch='ns')
    result = list(result.get_points(measurement="filtered-backoff"))

    v1 = client.CoreV1Api()

    for pod in result:
        try:
            data = v1.read_namespaced_pod_status(str(pod['pod_name']), str(pod['namespace']))
            if pod['pod_id'] != data.metadata.uid: #Sometime there might be more than one pods with the same name (But different ID)
                influxClient.query('DELETE FROM "filtered-backoff" WHERE pod_id=\'' + str(pod['pod_id']) + '\' AND namespace=\'' + str(pod['namespace']) + '\'')
                print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Cleared Data From Filtered-BackOff ' + str(pod['pod_id'])
        except kubernetes.client.rest.ApiException:  # POD is Not Running. Delete The Data From filtered-backoff table# (Because it didn't send any termination event)
            influxClient.query('DELETE FROM "filtered-backoff" WHERE pod_id=\'' + str(pod['pod_id']) + '\' AND namespace=\'' + str(pod['namespace']) + '\'')
            print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Cleared Data From Filtered-BackOff ' + str(pod['pod_id'])
        except:
            print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Unknown Error Occured While Cleaning up From Filtered-BackOff: ' + str(pod['pod_id'])
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Finished Cleaning Filtered-BackOff Measurement '