from kubernetes import kubernetes
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pprint import pprint
import os

config.load_kube_config()
v1 = client.CoreV1Api()

#tested with CB and Mongo
def calc_ec2_based_crd_cost(environment,environment_type,namespace):

    api_instance = kubernetes.client.CustomObjectsApi(kubernetes.client.ApiClient())
    group = 'prsn.io' 
    version = 'v1' 
    
    #role   :   plural in CRD
    considered_crd = {
        "cb" : "cbs",
        "mg":"mongos"
    }
    for role,crd_plural in considered_crd.iteritems():
        api_response = api_instance.list_namespaced_custom_object(group, version,namespace,crd_plural)
        responce_items = api_response.__getitem__("items")
        if(len(responce_items) != 0):
             calculated_names = []
             for item in responce_items:
                 calc_name = item.__getitem__("metadata").__getitem__("name")
                 calc_name += "-" + namespace
                 calc_name += "-" + role
                 calc_name += "-" + environment
                 calc_name += "-" + environment_type
                 calculated_names.append(item)
                 print(calc_name)
                
        else:
            print("No resources. Skipping")



namespaces = v1.list_namespace()

ENVIRONMENT = os.environ['ENVIRONMENT'] if "ENVIRONMENT" in os.environ else "glp1"
ENVIRONMENT_TYPE = os.environ['ENVIRONMENT_TYPE'] if "ENVIRONMENT_TYPE" in os.environ else "pre"

for namespace in namespaces.items:
    namespace_name = namespace.metadata.name
    calc_ec2_based_crd_cost(ENVIRONMENT,ENVIRONMENT_TYPE, namespace_name)
    