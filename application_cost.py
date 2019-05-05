#namespace level costing
import kubernetes
from kubernetes import client,config
from pprint import pprint

config.load_kube_config()
v1 = client.CoreV1Api()

total_cluster_cost = 500

#converts memory str to int
def memory_to_int(memory_str):
    int_memory = 0
    if "Ki" in memory_str or "K" in memory_str:
        arr = memory_str.split("K")
        int_memory = int (arr[0])
    elif "Mi" in memory_str or "M" in memory_str:
        arr = memory_str.split("M")
        int_memory = int (arr[0]) * 1024
    return int_memory

def cpu_mi_convert(cpu_str):
    cpu = 0
    if type(cpu_str) is int:
        return cpu_str
    if "m" in cpu_str:
        cpu_int = cpu_str[0:len(cpu_str)-1]
        cpu = int(cpu_int) / 1000.0
        print cpu
    else:
        cpu = int (cpu_str)
    return cpu

def pod_total_resource(pod):
    pod_cpu_usage  = 0
    pod_memory_usage  = 0
    for container in pod.spec.containers:
        requests = container.resources.requests
        print requests
        if requests is None:
            pod_cpu_usage += cpu_mi_convert("5m")
            pod_memory_usage += memory_to_int("100M")
        else:
            pod_cpu_usage += cpu_mi_convert(requests["cpu"])
            pod_memory_usage += memory_to_int(requests["memory"])
    return (pod_cpu_usage,pod_memory_usage)


#Calculate minion total compute resources
total_cpu = 0
total_memory = 0
try:
    #nodes = v1.list_node(label_selector="role=minion")
    api_responce_nodes = v1.list_node(pretty=True,field_selector="metadata.name=minikube")
    for node in api_responce_nodes.items:
        total_cpu += int(node.status.capacity["cpu"])
        total_memory += memory_to_int(node.status.capacity["memory"])
except Exception as e:
    print e

print (total_cpu,total_memory)

try:
    api_responce_namespaces = v1.list_namespace()
    for namespace in api_responce_namespaces.items:
        namespace_name = namespace.metadata.name
        namespace_total_cpu_usage = 0
        namespace_total_memory_usage = 0

        api_responce_pod = v1.list_namespaced_pod(namespace_name)
        for pod in api_responce_pod.items:
            print pod_total_resource(pod)
except Exception as e:
    print e

