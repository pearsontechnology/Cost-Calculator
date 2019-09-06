# -*- coding: utf-8 -*-
import boto3
from configparser import ConfigParser 
from influxdb import InfluxDBClient
import json
import os
from datetime import datetime
import requests
import time
import traceback

config = ConfigParser()
config.read(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'config.cfg')))

EBS_PRICE = {}
pricing = boto3.client('pricing', region_name="us-east-1")  # Pricing doesn't depends on provided region here

today = datetime.utcnow()
timestamp_today = time.mktime(today.timetuple())


# Get the Price for one day. Example: get_ebs_pricing('vol-0f32d8c8f34baacd6', 'US West (N. California)', 'us-west-1')
def get_ebs_pricing(id, location, region_name):
    global EBS_PRICE
    location = location.strip()

    try:
        # Getting the type and the size of the volume
        global ec2_resource, pricing
        ec2_resource = boto3.resource('ec2', region_name=region_name)

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

        EBS_PRICE[location][volume_type] = float(response) / 30 / 24
        return EBS_PRICE[location][volume_type] * volume_size
    except:
        print (traceback.format_exc())
        print (datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Calculating Price of the Volume :' + id + ', Region :' + location)
        return 0


def get_volume_cost(instance, region_name, region):
    cost = 0
    volumes = instance.volumes.all()
    for volume in volumes:
        cost = cost + get_ebs_pricing(volume.id, region_name, region)
    return cost


def ebs_cost_calculation(role,region, environment, environment_type, namespace):


    ec2_resource = boto3.resource('ec2', region_name=region)
    region_name = config.get('regions', region)

    #start = time.time()

    print (datetime.utcnow().strftime(
        '%Y-%m-%d %H:%M:%S') + ': ' + 'EBS Cost Calculation(Per Day) Started For ' + role)
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION:' + region)
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION NAME:' + region_name)

    instances = ec2_resource.instances.filter(
        Filters=[
            {'Name': 'tag:Environment', 'Values': [environment]},
            {'Name': 'tag:EnvironmentType', 'Values': [environment_type]},
            {'Name': 'tag:Role', 'Values': [role]},
            {'Name': 'tag:namespace', 'Values': [namespace]}
        ]
    )

    instance_count = 0
    total_volume_cost = 0

    for instance in instances:
        instance_count = instance_count + 1
        volume_cost = get_volume_cost(instance, region_name, region)

        #print str(instance_count) + '. ' + 'Instance : ' + instance.id,
        #print ' |  Volume Cost : $' + str(volume_cost),

        total_volume_cost = total_volume_cost + volume_cost

    #print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Processed ' + str(instance_count) + ' Instances'
    #print 'Total Volume Cost(For Day) : $' + str(total_volume_cost)
    #print 'Total Cost(For Day) : $' + str(total_volume_cost)
    #end = time.time()
    #print datetime.utcnow().strftime(
    #    '%Y-%m-%d %H:%M:%S') + ': ' + 'EBS Cost Calculation Ended for ' + role + '. Total Execution Time is ' + str(
    #    end - start) + ' Seconds'

    return total_volume_cost


def ebs_main_calc(region, environment, environment_type, role, namespace):
    roles = [role]
    total_ebs_cost = 0
    for role in roles:
        role_cost = ebs_cost_calculation(role,region, environment, environment_type, namespace)
        total_ebs_cost = total_ebs_cost + role_cost
    #    print 'Cost upto ' + role + ' $' + str(total_ebs_cost)
    #    print

    #print 'Total Cost For EBS(Per Day) : $' + str(total_ebs_cost)
    return total_ebs_cost
