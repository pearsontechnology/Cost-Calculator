import boto3
from datetime import datetime, timedelta
import ConfigParser as cp
import os
import traceback

config = cp.RawConfigParser()
config.read(os.path.dirname(os.path.abspath(__file__)) + '/config.cfg')

REGION = os.environ['REGION']
REGION_NAME = config.get('regions', REGION)
ENVIRONMENT = os.environ['ENVIRONMENT']
ENVIRONMENT_TYPE = os.environ['ENVIRONMENT_TYPE']

client = boto3.client('ce')

today = datetime.utcnow()
str_today = today.strftime('%Y-%m-%d')
yesterday = datetime.today() - timedelta(days=1)
str_yesterday = yesterday.strftime('%Y-%m-%d')


def format_tags(roles, environment, environment_type):
    formatted_name_tag_values = []
    for role in roles:
        role = role + "-" + environment + "-" + environment_type
        formatted_name_tag_values.append(role)

    return formatted_name_tag_values


def get_name_tag_values(environment, environment_type, service):
    if service == 'Amazon Elastic Compute Cloud - Compute' or service == 'EC2 - Other':
        roles = ['master', 'minion', 'stackstorm', 'etcd', 'consul', 'bastion', 'ca', 'prometheus']
        formatted_name_tag_values = format_tags(roles, environment, environment_type)

        if service == 'EC2 - Other':
            # Append NAT-GATEWAY Tag
            formatted_name_tag_values.append(environment+'-'+environment_type)

        return formatted_name_tag_values

    elif service == 'Amazon Elastic Load Balancing':
        # prometheus-ishan-dev-int
        roles = ['lb-ca', 'etcd', 'consul', 'lb-int-master', 'lb-master', 'lb-minion', 'lb-int-minion', 'prometheus',
                 'stackstorm']
        formatted_name_tag_values = format_tags(roles, environment, environment_type)
        return formatted_name_tag_values

    elif service == 'Amazon Elasticsearch Service':
        roles = ['db']
        formatted_name_tag_values = format_tags(roles, environment, environment_type)
        return formatted_name_tag_values

    elif service == 'Amazon Relational Database Service':
        roles = ['keycloak-db', 'grafana-db']
        formatted_name_tag_values = format_tags(roles, environment, environment_type)
        return formatted_name_tag_values


def get_cost_and_usage(region, environment, environment_type, service):
    name_tag_values = get_name_tag_values(environment, environment_type, service)
    try:
        response = client.get_cost_and_usage(
            TimePeriod={
                'Start': str_yesterday,
                'End': str_today
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
                        'Tags': {
                            'Key': 'Name',
                            'Values': name_tag_values
                        }
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
        print  '(' + service + '): $' + str(unblended_cost)
        return float(unblended_cost)

    except:
        print (traceback.format_exc())
        print (datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Getting the cost of ' + service + ', Region :' + region)
        return 0


def get_cluster_cost(region, environment, environment_type):
    print 'Unblended Costs of', str_yesterday, environment, environment_type, region

    services = ['Amazon Elastic Compute Cloud - Compute', 'EC2 - Other', 'Amazon Elastic Load Balancing',
                'Amazon Elasticsearch Service', 'Amazon Relational Database Service']
    total_cost = 0
    for service in services:
        cost_per_service = get_cost_and_usage(region, environment, environment_type, service)
        total_cost = total_cost + cost_per_service

    print 'Total Cost For The Environment(For Day): $', str(total_cost)
    return total_cost


get_cluster_cost(REGION, ENVIRONMENT, ENVIRONMENT_TYPE)
