# этот скрипт делает обновление списка докторов -> достаточно обновление раз в день

import pandas
import requests
import sys
import time
import smtplib
from config import pg_host, pg_user, pg_pass, pg_db, email_server, email_port, email_user, email_pass, email_notification
from datetime import datetime, timedelta
from email.message import EmailMessage
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



datetime_now = datetime.utcnow() + timedelta(hours=3)
log('Start:  ' + datetime_now.strftime('%Y-%m-%d %H:%M:%S' + '. '), end='')
pg = create_engine('postgresql://' + pg_user + ':' + pg_pass + '@' + pg_host + '/' + pg_db)
try:
    specialities = pandas.read_sql(sql='SELECT speciality_id, name, lpu_id FROM specialities', con=pg)
except Exception as e:
    log(f'Exit script. Error requesting specialities from Postgres: {e}', admin=True)
else:
    df_doctors = pandas.DataFrame()
    for i in specialities.index:
        #if specialities['speciality_id'][i] == '2' or specialities['speciality_id'][i] == '8' or specialities['speciality_id'][i] == '19':  # 19 - с нулем докторов
        url = 'https://gorzdrav.spb.ru/_api/api/lpu/' + specialities['lpu_id'][i] + '/doctor?specialityId=' + specialities['speciality_id'][i]
        try:
            response = requests.get(url)
            json = response.json()
            json = json['result']
        except Exception as e:
            log(f'Exit script. Error parsing from JSON: {e}, url={url}', admin=True)
            sys.exit(1)
        else:
            try:
                df_doctor = pandas.DataFrame.from_dict(json)
                df_doctor.drop(['areaNumber', 'areaType', 'freeParticipantCount', 'freeTicketCount', 'lastDate', 'nearestDate'], inplace=True, axis=1)
            except:
                pass
            else:
                df_doctor['speciality_id'] = specialities['speciality_id'][i]
                df_doctor['speciality_name'] = specialities['name'][i]
                df_doctor['lpu_id'] = specialities['lpu_id'][i]
                df_doctors = df_doctors.append(df_doctor, ignore_index=True)
                time.sleep(1)


    if len(df_doctors) >= 50 and len(df_doctors) <= 55:
        try:
            df_doctors = df_doctors.rename(columns={'id': 'doctor_id'})
            df_doctors.to_sql(name='doctors', con=pg, if_exists='replace', index=False)
        except Exception as e:
            log(f'Exit script. Error updating {len(df_doctors)} doctors in Postgres: {e}', admin=True)
        else:
            log(f'{len(df_doctors)} doctors are successfully updated in Postgres')
            datetime_now = datetime.utcnow() + timedelta(hours=3)
            log('Finish:  ' + datetime_now.strftime('%Y-%m-%d %H:%M:%S' + '. '), end='')
    else:
        log(f'Exit script. Doctors less then 51 or more 55: {len(df_doctors)}. No update Postgres', admin=True)


# DROP TABLE IF EXISTS records
#
# CREATE TABLE records
# (
#    lpu_id TEXT,
#    speciality_id TEXT,
#    doctor_id  TEXT,
#    notification_days INT,
#    chat_id INT,
#    date_creating TIMESTAMP,
#    date_deleting TIMESTAMP,
#    record_id SERIAL PRIMARY KEY
# );
#
# INSERT INTO records (lpu_id, speciality_id, doctor_id, notification_days, chat_id, date_creating, date_deleting)
#    VALUES ('147', '8', NULL, 10, '95453211', CAST('2020-11-19' AS TIMESTAMP), NULL);
#
# INSERT INTO records (lpu_id, speciality_id, doctor_id, notification_days, chat_id, date_creating, date_deleting)
#    VALUES ('147','52', '311', 10, '95453211', CAST('2020-11-19' AS TIMESTAMP), NULL);





# CREATE TRIGGER update_specialities AFTER UPDATE ON specialities
#     FOR EACH ROW --WHEN (OLD.name IS DISTINCT FROM NEW.name)
#     EXECUTE PROCEDURE update_specialities();
#
# CREATE OR REPLACE FUNCTION update_specialities() RETURNS trigger AS $$
# BEGIN
#    UPDATE records
#       SET speciality_name = CONCAT(NEW.name,'1')
#    WHERE records.speciality_id = NEW.speciality_id;
#    RETURN NEW;
# END;
# $$ LANGUAGE  plpgsql;
#
# DROP FUNCTION update_specialities() CASCADE;
#
# UPDATE specialities SET name = 'Гастроэнтерл' WHERE speciality_id='8';
#
# SELECT EXISTS (
#     SELECT  tgenabled
#     FROM    pg_trigger
#     WHERE   tgname='update_specialities' --AND
#             --tgenabled != 'D'
# );
#
# DELETE FROM specialities WHERE 1=1;