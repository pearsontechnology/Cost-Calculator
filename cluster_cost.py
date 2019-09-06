import boto3
from datetime import datetime, timedelta
import os
import traceback

client = boto3.client('ce')

def get_number_of_paas_per_region(region):
    # Assumption : #of vpcs = #of paas
    ec2 = boto3.client('ec2', region_name=region)
    pass_count = 0
    try:
        vpcs = ec2.describe_vpcs()
        for _ in vpcs['Vpcs']:
            pass_count = pass_count + 1

        print (datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Number of PAAS in ' + region + ' is = ' + str(pass_count))
        return pass_count

    except:
        print (traceback.format_exc())
        print (datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Getting the number of paas')
        return 0


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
            formatted_name_tag_values.append(environment + '-' + environment_type)

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


def get_cost_and_usage(date, region, environment, environment_type, service):

    str_start_date = date
    start_date = datetime.strptime(date, '%Y-%m-%d')
    end_date = start_date + timedelta(days=1)
    str_end_date = end_date.strftime('%Y-%m-%d')

    name_tag_values = get_name_tag_values(environment, environment_type, service)
    Tags = {
        'Key': 'Name',
        'Values': name_tag_values
    }

    if service == 'AmazonCloudWatch' or service == 'AWS CloudTrail':
        Tags = {
            'Key': 'CreatedBy',
            'Values': ['']
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
        print  ('(' + service + '): $' + str(unblended_cost))
        return float(unblended_cost)

    except:
        print (traceback.format_exc())
        print (datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Getting the cost of ' + service + ', Region :' + region)
        return 0


def get_cluster_cost(date, region, environment, environment_type):
    print ('Unblended Costs of', date, environment, environment_type, region)

    total_cost = 0
    services = ['Amazon Elastic Compute Cloud - Compute', 'EC2 - Other', 'Amazon Elastic Load Balancing',
                'Amazon Elasticsearch Service', 'Amazon Relational Database Service', 'AmazonCloudWatch',
                'AWS CloudTrail']

    for service in services:
        # Cloudwatch and CloudTrail costs will be divided among the number of PASS since it have no tags
        if service == 'AmazonCloudWatch' or service == 'AWS CloudTrail':
            cost_per_service = get_cost_and_usage(date, region, environment, environment_type,
                                                  service) / get_number_of_paas_per_region(region)
            print ('(' + service + ' - Per PAAS): ' + str(cost_per_service))

        else:
            cost_per_service = get_cost_and_usage(date, region, environment, environment_type, service)

        total_cost = total_cost + cost_per_service

    print ('Total Cost For The Environment(For Day): $', str(total_cost))
    return total_cost

def get_cluster_cost_per_hour(date, region, environment, environment_type):
    return float(get_cluster_cost(date, region, environment, environment_type)) / 24.0

date = datetime.now() - timedelta(days=1)
print(get_cluster_cost_per_hour(date.strftime("%Y-%m-%d"),"us-east-2","glp1","pre"))