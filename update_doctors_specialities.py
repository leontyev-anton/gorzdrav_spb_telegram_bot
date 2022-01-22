# этот скрипт делает обновление списка докторов -> достаточно обновление раз в день
import smtplib
import sys
import time
from datetime import datetime, timedelta
from email.message import EmailMessage

import pandas
import requests
from config import pg_host, pg_user, pg_pass, pg_db, email_server, email_port, email_user, email_pass, email_notification
from sqlalchemy import create_engine

def log(text, end='\r\n', admin=False):
    print(text, end=end)
    if admin:
        send_email(text)

def send_email(text):
    try:
        server = smtplib.SMTP_SSL(email_server, email_port)
        server.login(email_user, email_pass)
        msg = EmailMessage()  # дока https://docs.python.org/3/library/email.examples.html#email-examples
        msg['Subject'] = ''  # тема пустая, тк тексты ошибок туда опасно отправлять - переходы на новую строку и еще непонятно что там может быть
        msg['From'] = 'Gorzdrav Update Doctors Specialities <' + email_user + '>'
        msg['To'] = email_notification
        msg.set_content(text)
        server.send_message(msg)
        server.quit()
        log('Email notification was sent successfully')
    except Exception as e:
        log('Email notification was not sent - error with email sending: ' + str(e) )

my_headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36',
              'Referer': 'https://gorzdrav.spb.ru/service-free-schedule',
              'X-Requested-With': 'XMLHttpRequest'}  # чтобы не выглядеть как бот, будем отправлять запросы с этими заголовками

datetime_now = datetime.utcnow() + timedelta(hours=3)
log('Start:  ' + datetime_now.strftime('%Y-%m-%d %H:%M:%S' + '. '), end='')
pg = create_engine('postgresql://' + pg_user + ':' + pg_pass + '@' + pg_host + '/' + pg_db)
try:
    #specialities = pandas.read_sql(sql="SELECT speciality_id, name, lpu_id FROM specialities WHERE speciality_id='2'", con=pg)
    specialities = pandas.read_sql(sql="SELECT speciality_id, name, lpu_id FROM specialities", con=pg)
except Exception as e:
    log(f'Exit script. Error requesting specialities from Postgres: {e}', admin=True)
else:
    df_doctors = pandas.DataFrame()
    for i in specialities.index:
        #if specialities['speciality_id'][i] == '2' or specialities['speciality_id'][i] == '8' or specialities['speciality_id'][i] == '19':  # 19 - с нулем докторов
        url = 'https://gorzdrav.spb.ru/_api/api/v2/schedule/lpu/' + specialities['lpu_id'][i] + '/speciality/' + specialities['speciality_id'][i] + '/doctors'
        repeat = True   # сделаем 3 попытки на запрос
        iterations = 0
        while repeat:
            try:
                iterations += 1
                response = requests.get(url, headers=my_headers)
                success = response.json()['success']
                message = ''; exceptionMessage = ''
                if success == False:
                    message = response.json()['message']
                    exceptionMessage = response.json()['exceptionMessage']
                json = response.json()['result']
                repeat = False
            except Exception as e:
                if iterations == 3:
                    log(f'Exit script. Error parsing from JSON: {e}, after {iterations} iterations, exceptionMessages: '
                        f'{message} {exceptionMessage}, url[{i}] = {url}', admin=True)
                    sys.exit(1)
                else:
                    time.sleep(10 * iterations)
        try:
            df_doctor = pandas.DataFrame.from_dict(json)
            df_doctor.drop(['ariaNumber', 'ariaType', 'freeParticipantCount', 'freeTicketCount', 'lastDate', 'nearestDate'], inplace=True, axis=1)
        except:
            pass
        else:
            df_doctor['speciality_id'] = specialities['speciality_id'][i]
            df_doctor['speciality_name'] = specialities['name'][i]
            df_doctor['lpu_id'] = specialities['lpu_id'][i]
            df_doctors = df_doctors.append(df_doctor, ignore_index=True)
            time.sleep(5)


    if len(df_doctors) >= 46 and len(df_doctors) <= 57:
        try:
            df_doctors = df_doctors.rename(columns={'id': 'doctor_id'})
            df_doctors.to_sql(name='doctors', con=pg, if_exists='replace', index=False)
        except Exception as e:
            log(f'Exit script. Error updating {len(df_doctors)} doctors in Postgres: {e}', admin=True)
        else:
            log(f'{len(df_doctors)} doctors are successfully updated in Postgres')
            datetime_now = datetime.utcnow() + timedelta(hours=3)
            log('Finish:  ' + datetime_now.strftime('%Y-%m-%d %H:%M:%S' + '. '))
    else:
        log(f'Exit script. Doctors less then 46 or more 57: {len(df_doctors)}. No update Postgres', admin=True)

