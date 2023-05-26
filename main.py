import argparse
from datetime import datetime, timedelta
import logging
import sys
import notify2
import requests
import subprocess
from threading import Timer
import chime
import smtplib
from dotenv import dotenv_values
import os

LOGGING_FORMAT = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'


LOCATIONS = [
    #('SFO', 5446),
    ('BOS', 5441),
    #('LND', 5001),
    # ('LAX', 5180)
]

DELTA = 4  # Weeks
secrets = dotenv_values("secrets.env")
SCHEDULER_API_URL = 'https://ttp.cbp.dhs.gov/schedulerapi/locations/{location}/slots?startTimestamp={start}&endTimestamp={end}'
TTP_TIME_FORMAT = '%Y-%m-%dT%H:%M'

NOTIF_MESSAGE = 'New appointment slot open at {location}: {date}'
MESSAGE_TIME_FORMAT = '%A, %B %d, %Y at %I:%M %p'
past_notifications = []
def sendNotification(message, loc, date):
    notify2.init("Global Entry Notifier")
    notice = notify2.Notification("Global Entry Notifier", message)
    notice.show()
    if(str(loc)+str(date) not in past_notifications):
        # creates SMTP session
        s = smtplib.SMTP('smtp.gmail.com', 587)
         
        # start TLS for security
        s.starttls()
 
        # Authentication
        s.login(secrets["FROM_EMAIL"], secrets["EMAIL_PASSWORD"])

        sent_from = secrets["FROM_EMAIL"]
        sent_to = [secrets["TO_EMAIL"]]
        sent_subject = "{} global entry location has an open appointment!".format(loc)
        sent_body = ("There is an available appointment at the {} location on {}".format(loc, date))
        email_text = """\
        From: %s
        To: %s
        Subject: %s

        %s
        """ % (sent_from, ", ".join(sent_to), sent_subject, sent_body)
        # sending the mail
        s.sendmail(sent_from, sent_to, email_text)
     
        # terminating the session
        s.quit()
        past_notifications.append(str(loc)+str(date))

        if(len(past_notifications)>20):
    	    past_notifications.pop(0)
    return
    
def check_for_openings(location_name, location_code, test_mode=True):
    start = datetime.now() + timedelta(days=1)
    end = start + timedelta(weeks=DELTA)

    url = SCHEDULER_API_URL.format(location=location_code,
                                   start=start.strftime(TTP_TIME_FORMAT),
                                   end=end.strftime(TTP_TIME_FORMAT))
    try:
        results = requests.get(url).json()  # List of flat appointment objects
    except requests.ConnectionError:
        logging.exception('Could not connect to scheduler API')
        sys.exit(1)

    for result in results:
        if result['active'] > 0:
            logging.info('Opening found for {}'.format(location_name))

            timestamp = datetime.strptime(result['timestamp'], TTP_TIME_FORMAT)
            message = NOTIF_MESSAGE.format(location=location_name,
                                           date=timestamp.strftime(MESSAGE_TIME_FORMAT))
            if test_mode:
                print(datetime.now().strftime("%H:%M:%S")+" "+message)
                sendNotification(message, location_name, timestamp)
                chime.success()
            else:
                logging.info('Notifying: ' + message)
                sendNotification(message)
            return  # Halt on first match

    logging.info('No openings for {}'.format(location_name))

def check_locations():
    for location_name, location_code in LOCATIONS:
        check_for_openings(location_name, location_code, True)

    Timer(60, check_locations).start()

def main():


    parser = argparse.ArgumentParser()
    parser.add_argument('--test', '-t', action='store_true', default=False)
    parser.add_argument('--verbose', '-v', action='store_true', default=False)
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format=LOGGING_FORMAT,
                            level=logging.INFO,
                            stream=sys.stdout)

    logging.info('Starting checks (locations: {})'.format(len(LOCATIONS)))
    check_locations()

        

if __name__ == '__main__':
    main()
