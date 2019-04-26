#!/bin/bash

apt-get update
apt-get install python curl -y
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python get-pip.py
pip install schedule
pip install kubernetes
pip install influxdb
pip install boto3
python /app/main.py
