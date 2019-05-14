# namespace level costing
import kubernetes
from kubernetes import client, config
from pprint import pprint
import os
from influxdb import InfluxDBClient
from datetime import datetime, timedelta
import traceback


def insert_cost_data(influx_client, app_cost_data):
    data = []
    for app in app_cost_data:
        data.append({
            "measurement": "application_cost",
            "tags": {
                "namespace": str(app["namespace"]),
                "calc_date": str(app["calc_date"])
            },
            "fields": {
                "calc_hour": str(app["calc_hour"]),
                "cpu_usage": float(app["cpu_usage"]),
                "memory_usage": float(app["memory_usage"]),
                "pod_count": int(app["pod_count"]),
                "app_cost": float(app["app_cost"])
            }
        })
    try:
        influx_client.write_points(data)
        print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
               'Cost Calculation(For This Hour) Inserted Successfully')
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + \
            ': ' + 'Data Insert Error '


def insert_namespace_usage(influx_client, namespace_resource_data):
    data = []
    now = datetime.now()
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
    try:
        influx_client.write_points(data)
        print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
               'Namespace Resource Usage (For This Hour) Inserted Successfully')
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + \
            ': ' + 'Data Insert Error '


def get_resource_usage_by_date(influx_client, search_date):

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
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + \
            ': ' + 'Data Read Error'

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
    return int_memory


# convert cpu mi to number
def cpu_mi_convert(cpu_str):
    cpu = 0
    if type(cpu_str) is int:
        return cpu_str
    if "m" in cpu_str:
        cpu_int = cpu_str[0:len(cpu_str)-1]
        cpu = int(cpu_int) / 1000.0
    else:
        cpu = int(cpu_str)
    return cpu


# Goes through containers and calculated total pod resource usage
def pod_total_resource(pod):
    pod_cpu_usage = 0
    pod_memory_usage = 0
    default_cpu = "50m"
    default_memory = "100Mi"
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
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + \
            ': ' + 'Pod resource calculation error '
    return (pod_cpu_usage, pod_memory_usage)


# Calculate minion total available  compute resources
def compute_total_minion_resources(corev1api):
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
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + \
            'Minion Total Resource Calculation Error (v1 -> listNodes)'
    return (minion_total_cpu, minion_total_memory)

def do_crd_calculation():
    data = {
        "cb": 0,
        "mongo":0,
        "rds": 0,
        "neptune":0
    }
    return data

def do_current_resource_usage_calcultaion(influx_client, k8sv1):
    namespace_usage_data = []
    try:

        api_responce_namespaces = k8sv1.list_namespace()
        for namespace in api_responce_namespaces.items:

            namespace_name = namespace.metadata.name
            namespace_pod_count = 0
            namespace_total_cpu_usage = 0
            namespace_total_memory_usage = 0

            api_responce_pod = k8sv1.list_namespaced_pod(namespace_name)

            for pod in api_responce_pod.items:
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
        insert_namespace_usage(influx_client, namespace_usage_data)
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + \
            'Namespace Resource Calculatoion Error'
    return


def do_past_namespace_cost_calculation(influx_client, cost_date, total_cluster_cost):
    # ratio 50:50. as percentage
    CPU_RATIO = 50
    MEMORY_RATIO = 100 - CPU_RATIO
    app_cost_data = []
    total_cpu_used = 0
    total_memory_used = 0

    try:
        print cost_date
        app_cost_data, total_cpu_used, total_memory_used = get_resource_usage_by_date(
            influx_client, cost_date)

        if len(app_cost_data) == 0:
            print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + \
                'Past data unavailable on '+str(cost_date)+' . Skipping calculation'
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
                crd_cost = do_crd_calculation()
                app.update(crd_cost)
                
            print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') +
                   ': ' + 'Starting to Insert Data')
            pprint(app_cost_data)
            # insert_cost_data(influx_client, app_cost_data)
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + \
            'Past Cost Calculatoion Error'
    return

# Main Procedure.


def main_procedure(REGION, ENVIRONMENT, ENVIRONMENT_TYPE, HOST, PORT, USER, PASSWORD, DATABASE):

    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') +
           ': ' + 'Past Cost and Usage Calculation(For This Hour) Started')

    cost_date = datetime.now() - timedelta(days=2)
    config.load_kube_config()
    v1 = client.CoreV1Api()

    influx_client = InfluxDBClient(HOST, PORT, USER, PASSWORD, DATABASE)
    # get_cluster_cost(cost_date.strftime("%Y-%m-%d"),REGION, ENVIRONMENT, ENVIRONMENT_TYPE)
    total_cluster_cost = 500
    do_current_resource_usage_calcultaion(influx_client, v1)
    do_past_namespace_cost_calculation(
        influx_client, cost_date, total_cluster_cost)
    return
