#namespace level costing
import kubernetes
from kubernetes import client,config
from pprint import pprint

config.load_kube_config()
v1 = client.CoreV1Api()

total_cluster_cost = 500

#Calculate minion total compute resources
total_cpu = 0
total_memory = 0
try:
    #nodes = v1.list_node(label_selector="role=minion")
    api_responce = v1.list_node(pretty=True,field_selector="metadata.name=minikube")
    for node in api_responce.items:
        total_cpu += int(node.status.capacity["cpu"])
        memory_str = node.status.capacity["memory"]
        if str.endswith(memory_str,"i") or str.endswith(memory_str,"b"):
            total_memory += int(memory_str[0:len(memory_str) - 2])
        else:
            total_memory += int(memory_str[0,len(memory_str) - 1])
except Exception as e:
    print e
