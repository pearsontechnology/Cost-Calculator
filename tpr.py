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

#Get the Price for one day. Example: getEBSPricing('vol-0f32d8c8f34baacd6', 'US West (N. California)')
def getEBSPricing(id, location):
    try:
        #Getting the type and the size of the volume
        global ec2Resource, pricing
        volume = ec2Resource.Volume(id)
        volumeType = volume.volume_type
        volumeSize =  volume.size

        #Getting the price of the volume
        if volumeType == 'gp2':
            value = 'General Purpose'
        elif volumeType == 'io1':
            value = 'Provisioned IOPS'
        elif volumeType == 'st1':
            value = 'Throughput Optimized HDD'
        elif volumeType == 'sc1':
            value = 'Cold HDD'
        else:
            return float(0) #Means Volume Type is Standard and 0 price for standard volumes

        response = pricing.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Storage'},
                {'Type': 'TERM_MATCH', 'Field': 'volumeType', 'Value': value}
            ]
        )
        response = json.loads(response['PriceList'][0])['terms']['OnDemand']
        key = response.keys()[0]
        response = response[key]['priceDimensions']
        key = response.keys()[0]
        response = response[key]['pricePerUnit']['USD']
        return (float(response)/30) * volumeSize
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Calculating Price of the Volume :'+id +', Region :' + location
        return 0

#Get the price of the RDS. Example : getRDSPricing('db.t2.large', 'South America (Sao Paulo)', 'Single-AZ', 'PostgreSQL')
def getRDSPricing(type, location, availability, engine):
    #Availability : Single-AZ, Multi-AZ
    #engine : Oracle, MySQL, PostgreSQL,
    global pricing
    try:
        response = pricing.get_products(
            ServiceCode='AmazonRDS', MaxResults=100,
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': availability},
                {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': engine},
            ]
        )
        response = json.loads(response['PriceList'][0])['terms']['OnDemand']
        key = response.keys()[0]
        response = response[key]['priceDimensions']
        key = response.keys()[0]
        response = response[key]['pricePerUnit']['USD']
        return float(response)*24
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Calculating Cost for RDS :' + type +' ' + location +' ' + availability+' ' + engine
        return 0

def getInstanceNameFromTags(tags):
    for tag in tags:
        if tag['Key'].lower() == "name":
            return tag['Value']

def getInstanceNamespaceFromTags(tags):
    for tag in tags:
        if tag['Key'].lower() == "namespace":
            return tag['Value']

#Example: getRDSNamespace('arn:aws:rds:us-east-1:815492460363:db:kong-us1-prod-docs')
def getRDSNamespace(arn):
    global rds
    tags = rds.list_tags_for_resource(ResourceName=arn)['TagList']
    for tag in tags:
        if tag['Key'].lower() == "namespace":
            return tag['Value']

def getVolumeCost(instance):
    global REGION, REGION_NAME
    cost = 0
    volumes = instance.volumes.all()
    for volume in volumes:
        cost = cost + getEBSPricing(volume.id, REGION_NAME)
    return cost

#Main Function for Calculating TPR Cost. This will return the cost with the namespaces as dictionary
def TPRCalculation():
    global ec2Resource, rds, REGION_NAME, REGION, VPC_ID
    ############################################INSTANCES AND IT'S IMPORTANT DATA(Filtered By Name Tag - mongo, cass) ARE RETRIEVED HERE###########################################################
    start = time.time()
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Job Started: TPR Calculation'
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION :' + REGION
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION NAME:' + REGION_NAME
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'VPC ID:' + VPC_ID

    instances = ec2Resource.instances.filter(
        Filters=[{'Name': 'vpc-id', 'Values': [VPC_ID]}]
    )
    tpr = {}
    instanceCount = 0
    for instance in instances:
        instanceCount = instanceCount + 1
        name =  getInstanceNameFromTags(instance.tags)
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Processing Instance : ' + instance.id,
        if re.search('mongo', name, re.IGNORECASE): #Means this is mongo instance
            print ' is TPR(Mongo)'
            try:
                namespace = getInstanceNamespaceFromTags(instance.tags).lower()
            except:
                print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Error(TPR) -> Namespace Not Found For Mongo Instance : ' + instance.id + '. Excluding From TPR Calculation...'
                continue
            volumeCost = getVolumeCost(instance)
            instanceCost = getEC2Pricing(instance.instance_type, REGION_NAME)
            try:
                tpr[namespace]['mongo'] = tpr[namespace]['mongo'] + volumeCost + instanceCost
            except:
                tpr[namespace] = {}
                tpr[namespace]['mongo'] = volumeCost + instanceCost

        elif re.search('cass', name, re.IGNORECASE):
            print ' is TPR(Cassandra)'
            try:
                namespace = getInstanceNamespaceFromTags(instance.tags).lower()
            except:
                print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Error. Namespace Not Found For Cassandra Instance : ' + instance.id + '. Excluding From TPR Calculation...'
                continue
            volumeCost = getVolumeCost(instance)
            instanceCost = getEC2Pricing(instance.instance_type, REGION_NAME)
            try:
                tpr[namespace]['cass'] = tpr[namespace]['cass'] + volumeCost + instanceCost
            except:
                tpr[namespace] = {}
                tpr[namespace]['cass'] = volumeCost + instanceCost
        else:
            print ' is NOT TPR'

    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Processed ' + str(instanceCount) + ' Instances'

    #############################################WE CAN RETRIEVE RDS HERE###########################################################
    dbInstances = rds.describe_db_instances()['DBInstances']
    for dbInstance in dbInstances:
        arn = dbInstance['DBInstanceArn']
        print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Processing RDS : ' + arn
        type = dbInstance['DBInstanceClass']
        availability = 'Single-AZ'
        engine = dbInstance['Engine']
        if engine == 'postgres':
            engine = 'PostgreSQL'
        elif engine == 'mysql':
            engine = 'MySQL'
        else:
            print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Unknown DB Engine Detected. It must be other than MySQL & PostgreSQL. ARN:' + arn + ' Engine: ' + engine
            continue
        if dbInstance['MultiAZ'] == True:
            availability = 'Multi-AZ'

        namespace = getRDSNamespace(arn)
        if namespace == None:
            continue
        if dbInstance['DBSubnetGroup']['VpcId'] != VPC_ID:
            continue
        cost = getRDSPricing(type, REGION_NAME, availability, engine)
        try:
            tpr[namespace]['rds'] = tpr[namespace]['rds'] + cost
        except:
            tpr[namespace] = {}
            tpr[namespace]['rds'] = cost

    totalTPR = {}
    for namespace, resources in tpr.items():
        totalTPR[namespace] = 0
        for item, cost in resources.items():
            totalTPR[namespace] = totalTPR[namespace] + cost

    end = time.time()
    print 'TPR Calculation Ended. Total Execution Time is ' + str(end - start)
