from __future__ import print_function
import kubernetes.client
from kubernetes.client.rest import ApiException
from kubernetes import client, config
import ConfigParser as cp
import os
import traceback
from datetime import datetime, timedelta
import boto3
from cb_ebs_cost import ebs_main_calc
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

config.load_kube_config()

config = cp.RawConfigParser()
config.read(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'config.cfg')))

REGION = os.environ['REGION'] if "REGION" in os.environ else "us-east-2"
REGION_NAME = config.get('regions', REGION)
ENVIRONMENT = os.environ['ENVIRONMENT'] if "ENVIRONMENT" in os.environ else "glp1"
ENVIRONMENT_TYPE = os.environ['ENVIRONMENT_TYPE'] if "ENVIRONMENT_TYPE" in os.environ else "pre"

SINGULAR='cb'
PLURAL='cbs'
VERSION='v1'
GROUP='prsn.io'

client = boto3.client('ce')
api_instance = kubernetes.client.CustomObjectsApi()

def get_names():
    try:
        formatted_name_tag_values = []
        api_response = api_instance.list_cluster_custom_object(group=GROUP,version=VERSION,plural=PLURAL)

        for i in api_response['items']:

            role = i["metadata"]['name']
            role += "-" + i['metadata']['namespace']
            role += "-" + SINGULAR
            role += "-" + ENVIRONMENT
            role += "-" + ENVIRONMENT_TYPE

            formatted_name_tag_values.append(role)

        # print (formatted_name_tag_values)
        return formatted_name_tag_values

    except ApiException as e:
        print("Exception when calling CustomObjectsApi->list_cluster_custom_object: %s\n" % e)
        return formatted_name_tag_values


def get_cost_and_usage(date, region, service):

    str_start_date = date
    start_date = datetime.strptime(date, '%Y-%m-%d')
    end_date = start_date + timedelta(days=1)
    str_end_date = end_date.strftime('%Y-%m-%d')

    name_tag_values = get_names()
    Tags = {
        'Key': 'Name',
        'Values': name_tag_values
    }

    try:
        response = client.get_cost_and_usage(
            TimePeriod={
                'Start': str_start_date,
                'End': str_end_date
            },
            Granularity='MONTHLY',
            Filter={
                'And': [
                    {
                        'Dimensions': {
                            'Key': 'SERVICE',
                            'Values': [
                                service
                            ],
                        }
                    }
                    ,
                    {
                        'Dimensions': {
                            'Key': 'REGION',
                            'Values': [
                                region
                            ],
                        }
                    }
                    ,
                    {
                        'Tags': Tags
                    }
                ]
            },
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }
            ],
            Metrics=[
                'UnblendedCost'
            ]
        )

        unblended_cost = response['ResultsByTime'][0]['Groups'][0]['Metrics']['UnblendedCost']['Amount']
        print ( "(" + service + "): $" + str(unblended_cost))
        return float(unblended_cost)

    except:
        print (traceback.format_exc())
        print (datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Getting the cost of ' + service + ', Region :' + region)
        return 0



def get_cb_crd_costs(date, environment, environment_type, region):
    print ('Unblended Costs of CB ', date, environment, environment_type, region)

    total_cost = 0
    services = ['Amazon Elastic Compute Cloud - Compute', 'EC2 - Other', 'Amazon Elastic Load Balancing', 'EBS']

    for service in services:

        if service == 'EBS':
            cost_per_service = ebs_main_calc(region, environment, environment_type)
            print ('(EBS): ' + str(cost_per_service))

        else:
            cost_per_service = get_cost_and_usage(date, region, service)

        total_cost = total_cost + cost_per_service

    print ('Total CB Cost For The Environment(For Day): $', str(total_cost))
    return total_cost

get_cb_crd_costs('2019-05-20', ENVIRONMENT, ENVIRONMENT_TYPE, REGION)