import time
from datetime import datetime
from application_cost import main_procedure

print datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + ': ' + 'No Import Errors -> Running Procedure'

while True:
    main_procedure()
    time.sleep(60*60)
