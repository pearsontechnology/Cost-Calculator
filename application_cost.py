# namespace level costing
import kubernetes
from kubernetes import client, config
from pprint import pprint
import os
from influxdb import InfluxDBClient
from datetime import datetime, timedelta
import time
import traceback
from cluster_cost import get_cluster_cost_per_hour
from crd_costs import crd_cost_by_namespace


def insert_cost_data(influx_client, app_cost_data, debug=True, influx_write=True):
    retries = 0
    retry_limit = 5
    data = []
    for app in app_cost_data:

        fields = {
            "calc_hour": str(app["calc_hour"]),
            "cpu_usage": float(app["cpu_usage"]),
            "memory_usage": float(app["memory_usage"]),
            "pod_count": int(app["pod_count"]),
            "app_cost": float(app["app_cost"])
        }
        tags = {
            "namespace": str(app["namespace"]),
            "calc_date": str(app["calc_date"])
        }

        for key in app.keys():
            if key not in fields and key not in tags:
                fields[key] = float(app[key])
        data.append({
            "measurement": "application_cost",
            "tags": tags,
            "fields": fields
        })
    
    if not influx_write:
        pprint(data)
        return
    while retries < retry_limit:
        try:
            influx_client.write_points(data)
            print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
                'Cost Calculation(For This Hour) Inserted Successfully')
            break
        except:
            print(datetime.utcnow().strftime(
                '%Y-%m-%d %H:%M:%S') + ': ' + 'Data Insert Error. Retrying in 10 secounds')
            if debug:
                print(traceback.format_exc())
            retries += 1
            time.sleep(10)


def insert_namespace_usage(influx_client, namespace_resource_data,debug=True, influx_write=True):
    data = []
    now = datetime.now()
    retries = 0
    retry_limit = 5

    for app in namespace_resource_data:
        data.append({
            "measurement": "namespace_resource_usage",
            "tags": {
                "namespace": str(app["namespace"]),
                "calc_date": now.strftime("%Y-%m-%d")
            },
            "fields": {
                "calc_hour": int(now.hour),
                "cpu_usage": float(app["cpu_usage"]),
                "memory_usage": float(app["memory_usage"]),
                "pod_count": int(app["pod_count"])
            }
        })
    if not influx_write:
        pprint(data)
        return
    while retries < retry_limit:
        try:
            influx_client.write_points(data)
            print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
              'Namespace Resource Usage (For This Hour) Inserted Successfully')
            break
        except:
            print(datetime.utcnow().strftime(
                '%Y-%m-%d %H:%M:%S') + ': ' + 'Data Insert Error. Retrying in 10 secounds')
            if debug:
                print(traceback.format_exc())
            retries += 1
            time.sleep(10)


def get_resource_usage_by_date(influx_client, search_date,debug=True):

    result = None
    total_memory_used = 0
    total_cpu_used = 0.0
    return_data = []
    try:
        query = "SELECT * FROM namespace_resource_usage where calc_date = '" + \
            search_date.strftime("%Y-%m-%d") + \
            "' AND calc_hour = " + str(search_date.hour)
        result = influx_client.query(query)

    except:
        print(datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Past Resource Usage Read Error')
        if debug:
            print(traceback.format_exc())

    if result is not None and result.error is None:
        result_list = list(result.get_points(
            measurement="namespace_resource_usage"))
        for result_item in result_list:
            return_data.append({
                "namespace": result_item["namespace"],
                "cpu_usage": result_item["cpu_usage"],
                "memory_usage": result_item["memory_usage"],
                "pod_count": result_item["pod_count"],
                "calc_date": result_item["calc_date"],
                "calc_hour": result_item["calc_hour"],
            })
            total_memory_used += int(result_item["memory_usage"])
            total_cpu_used += float(result_item["cpu_usage"])
    elif result is not None and result.error is not None:
        raise Exception("Influxdb Error :" + str(result.error))

    return return_data, total_cpu_used, total_memory_used


# converts memory str to int
def memory_to_int(memory_str):
    int_memory = 0
    if "Ki" in memory_str or "K" in memory_str:
        arr = memory_str.split("K")
        int_memory = int(arr[0])
    elif "Mi" in memory_str or "M" in memory_str:
        arr = memory_str.split("M")
        int_memory = int(arr[0]) * 1024
    elif "Gi" in memory_str or "G" in memory_str:
        arr = memory_str.split("G")
        int_memory = int(arr[0]) * 1024 * 1024
    return int_memory


# convert cpu mi to number
def cpu_mi_convert(cpu_str):
    cpu = 0
    if "m" in cpu_str:
        cpu_arr = cpu_str.split("m")
        cpu = float(cpu_arr[0]) / 1000.0
    else:
        cpu = float(cpu_str)
    return cpu


# Goes through containers and calculated total pod resource usage
def pod_total_resource(pod,debug=True):
    pod_cpu_usage = 0
    pod_memory_usage = 0
    default_cpu = "500m"
    default_memory = "1Gi"
    try:
        for container in pod.spec.containers:
            requests = container.resources.requests
            if requests is None:
                pod_cpu_usage += cpu_mi_convert(default_cpu)
                pod_memory_usage += memory_to_int(default_memory)
            else:
                if "cpu" in requests:
                    pod_cpu_usage += cpu_mi_convert(requests["cpu"])
                else:
                    pod_cpu_usage += cpu_mi_convert(default_cpu)
                if "memory" in requests:
                    pod_memory_usage += memory_to_int(requests["memory"])
                else:
                    pod_memory_usage += memory_to_int(default_memory)
    except:
        print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') +
              ': ' + 'Pod resource calculation error ')
        if debug:
            print(traceback.format_exc())
    return (pod_cpu_usage, pod_memory_usage)


