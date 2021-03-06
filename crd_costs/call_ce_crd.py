import boto3
import traceback
from datetime import datetime, timedelta


def call_ce_crd(date, region, services, tags,debug=True):

    client = boto3.client('ce')
    str_start_date = date.strftime('%Y-%m-%d')
    end_date = date + timedelta(days=1)    
    str_end_date = end_date.strftime('%Y-%m-%d')
    return_cost = 0.0

    for service in services:
        try:
            response = client.get_cost_and_usage(
                TimePeriod={
                    'Start': str_start_date,
                    'End': str_end_date
                },
                Granularity='MONTHLY',
                Filter={
                    'And': [
                        {
                            'Dimensions': {
                                'Key': 'SERVICE',
                                'Values': [service]
                            }
                        },
                        {
                            'Dimensions': {
                                'Key': 'REGION',
                                'Values': [
                                    region
                                ],
                            }
                        },
                        {
                            'Tags': {
                                "Key":"Name",
                                "Values":tags                            
                            }
                        }
                    ]
                },
                GroupBy=[
                    {
                        'Type': 'DIMENSION',
                        'Key': 'SERVICE'
                    }
                ],
                Metrics=[
                    'UnblendedCost'
                ]
            )

            unblended_cost = response['ResultsByTime'][0]['Groups'][0]['Metrics']['UnblendedCost']['Amount']
            if debug:
                print ("(" + service + "): $" + str(unblended_cost))
            return_cost += float(unblended_cost)

        except:
            print (datetime.utcnow().strftime(
                '%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Getting the cost of ' + service + ', Region :' + region)
            if debug:
                print (traceback.format_exc())
            return_cost += 0.0

    return float(return_cost) /24.0
