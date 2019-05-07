# -*- coding: utf-8 -*-
import ConfigParser as cp
import boto3
import json
from datetime import datetime
import time
import traceback
import re
import os

# Note: This does not calculate DATA TRANSFER, BACKUP STORAGE cost.
# Note: This does not calculate DATA TRANSFER, BACKUP STORAGE cost.
# Note: This does not calculate DATA TRANSFER, BACKUP STORAGE cost.
# Note: This does not calculate DATA TRANSFER, BACKUP STORAGE cost.
# Note: This does not calculate DATA TRANSFER, BACKUP STORAGE cost.

config = cp.RawConfigParser()
config.read(os.path.dirname(os.path.abspath(__file__)) + '/config.cfg')

REGION = os.environ['REGION']
REGION_NAME = config.get('regions', REGION)
ENVIRONMENT = os.environ['ENVIRONMENT']
ENVIRONMENT_TYPE = os.environ['ENVIRONMENT_TYPE']

VPC_ID = 'vpc-ff8af197'

client = boto3.client('rds', region_name=REGION)
pricing = boto3.client('pricing')


# Get the price of the RDS. Example : getRDSPricing('db.t2.large', 'South America (Sao Paulo)', 'Single-AZ',
# 'PostgreSQL')
def get_rds_pricing(type, location, availability, engine):
    # Availability : Single-AZ, Multi-AZ
    # engine : Oracle, MySQL, PostgreSQL,
    global pricing
    try:
        service_code = 'AmazonRDS'
        if engine == "Amazon Neptune":
            service_code = 'AmazonNeptune'
            availability = 'MultiAZ'

        response = pricing.get_products(
            ServiceCode=service_code, MaxResults=100,
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': type},
                {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': engine},
                {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': availability},
            ]
        )
        response = json.loads(response['PriceList'][0])['terms']['OnDemand']
        key = response.keys()[0]
        response = response[key]['priceDimensions']
        key = response.keys()[0]
        response = response[key]['pricePerUnit']['USD']
        return float(response)
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Calculating Cost for RDS :' + type + ' ' + location + ' ' + availability + ' ' + engine
        return 0


def get_rds_storage_pricing(type, location, availability, engine):
    # Availability : Single-AZ, Multi-AZ
    # engine : Oracle, MySQL, PostgreSQL,
    print type, location, availability, engine
    global pricing
    try:
        service_code = 'AmazonRDS'
        if engine == "Amazon Neptune":
            service_code = 'AmazonNeptune'
            availability = 'MultiAZ'

        response = pricing.get_products(
            ServiceCode=service_code, MaxResults=100,
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Database Storage'},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                {'Type': 'TERM_MATCH', 'Field': 'storageMedia', 'Value': 'SSD'},
                {'Type': 'TERM_MATCH', 'Field': 'volumeType', 'Value': 'General Purpose'},
                {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': availability},
            ]
        )
        response = json.loads(response['PriceList'][0])['terms']['OnDemand']
        key = response.keys()[0]
        response = response[key]['priceDimensions']
        key = response.keys()[0]
        response = float(response[key]['pricePerUnit']['USD']) / 24 / 30
        print "Per hour storage cost rate: ", response
        return float(response)
    except:
        print (traceback.format_exc())
        print datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Calculating Cost for RDS :' + type + ' ' + location + ' ' + availability + ' ' + engine
        return 0


def rds_cost():
    global REGION, REGION_NAME, VPC_ID

    start = time.time()

    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'RDS Cost Calculation(For a Hour) Started')
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION:' + REGION)
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'REGION NAME:' + REGION_NAME)
    # print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'VPC ID:' + VPC_ID)

    total_instance_cost = 0
    instance_count = 0
    db_instances = client.describe_db_instances()['DBInstances']

    for db_instance in db_instances:
        db_instance_name = db_instance['DBInstanceIdentifier']
        if re.search('grafana', db_instance_name) and re.search(ENVIRONMENT, db_instance_name) \
                and re.search(ENVIRONMENT_TYPE, db_instance_name):
            arn = db_instance['DBInstanceArn']
            instance_class = db_instance['DBInstanceClass']
            availability = 'Single-AZ'
            engine = db_instance['Engine']

            # if db_instance['DBSubnetGroup']['VpcId'] != VPC_ID:
            #     print datetime.utcnow().strftime(
            #         '%Y-%m-%d %H:%M:%S') + ': ' + 'RDS Not in Same VPC : ' + arn + '. Excluding From Calculation...'
            #     continue
            instance_count = instance_count + 1

            if engine == 'postgres':
                engine = 'PostgreSQL'
            elif engine == 'mysql':
                engine = 'MySQL'
            elif engine == 'aurora-mysql':
                engine = 'Aurora MySQL'
            elif engine == 'mariadb':
                engine = 'MariaDB'
            elif engine == 'neptune':
                engine = 'Amazon Neptune'
            else:
                print datetime.utcnow().strftime(
                    '%Y-%m-%d %H:%M:%S') + ': ' + 'Unknown DB Engine Detected. It must be other than MySQL, Aurora, MariaDB and PostgreSQL. ARN:' + arn + ' Engine: ' + engine
                continue
            if db_instance['MultiAZ']:
                availability = 'Multi-AZ'

            cost = get_rds_pricing(instance_class, REGION_NAME, availability, engine)
            storage_cost = get_rds_storage_pricing(instance_class, REGION_NAME, availability, engine) * int(
                db_instance['AllocatedStorage'])
            rds_tot_cost = cost + storage_cost

            print str(instance_count) + '. ' + 'DB Instance : ' + arn,
            print ' |  Instance Cost : $' + str(cost),
            print ' |  Volume Cost : $' + str(storage_cost),
            print ' |  Total Cost : $' + str(rds_tot_cost)

            total_instance_cost = total_instance_cost + rds_tot_cost

    print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'Processed ' + str(instance_count) + ' Instances'
    print 'Total Cost(For This Hour) : $' + str(total_instance_cost)
    end = time.time()
    print datetime.utcnow().strftime(
        '%Y-%m-%d %H:%M:%S') + ': ' + 'RDS Cost Calculation Ended. Total Execution Time is ' + str(
        end - start) + ' Seconds'
    return total_instance_cost


# get_rds_pricing('db.r4.4xlarge', 'US East (Ohio)', 'Single-AZ', 'Amazon Neptune')
# rds_cost()
