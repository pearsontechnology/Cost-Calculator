from kubernetes import kubernetes
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pprint import pprint
import os
from call_ce_crd import call_ce_crd
from datetime import datetime,timedelta


def calc_rds_crd_cost(date,region,environment, environment_type, namespace,debug=True):

    api_instance = kubernetes.client.CustomObjectsApi(kubernetes.client.ApiClient())
    group = 'prsn.io'
    version = 'v1'

    # role   :   plural in CRD
    considered_crd = {
        "mysql": "mysqls",
        "postgres": "postgreses"
    }

    services = ['Amazon Relational Database Service']

    return_obj = {}

    for role, crd_plural in considered_crd.items():
        try:
            api_response = api_instance.list_namespaced_custom_object(
                group, version, namespace, crd_plural)
            responce_items = api_response["items"]
            if(len(responce_items) != 0):
                calculated_names = []
                for item in responce_items:
                    calc_name = environment #1
                    calc_name += "-" + environment_type#2
                    calc_name += "-" + split_by_and_merge("-",namespace)#3
                    calc_name += "-" + role#4
                    calc_name += "-" + split_by_and_merge("-",item["metadata"]["name"])#5
                    calculated_names.append(calc_name)
                print(calculated_names)
                return_obj[crd_plural] = call_ce_crd(date,region,services,calculated_names)
            else:
                print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + crd_plural + 
                  ' No Resources. Skipping')
        except Exception as e:
            if debug:
                print(e)
            continue

    return return_obj

def split_by_and_merge(delim,inputstr):
    splitarr = inputstr.split(delim)
    print(splitarr)
    return ''.join(splitarr)
