from kubernetes import kubernetes
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pprint import pprint
import os
from .call_ce_crd import call_ce_crd
from datetime import datetime,timedelta


# tested with CB and Mongo
def calc_ec2_based_crd_cost(date,region,environment, environment_type, namespace):

    api_instance = kubernetes.client.CustomObjectsApi(kubernetes.client.ApiClient())
    group = 'prsn.io'
    version = 'v1'

    # role   :   plural in CRD
    considered_crd = {
        "cb": "cbs",
        "mg": "mongos"
    }

    services = ['Amazon Elastic Compute Cloud - Compute', 'Amazon Elastic Load Balancing','EC2 - Other']

    return_obj = {}

    for role, crd_plural in considered_crd.items():
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
        except Exception as e:
            print(e)
            continue

    return return_obj