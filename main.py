import schedule
import time

from application_cost import main_procedure

schedule.every().hour.at("00:00").do(main_procedure) ### RUNS EVERY HOUR At @HOUR:00
main_procedure()
while True:
    schedule.run_pending()
    time.sleep(1)
