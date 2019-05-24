from kubernetes import kubernetes
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pprint import pprint
import os
from call_ce_crd import call_ce_crd
from datetime import datetime,timedelta

config.load_kube_config()
v1 = client.CoreV1Api()

# tested with CB and Mongo
def calc_ec2_based_crd_cost(date,region,environment, environment_type, namespace):

    api_instance = kubernetes.client.CustomObjectsApi(
        kubernetes.client.ApiClient())
    group = 'prsn.io'
    version = 'v1'

    # role   :   plural in CRD
    considered_crd = {
        "cb": "cbs",
        "mg": "mongos"
    }

    services = ['Amazon Elastic Compute Cloud - Compute',
                'EC2 - Other', 'Amazon Elastic Load Balancing']

    return_obj = {}

    for role, crd_plural in considered_crd.iteritems():
        try:
            api_response = api_instance.list_namespaced_custom_object(
                group, version, namespace, crd_plural)
            responce_items = api_response["items"]
            if(len(responce_items) != 0):
                calculated_names = []
                for item in responce_items:
                    calc_name = item["metadata"]["name"]
                    calc_name += "-" + namespace
                    calc_name += "-" + role
                    calc_name += "-" + environment
                    calc_name += "-" + environment_type
                    calculated_names.append(calc_name)
                print(calculated_names)
                return_obj[crd_plural] = call_ce_crd(date,region,services,calculated_names)
            else:
                print("No resources. Skipping")
        except ApiException:
            continue
    
    return return_obj


namespaces = v1.list_namespace()

ENVIRONMENT = os.environ['ENVIRONMENT'] if "ENVIRONMENT" in os.environ else "glp1"
ENVIRONMENT_TYPE = os.environ['ENVIRONMENT_TYPE'] if "ENVIRONMENT_TYPE" in os.environ else "pre"

cost_date = datetime.now() - timedelta(days=2) 
for namespace in namespaces.items:
    namespace_name = namespace.metadata.name
    calc_ec2_based_crd_cost(datetime.strftime(cost_date, '%Y-%m-%d'),"us-east-2",ENVIRONMENT, ENVIRONMENT_TYPE, namespace_name)