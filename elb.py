# -*- coding: utf-8 -*-
import ConfigParser as cp
import boto3
from datetime import datetime
import time
import traceback
import os
import re

config = cp.RawConfigParser()
config.read(os.path.dirname(os.path.abspath(__file__)) + '/config.cfg')

REGION = os.environ['REGION']
REGION_NAME = config.get('regions', REGION)
ENVIRONMENT = os.environ['ENVIRONMENT']
ENVIRONMENT_TYPE = os.environ['ENVIRONMENT_TYPE']
# VPC_ID = 'vpc-ff8af197'

today = datetime.utcnow()
timestamp_today = time.mktime(today.timetuple())

def get_lb_version(region):
    if region == 'us-west-1':
        lb_version = 'elbv2'
        regional_cost = config.get('elb_costs', 'us-west-1')
    elif region == 'us-east-1':
        lb_version = 'elb'
        regional_cost = config.get('elb_costs', 'us-east-1')
    elif region == 'us-east-2':
        lb_version = 'elbv2'
        regional_cost = config.get('elb_costs', 'us-east-2')
    elif region == 'eu-west-1':
        lb_version = 'elbv2'
        regional_cost = config.get('elb_costs', 'eu-west-1')
    elif region == 'ap-southeast-1':
        lb_version = 'elb'
        regional_cost = config.get('elb_costs', 'ap-southeast-1')
    elif region == 'us-west-2':
        lb_version = 'elbv2'
        regional_cost = config.get('elb_costs', 'us-west-2')

    return lb_version, regional_cost


def elb_cost():
    start = time.time()

    # There are two boto3 lb client versions.
    # 1.`elb` - classical lbs
    # 2.`elbv2` - network & application lbs
    lb_version, regional_cost = get_lb_version(REGION)

    total_instance_cost = 0
    instance_count = 0

    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'ELB Cost Calculation(For This Hour) Started')
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION:' + REGION)
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION NAME:' + REGION_NAME)

    try:
        client = boto3.client(lb_version, region_name=REGION)
        bals = client.describe_load_balancers()
        # set the iterater according to elb client version
        if lb_version =='elbv2':
            elbs = bals['LoadBalancers']
        else:
            elbs = bals['LoadBalancerDescriptions']

        for elb in elbs:
            # remove cb related elbs
            elb_name = elb['LoadBalancerName']
            if not re.search('cb', elb_name):
                exp_env = '\\b'+ENVIRONMENT+'\\b'
                exp_ent_type = '\\b'+ENVIRONMENT_TYPE+'\\b'

                if re.search(exp_env, elb_name) and re.search(exp_ent_type, elb_name):
                    instance_count = instance_count + 1
                    cost = float(regional_cost)
                    print 'ELB Instance : ' + (elb_name),
                    print ' |  Cost : $' + str(cost)

                    total_instance_cost = total_instance_cost + cost

        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Processed ' + str(instance_count) + ' Instances'
        print 'Total Cost(For This Hour) : $' + str(total_instance_cost)
        end = time.time()
        print datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'ELB Cost Calculation Ended. Total Execution Time is ' + str(end - start) + ' Seconds'
        return total_instance_cost
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Calculating Cost for ELB'


#elb_cost()
