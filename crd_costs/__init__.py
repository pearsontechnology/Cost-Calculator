from .ec2_crd_cost import calc_ec2_based_crd_cost
from .neptune_crd_cost import calc_neptune_crd_cost
from .rds_crd_cost import calc_rds_crd_cost

from pprint import pprint
from datetime import datetime

def crd_cost_by_namespace(region,environment, environment_type,date,namespace,debug=True):
    print(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' +
                    'CRD Cost Calculation for ' + namespace)
    crd_namespace_costs = {}

    crd_namespace_costs.update(
        calc_ec2_based_crd_cost(date,region,environment,environment_type,namespace,debug)
    )
    crd_namespace_costs.update(
        calc_neptune_crd_cost(date,region,environment,environment_type,namespace,debug)
    )
    crd_namespace_costs.update(
        calc_rds_crd_cost(date,region,environment,environment_type,namespace,debug)
    )
    if debug:
        pprint(crd_namespace_costs)
    return crd_namespace_costs