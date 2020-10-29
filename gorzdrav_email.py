import requests
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

def write_log(subject, send_email=False, body_email=False):
    print(subject)
    if send_email:
        try:
            server = smtplib.SMTP_SSL('smtp.mail.ru', 465)
            server.login('', '')
            msg = EmailMessage()  # https://docs.python.org/3/library/email.examples.html#email-examples
            msg['Subject'] = subject
            msg['From'] = 'Gorzdrav Spb Bot ...'
            msg['To'] = '...'
            if body_email:
                msg.set_content(body_email)
            server.send_message(msg)
            server.quit()
            print('Email notification was sent successfully')
        except Exception as e:
            print('Email notification was not sent - error with email sending: ' + str(e))

write_log((datetime.utcnow() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S'))
# https://gorzdrav.spb.ru/service-free-schedule#%5B%7B%22district%22:%2211%22%7D,%7B%22lpu%22:%22147%22%7D%5D
gorzdrav_url = 'https://gorzdrav.spb.ru/_api/api/lpu/147/speciality'
#gorzdrav_url = 'http://metalcd-altnet.ru/'
#gorzdrav_url = 'http://metalcd-altnet.ru/speciality.json'
response = requests.get(gorzdrav_url)


if response.status_code == 200:
    try:
        json = response.json()
    except Exception as e:
        write_log('Could not parse page to JSON: ' + str(e), send_email=True, body_email=gorzdrav_url + '\r\n\r\nPage Text = \r\n' + response.text)
    else:
        specialty_id = '81'  # 81 - Травматолог-ортопед, 52 - Педиатр, 555 - несуществующая
        flag_find_specialty = 0
        for item in json['result']:
            if item['id'] == specialty_id:
                flag_find_specialty = flag_find_specialty + 1
                good_item = item

        if flag_find_specialty == 0:
            write_log('Parsing is working, but don\'t find any result for specialty_id: ' + specialty_id, send_email=True, body_email=gorzdrav_url)
        elif flag_find_specialty == 1:
            specialty_name = good_item['name']
            tickets = good_item['countFreeParticipant']
            if good_item['nearestDate'] is not None:
                nearest_date = good_item['nearestDate'][:10]
            else:
                nearest_date = None
            if good_item['lastDate'] is not None:
                last_date = good_item['lastDate'][:10]
            else:
                last_date = None

            if tickets > 0:
                write_log(specialty_name + '. Available tickets: ' + str(tickets) + '. Dates: ' + nearest_date + ' - '
                          + last_date, send_email=True, body_email='https://gorzdrav.spb.ru/service-free-schedule')
            else:
                write_log(
                    'No available tickets: ' + str(tickets) + '. specialty_id: ' + specialty_id + '. ' + specialty_name)

        else:
            write_log('Parsing is working, but find several results for specialty_id: ' + specialty_id, send_email=True,
                      body_email=gorzdrav_url)
else:
    write_log('Error at reguest Gorzdrav url. Response Status Code = ' + str(response.status_code), send_email=True, body_email=gorzdrav_url + '\r\n\r\nResponse Text = \r\n' + response.text)
    write_log('Response Text = \r\n' + response.text)


