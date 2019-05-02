# -*- coding: utf-8 -*-
import ConfigParser as cp
import boto3
import json
from datetime import datetime
import time
import traceback

config_1 = cp.RawConfigParser()
config_1.read(os.path.dirname(os.path.abspath(__file__))+'/config.cfg')

REGION = 'us-east-2'
REGION_NAME = 'US East (Ohio)'
ENVIRONMENT = 'glp1'
ENVIRONMENT_TYPE = 'pre'
VPC_ID = 'vpc-ff8af197'

EC2_PRICE = {}
EBS_PRICE = {}

ec2_resource = boto3.resource('ec2', region_name=REGION)
pricing = boto3.client('pricing', region_name='us-east-1') # Pricing doesn't depends on provided region here 


##### Get the Price of Instance (OnDemand). Example: get_ec2_pricing('t2.nano', 'US East (N. Virginia)') - Price calculated for 1 day
def get_ec2_pricing(instance_type, location):
    global pricing, EC2_PRICE
    instance_type = instance_type.strip()
    location = location.strip()

    # Get price from the variable if Already calculated. This saves times and api requests

    if location in EC2_PRICE:  # Location is there.
        if instance_type in EC2_PRICE[location]:  # Price also there
            return EC2_PRICE[location][instance_type]
    else:
        EC2_PRICE[location] = {}  # Price is not there. Create location dict.

    # Price info is not in variable. Calculate it.
    try:
        response = pricing.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'shared'},
                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'operation', 'Value': 'RunInstances'},
            ],
        )
        response = json.loads(response['PriceList'][0])['terms']['OnDemand']
        key = response.keys()[0]
        response = response[key]['priceDimensions']
        key = response.keys()[0]
        response = response[key]['pricePerUnit']['USD']
        EC2_PRICE[location][instance_type] = float(response);
        return EC2_PRICE[location][instance_type];

    except:
        print (traceback.format_exc())
        print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Getting Price of the instance :' + instance_type + ', Region :' + location + ', OS :Linux')
        return 0


# Get the Price for one day. Example: get_ebs_pricing('vol-0f32d8c8f34baacd6', 'US West (N. California)')
def get_ebs_pricing(id, location):
    global EBS_PRICE
    location = location.strip()

    try:
        # Getting the type and the size of the volume
        global ec2_resource, pricing
        volume = ec2_resource.Volume(id)
        volume_type = volume.volume_type
        volume_size = volume.size

        # Get price from the variable if Already calculated. This saves times and api requests

        if location in EBS_PRICE:  # Location is there.
            if volume_type in EBS_PRICE[location]:  # Price also there
                return EBS_PRICE[location][volume_type] * volume_size
        else:
            EBS_PRICE[location] = {}  # Price is not there. Create location dict.

        # Price info is not in variable. Calculate it.

        # Getting the price of the volume
        if volume_type == 'gp2':
            value = 'General Purpose'
        elif volume_type == 'io1':
            value = 'Provisioned IOPS'
        elif volume_type == 'st1':
            value = 'Throughput Optimized HDD'
        elif volume_type == 'sc1':
            value = 'Cold HDD'
        else:
            return float(0)  # Means Volume Type is Standard and 0 price for standard volumes

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
        EBS_PRICE[location][volume_type] = float(response)/30
        return EBS_PRICE[location][volume_type] * volume_size
    except:
        print (traceback.format_exc())
        print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Calculating Price of the Volume :' + id + ', Region :' + location)
        return 0


def get_volume_cost(instance, location):
    cost = 0
    volumes = instance.volumes.all()
    for volume in volumes:
        cost = cost + get_ebs_pricing(volume.id, location)
    return cost

def ec2_cost_calculation():
    global ec2_resource, REGION, REGION_NAME, VPC_ID, EC2_PRICE, EBS_PRICE
    ############################################INSTANCES AND IT'S IMPORTANT DATA(Filtered By Name Tag - mongo, cass) ARE RETRIEVED HERE###########################################################
    start = time.time()

    EC2_PRICE = {}
    EBS_PRICE = {}

    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'EC2 Cost Calculation(For Hours) Started')
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION:' + REGION)
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION NAME:' + REGION_NAME)
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'VPC ID:' + VPC_ID)

    instances = ec2_resource.instances.filter(
        Filters=[
            {'Name': 'vpc-id', 'Values': [VPC_ID]},   # If filtering by tag, vpc id is not required
            {'Name': 'tag:Environment', 'Values': [ENVIRONMENT]},  # if filtering by vpc id, environment and environment type not required
            {'Name': 'tag:EnvironmentType', 'Values': [ENVIRONMENT_TYPE]}
        ]
    )

    instance_count = 0
    total_volume_cost = 0
    total_instance_cost = 0

    for instance in instances:
        instance_count = instance_count + 1

        volume_cost = get_volume_cost(instance, REGION_NAME)
        instance_cost = get_ec2_pricing(instance.instance_type, REGION_NAME)

        print str(instance_count) + '. ' + 'Instance : ' + instance.id,
        print ' |  Volume Cost : $' + str(volume_cost),
        print ' |  Instance Cost : $' + str(instance_cost)

        total_volume_cost = total_volume_cost + volume_cost
        total_instance_cost = total_instance_cost + instance_cost

    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Processed ' + str(instance_count) + ' Instances'
    print 'Total Instance Cost(For Hour) : $' + str(total_instance_cost)
    print 'Total Volume Cost(For Hour) : $' + str(total_volume_cost)
    print 'Total Cost(For Hour) : $' + str(total_instance_cost + total_volume_cost)
    end = time.time()
    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'EC2 Cost Calculation Ended. Total Execution Time is ' + str(end - start) + ' Seconds'

    return 0



