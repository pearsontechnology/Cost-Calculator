from kubernetes import kubernetes
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pprint import pprint
import os
from .call_ce_crd import call_ce_crd
from datetime import datetime,timedelta

# tested with CB and Mongo
def calc_neptune_crd_cost(date,region,environment, environment_type, namespace):

    api_instance = kubernetes.client.CustomObjectsApi(
        kubernetes.client.ApiClient())
    group = 'prsn.io'
    version = 'v1'

    # role   :   plural in CRD
    crd_plural = "neptunes"

    services = ['Amazon Neptune']

    return_obj = {}
    try:
        api_response = api_instance.list_namespaced_custom_object(
            group, version, namespace, crd_plural)
        responce_items = api_response["items"]
        if(len(responce_items) != 0):
            calculated_names = []
            for item in responce_items:
                calc_name = item["metadata"]["name"]
                calc_name += "-" + environment
                calc_name += "-" + region
                calc_name += "-" + namespace
                calc_name += "-" + environment_type
                for db_instance in item["spec"]["options"]["db_instances"]:
                    calc_name += "-" + db_instance["db_name"]
                    calculated_names.append(calc_name)
            print(calculated_names)
            return_obj[crd_plural] = call_ce_crd(date,region,services,calculated_names)
        else:
            print("No resources. Skipping")
    except Exception as e:
        print(e)
        return_obj = {}

    return return_obj
