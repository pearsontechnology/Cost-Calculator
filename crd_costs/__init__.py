from kubernetes import kubernetes
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import os
from datetime import datetime,timedelta
from ec2_crd_cost import calc_ec2_based_crd_cost
from neptune_crd_cost import calc_neptune_crd_cost
from pprint import pprint

def crd_cost_by_namespace(date,region,environment, environment_type, namespace):
    crd_namespace_costs = {}

    crd_namespace_costs.update(
        calc_ec2_based_crd_cost(date,region,environment,environment_type,namespace)
    )
    crd_namespace_costs.update(
        calc_neptune_crd_cost(date,region,environment,environment_type,namespace)
    )

    pprint(crd_namespace_costs)
    return crd_namespace_costs

config.load_kube_config()
v1 = client.CoreV1Api()

namespaces = v1.list_namespace()
ENVIRONMENT = os.environ['ENVIRONMENT'] if "ENVIRONMENT" in os.environ else "glp1" 
ENVIRONMENT_TYPE = os.environ['ENVIRONMENT_TYPE'] if "ENVIRONMENT_TYPE" in os.environ else "pre"

cost_date = datetime.now() - timedelta(days=2) 
for namespace in namespaces.items:
    namespace_name = namespace.metadata.name
    crd_cost_by_namespace(datetime.strftime(cost_date, '%Y-%m-%d'),"us-east-2",ENVIRONMENT, ENVIRONMENT_TYPE, namespace_name)