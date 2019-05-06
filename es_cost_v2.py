import ConfigParser as cp
import boto3
import json
from datetime import datetime
import time
import re
import traceback
import os

config = cp.RawConfigParser()
config.read(os.path.dirname(os.path.abspath(__file__)) + '/config.cfg')

REGION = 'us-east-2'
REGION_NAME = config.get('regions', REGION)
ENVIRONMENT = os.environ['ENVIRONMENT']
ENVIRONMENT_TYPE = os.environ['ENVIRONMENT_TYPE']

pricing = boto3.client('pricing')
es = boto3.client('es', region_name=REGION)


# Example: get_es_instance_per_hour_price('t2.micro.elasticsearch','US East (N. Virginia)')
def get_es_instance_per_hour_price(instance_type, region):
    try:
        es_instances_prices = pricing.get_products(
            ServiceCode='AmazonES',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region},
                {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Elastic Search Instance'},
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
            ]
        )

        resp = json.loads(es_instances_prices['PriceList'][0])['terms']['OnDemand']
        key = resp.keys()[0]
        resp = resp[key]['priceDimensions']
        key = resp.keys()[0]
        es_instance_price_per_hour = resp[key]['pricePerUnit']['USD']
        # print "Per hour cost rate: ",es_instance_price_per_hour
        return es_instance_price_per_hour
    except:
        print (traceback.format_exc())
        print (datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Getting Price of the instance :' + instance_type + ', Region :' + region)
        return 0


def get_es_instance_volume_per_hour_price(region):
    try:
        es_instances_prices = pricing.get_products(
            ServiceCode='AmazonES',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region},
                {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Elastic Search Volume'},
                {'Type': 'TERM_MATCH', 'Field': 'storageMedia', 'Value': 'GP2'},
            ]
        )

        resp = json.loads(es_instances_prices['PriceList'][0])['terms']['OnDemand']
        key = resp.keys()[0]
        resp = resp[key]['priceDimensions']
        key = resp.keys()[0]
        es_instance_price_per_hour = float(resp[key]['pricePerUnit']['USD']) / 30 / 24
        print "Per hour volume cost rate: ", es_instance_price_per_hour
        return es_instance_price_per_hour
        print es_instances_prices
    except:
        print (traceback.format_exc())
        print (datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Getting Price of the instance, Region :' + region)
        return 0


# Example: get_es_instance_volume_per_hour_price('US East (N. Virginia)')


# This includes both masters and data nodes
def get_es_total_cost():
    global master_count
    domain_count = 0
    total_es_cost = 0
    start = time.time()

    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'ES Cost Calculation(For Hour) Started')
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION:' + REGION)
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'ENVIRONMENT:' + ENVIRONMENT)
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'ENVIRONMENT TYPE:' + ENVIRONMENT_TYPE)
    print
    try:
        domain_names = es.list_domain_names()
        # grep domains by environment and environment type
        for domain in domain_names['DomainNames']:
            exp_env = '\\b' + ENVIRONMENT + '\\b'
            exp_ent_type = '\\b' + ENVIRONMENT_TYPE + '\\b'
            domain_name = domain['DomainName']
            if re.search(exp_env, domain_name) and re.search(exp_ent_type, domain_name):
                domain_count = domain_count + 1
                print domain_count, '.', domain_name
                domain_info = es.describe_elasticsearch_domain(
                    DomainName=domain['DomainName']
                )
                es_config = domain_info['DomainStatus']['ElasticsearchClusterConfig']
                # calculate master costs
                if es_config['DedicatedMasterEnabled']:
                    master_count = es_config['DedicatedMasterCount']
                    master_type = es_config['DedicatedMasterType']
                    master_nodes_cost = float(get_es_instance_per_hour_price(master_type, REGION_NAME)) * int(
                        master_count)
                    print 'Number of master nodes: ', master_count, '-', master_type
                    print 'Cost for master nodes: $', master_nodes_cost

                # calculate data_node costs
                minion_count = es_config['InstanceCount']
                minion_type = es_config['InstanceType']
                data_nodes_cost = float(get_es_instance_per_hour_price(minion_type, REGION_NAME)) * int(minion_count)
                print 'Number of data nodes: ', minion_count, '-', minion_type
                print 'Cost for data nodes: $', data_nodes_cost

                if es_config['DedicatedMasterEnabled']:
                    total_node_count = master_count + minion_count
                    total_node_cost = master_nodes_cost + data_nodes_cost
                else:
                    total_node_count = minion_count
                    total_node_cost = data_nodes_cost

                # calculate volume cost
                ebs_options = domain_info['DomainStatus']['EBSOptions']
                if ebs_options['EBSEnabled']:
                    volume_cost = float(get_es_instance_volume_per_hour_price(REGION_NAME)) * int(
                        ebs_options['VolumeSize']) * int(minion_count)
                    total_node_cost = total_node_cost + volume_cost
                    print 'Cost for volume: $', volume_cost

                # final domain cost
                total_es_cost = total_es_cost + total_node_cost

                print 'Total number of nodes in this ES domain: ', total_node_count
                print 'Total cost of this ES domain: $', str(total_node_cost)
                print

        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Processed ' + str(domain_count) + ' Domains'
        print 'Total ES Cost(For Hour) : $' + str(total_es_cost)
        end = time.time()
        print datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'ES Cost Calculation Ended. Total Execution Time is ' + str(
            end - start) + ' Seconds'
        return total_es_cost
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Calculating Cost for ES'
