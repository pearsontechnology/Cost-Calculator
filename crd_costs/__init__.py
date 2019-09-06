from .ec2_crd_cost import calc_ec2_based_crd_cost
from .neptune_crd_cost import calc_neptune_crd_cost
from pprint import pprint
def crd_cost_by_namespace(region,environment, environment_type,date,namespace):
    crd_namespace_costs = {}

    crd_namespace_costs.update(
        calc_ec2_based_crd_cost(date,region,environment,environment_type,namespace)
    )
    crd_namespace_costs.update(
        calc_neptune_crd_cost(date,region,environment,environment_type,namespace)
    )

    pprint(crd_namespace_costs)
    return crd_namespace_costs