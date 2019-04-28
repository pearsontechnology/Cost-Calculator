#from influxdb import InfluxdbClient
import os
import ConfigParser as cp
import requests
from datetime import datetime, timedelta
import boto3
REGION = os.environ.get('REGION')
VPC_ID = os.environ.get('VPC_ID')
DOMAIN = os.environ.get('ES_DOMAIN')
Client = boto3.client('es', region_name=REGION)


today = datetime.utcnow()
str_today = today.strftime('%Y.%m.%d')
yesterday = datetime.today() - timedelta(days=1)
str_yesterday = yesterday.strftime('%Y.%m.%d')
print str_today
# Get Data From Config File
# config_1 = cp.RawConfigParser()
# config_1.read(os.path.dirname(os.path.abspath(__file__))+'/config.cfg')

# EBS_COST_PER_GB = config_1.get('EBS_SSD_cost_per_day', 'EBS')
EBS_COST_PER_GB = 0.0045



def ebs_cost(ebs_vol_size):
    return ebs_vol_size * EBS_COST_PER_GB


def es_cost(instance_type, ebs_vol_size, num_instances, size):
    # BASIC_COST = config_1.get('ES_rate', instance_type)
    BASIC_COST = 0.587
    return (ebs_cost(float(size/1024.00/1024/1024))) * num_instances


def es_cost_calc(namespace):
    request = Client.describe_elasticsearch_domain(DomainName=DOMAIN)

    instance_type = request['DomainStatus']['ElasticsearchClusterConfig']['InstanceType']
    instance_count = request['DomainStatus']['ElasticsearchClusterConfig']['InstanceCount']
    ebs_volume_size = request['DomainStatus']['EBSOptions']['VolumeSize']
    endpoint = request['DomainStatus']['Endpoint']
    print instance_type
    print instance_count
    print ebs_volume_size

    final_endpoint = 'https://' + str(endpoint) + '/_cat/indices?bytes=b&h=index,store.size&format=json&s=index'

    #namespc = requests.get('https://search-us1-preprod-logging-7g5zq66uyxpscqd2zly4wswoq4.us-east-1.es.amazonaws.com/_cat/indices?bytes=b&h=index,store.size&format=json&s=index')
    namespc = requests.get(final_endpoint)
    namespc_result = namespc.json()
    output = []
    size = 0
    for j in namespc_result:
        if namespace in str(j):
            if str_yesterday in str(j):
                size = int(j['store.size'])
                namearray = j['index'][:-1* (len(j['index'].split('-')[-1]) +1 )]

                if len(namearray) == 2:
                    output.append(namearray[0])
                elif len(namearray) == 1:
                    output.append(namearray[0])
                else:
                    output.append(namearray[0] + namearray[1])

    nameset = set(output)
    for n in nameset:
        name = str(n)
        if name == namespace:
            print 'cost of ' + namespace + ' is: ' + str(es_cost(instance_type, ebs_volume_size, instance_count, size))
            return (es_cost(instance_type, ebs_volume_size, instance_count, size))
