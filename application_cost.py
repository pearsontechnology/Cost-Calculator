# namespace level costing
import kubernetes
from kubernetes import client, config
from pprint import pprint
import os
from influxdb import InfluxDBClient

config.load_kube_config()
v1 = client.CoreV1Api()

# Mock Cost. will be added EC2 and non EC2
total_cluster_cost = 500

HOST = os.environ['DATABASE_HOST'] if "DATABASE_HOST" in os.environ else "localhost"
PORT = os.environ['DATABASE_PORT'] if "DATABASE_PORT" in os.environ else 8086
USER = os.environ['DATABASE_USER'] if "DATABASE_USER" in os.environ else ""
PASSWORD = os.environ['DATABASE_PASSWORD'] if "DATABASE_PASSWORD" in os.environ else ""
DATABASE = os.environ['DATABASE_NAME'] if "DATABASE_NAME" in os.environ else "cost_db"

# creating influx client
influx_client = InfluxDBClient(HOST, PORT, USER, PASSWORD, DATABASE)



#strict typed insert into influxdb
def insert_cost_data(influx_client, app_cost_data):
    data = []
    for app in app_cost_data:
        data.append({
            "measurement": "application_cost",
            "tags": {
                "namespace": str(app["namespace"])
            },
            "fields": {
                "cpu_usage": float(app["cpu_usage"]),
                "memory_usage": float(app["memory_usage"]),
                "pod_count": int(app["pod_count"]),
                "app_cost": float(app["app_cost"])
            }
        })
    try:
        influx_client.write_points(data)
    except Exception as e:
        print "Data Insert Error :" + e.message



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
    except Exception as e:
        print "Pod resource calculation error " + e.message
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
    except Exception as e:
        print "Minion Total Resource Calculation Error (v1 -> listNodes) :" + e
    return (minion_total_cpu, minion_total_memory)

# Main Procedure.


app_cost_data = []
total_cpu_used = 0
total_memory_used = 0

# ratio 50:50. as percentage
CPU_RATIO = 50
MEMORY_RATIO = 100 - CPU_RATIO

try:

    api_responce_namespaces = v1.list_namespace()
    for namespace in api_responce_namespaces.items:

        namespace_name = namespace.metadata.name
        namespace_pod_count = 0
        namespace_total_cpu_usage = 0
        namespace_total_memory_usage = 0

        api_responce_pod = v1.list_namespaced_pod(namespace_name)

        for pod in api_responce_pod.items:
            namespace_pod_count += 1
            total_pod_cpu, total_pod_memory = pod_total_resource(pod)
            namespace_total_cpu_usage += total_pod_cpu
            namespace_total_memory_usage += total_pod_memory

        app_cost_data.append({
            "namespace": namespace_name,
            "cpu_usage": namespace_total_cpu_usage,
            "memory_usage": namespace_total_memory_usage,
            "pod_count": namespace_pod_count
        })

        total_cpu_used += namespace_total_cpu_usage
        total_memory_used += namespace_total_memory_usage

except Exception as e:
    print "Namespace Resource Calculatoion Error :" + e.message

for app in app_cost_data:
    app_cpu_cost = (CPU_RATIO/100.0 * total_cluster_cost) * \
        (float(app["cpu_usage"]) / float(total_cpu_used))
    app_memory_cost = (MEMORY_RATIO/100.0 * total_cluster_cost) * \
        (float(app["memory_usage"]) / float(total_memory_used))
    app_total_cost = app_cpu_cost + app_memory_cost
    app.update({
        "app_cost": app_total_cost
    })

insert_cost_data(influx_client, app_cost_data)
