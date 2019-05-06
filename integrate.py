# -*- coding: utf-8 -*-
import boto3
import ConfigParser as cp
from influxdb import InfluxDBClient
import json
from kubernetes import client, config, watch
import os
from datetime import datetime
import schedule
import requests
import time
import kubernetes

from ec2_cost import ec2_main_calc
from rds_cost import rds_cost
from elb import elb_cost
from es_cost_v2 import get_es_total_cost

config_1 = cp.RawConfigParser()
config_1.read(os.path.dirname(os.path.abspath(__file__))+'/config.cfg')

REGION = config_1.get('regions', 'default')
REGION_NAME = config_1.get('regions', REGION)
ENVIRONMENT = os.environ['ENVIRONMENT']
ENVIRONMENT_TYPE = os.environ['ENVIRONMENT_TYPE']
VPC_ID = 'vpc-ff8af197'

# Inserting into final calculation table
def insertFinalClusterCalc(timestamp, date, ENVIRONMENT, ec2_cost, rds_cost, elb_cost, es_cost, total_cost):
    global client
    data = [
        {
            "measurement": "final_cluster_calculation",
            "tags": {
                "environment": str(ENVIRONMENT),
                "date": date

            },
            "fields": {
                "ec2_cost": ec2_cost,
                "rds_cost": rds_cost,
                "elb_cost": elb_cost,
                "es_cost": es_cost,
                "total_cost": total_cost
                #"Cost": cost

            }
        }
    ]
    try:
        client.write_points(data)
        print 'inserted event record: ' + str(timestamp) + ', ' + ENVIRONMENT + ' cost: ' + str(total_cost)

    except:
        writeToFile("error-calc.log", "Error inserting data: " + str(ENVIRONMENT))

def cluster_costing():
    cost_ec2 = ec2_main_calc
    cost_rds = rds_cost()
    cost_es = get_es_total_cost()
    cost_elb = elb_cost()
    cost_total = cost_ec2 + cost_elb+ cost_es + cost_rds
    insertFinalClusterCalc(timestamp_today, today, ENVIRONMENT, cost_ec2, cost_rds, cost_elb, cost_es, cost_total)
    return cost_total
