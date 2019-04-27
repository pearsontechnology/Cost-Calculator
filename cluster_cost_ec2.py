# -*- coding: utf-8 -*-
import ConfigParser as cp
import boto3
import json
from datetime import datetime
import re
import time
import os
import traceback

config_1 = cp.RawConfigParser()
config_1.read(os.path.dirname(os.path.abspath(__file__))+'/config.cfg')

REGION = os.environ.get('REGION')
VPC_ID = os.environ.get('VPC_ID')

CONFIG_FILE_SECTION = 'regions'
REGION_NAME = config_1.get(CONFIG_FILE_SECTION, REGION)

ec2Resource = boto3.resource('ec2', region_name=REGION)
rds = boto3.client('rds', region_name=REGION)
pricing = boto3.client('pricing', region_name=REGION)

#####Get the Price of Instance (OnDemand). Example: getEC2Prices('t2.nano', 'US East (N. Virginia)') - Price calculated for 1 day
def getEC2Pricing(instanceType, location):
    global pricing
    instanceType = instanceType.strip()
    location = location.strip()
    try:
        response = pricing.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'usageType', 'Value': 'BoxUsage:'+instanceType},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'operation', 'Value': 'RunInstances'},
            ]
        )
        response = json.loads(response['PriceList'][0])['terms']['OnDemand']
        key = response.keys()[0]
        response = response[key]['priceDimensions']
        key = response.keys()[0]
        response = response[key]['pricePerUnit']['USD']
        return (float(response) * 24)
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Calculating Price of the instance :'+instanceType +', Region :' + location + ', OS :Linux'
        return 0

def getInstanceNameFromTags(tags):
    for tag in tags:
        if tag['Key'].lower() == "name":
            return tag['Value']

def Cluster_Cost_EC2_Calculation():
    global ec2Resource, REGION_NAME, REGION, VPC_ID
    ############################################INSTANCES AND IT'S IMPORTANT DATA(Filtered By Name Tag - mongo, cass) ARE RETRIEVED HERE###########################################################
    start = time.time()
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Job Started'
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION :' + REGION
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION NAME:' + REGION_NAME
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'VPC ID:' + VPC_ID

    instances = ec2Resource.instances.filter(
        Filters=[{'Name': 'vpc-id', 'Values': [VPC_ID]}]
    )

    instanceCount = 0
    for instance in instances:
        instanceCount = instanceCount + 1
        name =  getInstanceNameFromTags(instance.tags)
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Processing Instance : ' + instance.id,

        volumeCost = getVolumeCost(instance)
        instanceCost = getEC2Pricing(instance.instance_type, REGION_NAME)
        