# Calculate minion total available  compute resources
def compute_total_minion_resources(corev1api,debug=True):
    minion_total_cpu = 0
    minion_total_memory = 0
    try:
        #nodes = corev1api.list_node(label_selector="role=minion")
        api_responce_nodes = corev1api.list_node(
            pretty=True, field_selector="metadata.name=minikube")
        for node in api_responce_nodes.items:
            minion_total_cpu += int(node.status.capacity["cpu"])
            minion_total_memory += memory_to_int(
                node.status.capacity["memory"])
    except:
        print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
              'Minion Total Resource Calculation Error (v1 -> listNodes)')
        if debug:
            print(traceback.format_exc())
    return (minion_total_cpu, minion_total_memory)


def do_current_resource_usage_calcultaion(influx_client, k8sv1,excluded_ns_arr,debug=True,influx_write=True):
    print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
      'Starting Current Resource Usage Calculation')
    namespace_usage_data = []
    try:

        api_responce_namespaces = k8sv1.list_namespace()
        for namespace in api_responce_namespaces.items:

            namespace_name = namespace.metadata.name

            if namespace_name in excluded_ns_arr:
                print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
                  'Namespace "' + namespace_name +'" is excluded . Skipping ')
                continue
            
            namespace_pod_count = 0
            namespace_total_cpu_usage = 0
            namespace_total_memory_usage = 0

            api_responce_pod = k8sv1.list_namespaced_pod(namespace_name)
            for pod in api_responce_pod.items:
                pod_phase = pod.status.phase
                if pod_phase == "Succeeded" or pod_phase == "Failed":
                    continue
                namespace_pod_count += 1
                total_pod_cpu, total_pod_memory = pod_total_resource(pod)
                namespace_total_cpu_usage += total_pod_cpu
                namespace_total_memory_usage += total_pod_memory

            namespace_usage_data.append({
                "namespace": namespace_name,
                "cpu_usage": namespace_total_cpu_usage,
                "memory_usage": namespace_total_memory_usage,
                "pod_count": namespace_pod_count
            })
        insert_namespace_usage(influx_client, namespace_usage_data,debug,influx_write)
    except:
        print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') +
              ': ' + 'Namespace Resource Calculatoion Error')
        if debug:
            print(traceback.format_exc())
    return


def do_past_namespace_cost_calculation(REGION, ENVIRONMENT, ENVIRONMENT_TYPE, influx_client, cost_date, total_cluster_cost,debug=True,influx_write=True):
    print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
      'Starting Past Namespace Cost Calculation')
    # ratio 50:50. as percentage
    CPU_RATIO = 50
    MEMORY_RATIO = 100 - CPU_RATIO
    app_cost_data = []
    total_cpu_used = 0
    total_memory_used = 0

    try:
        app_cost_data, total_cpu_used, total_memory_used = get_resource_usage_by_date(
            influx_client, cost_date,debug)

        if len(app_cost_data) == 0:
            print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
                  'Past data unavailable on ' + str(cost_date)+' . Skipping calculation')
        else:
            for app in app_cost_data:
                app_cpu_cost = (CPU_RATIO/100.0 * total_cluster_cost) * \
                    (float(app["cpu_usage"]) / float(total_cpu_used))
                app_memory_cost = (MEMORY_RATIO/100.0 * total_cluster_cost) * \
                    (float(app["memory_usage"]) / float(total_memory_used))
                app_total_cost = app_cpu_cost + app_memory_cost
                app.update({
                    "app_cost": app_total_cost
                })
                crd_cost = crd_cost_by_namespace(
                    REGION, ENVIRONMENT, ENVIRONMENT_TYPE, cost_date,app["namespace"],debug)
                app.update(crd_cost)

            print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') +
                  ': ' + 'Starting to Insert Data')
            insert_cost_data(influx_client, app_cost_data,debug,influx_write)
    except:
        print(traceback.format_exc())
        print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') +
              ': ' + 'Past Cost Calculatoion Error')
    return


# Main Procedure.
def main_procedure(REGION, ENVIRONMENT, ENVIRONMENT_TYPE, HOST, PORT, USER, PASSWORD, DATABASE,EX_NS_ARR,DEBUG=True,INFLUX_WRITE=True):
    
    retries = 30
    current_retry = 0

    print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
          'Influxdb Availability Check Started')
    influx_client = InfluxDBClient(HOST, PORT, USER, PASSWORD, DATABASE)
    while True:
        try:
            influx_client.ping()
            break
        except:
            current_retry += 1
            print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),": Influxdb Connection Failed. Retrying in 60 Secounds")

            if current_retry > retries:
                #Add local persistance
                return
            else:
                time.sleep(60)
    print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
          'Influxdb Availability Check Ended')

    print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
      'Past Cost and Usage Calculation(For This Hour) Started')
      
    cost_date = datetime.now() - timedelta(days=2)
    config.load_incluster_config()
    v1 = client.CoreV1Api()

    total_cluster_cost = get_cluster_cost_per_hour(
       cost_date.strftime("%Y-%m-%d"), REGION, ENVIRONMENT, ENVIRONMENT_TYPE,DEBUG)

    do_current_resource_usage_calcultaion(influx_client, v1,EX_NS_ARR,DEBUG,INFLUX_WRITE)

    do_past_namespace_cost_calculation(
       REGION, ENVIRONMENT, ENVIRONMENT_TYPE, influx_client, cost_date, total_cluster_cost)

    return