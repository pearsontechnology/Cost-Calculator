import boto3
import traceback
from datetime import datetime,timedelta

def call_ce(date, region, service,tags):

    client = boto3.client('ce')
    str_start_date = date
    start_date = datetime.strptime(date, '%Y-%m-%d')
    end_date = start_date + timedelta(days=1)
    str_end_date = end_date.strftime('%Y-%m-%d')

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
                            'Values': [
                                service
                            ],
                        }
                    }
                    ,
                    {
                        'Dimensions': {
                            'Key': 'REGION',
                            'Values': [
                                region
                            ],
                        }
                    }
                    ,
                    {
                        'Tags': tags
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
        print ( "(" + service + "): $" + str(unblended_cost))
        return float(unblended_cost)

    except:
        print (traceback.format_exc())
        print (datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S') + ': ' + 'Error in Getting the cost of ' + service + ', Region :' + region)
        return 0.0