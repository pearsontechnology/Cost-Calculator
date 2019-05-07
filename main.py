import ConfigParser as cp
from influxdb import InfluxDBClient
import json
from kubernetes import client, config, watch
import os
from datetime import datetime
import schedule
import requests
import time

from pod_cost import mainProcedure
from filter import filteringJOB, filterFirstTime, cleanupFilteredBackOff
from ec2_cost_calculation import ec2_cost_calculation
from integrate import cluster_costing


def filteringAndCalculation():
    filteringJOB()
    filterFirstTime()
    cleanupFilteredBackOff()
    mainProcedure()

schedule.every().hour.at("00:30").do(filteringJOB) ### RUNS EVERY HOUR At @HOUR:30
schedule.every().hour.at("00:00").do(cluster_costing) ### RUNS EVERY HOUR At @HOUR:00
schedule.every().day.at("00:05").do(filteringAndCalculation) ### RUNS EVERY DAY At 00:05

filteringAndCalculation()

while True:
    schedule.run_pending()
    time.sleep(1)
