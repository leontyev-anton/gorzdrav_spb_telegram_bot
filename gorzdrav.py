# в этом файле описан парсер свободных талончиков -> должен запускаться раз в N минут
# вернуть в лог время старта скрипта

import requests
import sys
import time
import pandas
import urllib.parse
import smtplib
from config import pg_host, pg_user, pg_pass, pg_db, tg_bot_token, tg_chat_id_admin, email_server, email_port, \
    email_user, email_pass, email_notification
from sqlalchemy import create_engine  # кажется pandas только через нее может
from datetime import datetime, timedelta
from email.message import EmailMessage

def myexit(exitcode=0):
    global message_admin
    if len(message_admin) > 0:
        send_to_admin(message_admin, tg_bot_token, email_title_from='Gorzdrav Parser')
    sys.exit(exitcode)

def log(text, end='\r\n', admin=False):
    global message_admin
    print(text, end=end)
    if admin:
        message_admin += text + end

def send_to_admin(text, bot_token, email_title_from='Gorzdrav'):  # вынести в отдельный файл
    url_tg = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + tg_chat_id_admin + '&text=' + text
    try:
        response = requests.get(url_tg)
    except Exception as e:
        log(f'Script continues. Telegram admin notification sending error: {e}', admin=True)
    else:
        response_ok = ''
        if response.status_code == 200:
            try:    response_ok = response.json()['ok']
            except: pass
            else:   pass
        if response_ok == True:
            log ('Notification has been successfully sent to admin by telegram')
        else:
            log(f'Script continues. Notification hasn\'t been sent to admin by the telegram, response.status_code = {response.status_code}, response json ok = {response_ok}', admin=True)
            try:
                server = smtplib.SMTP_SSL(email_server, email_port)
                server.login(email_user, email_pass)
                msg = EmailMessage()  # дока https://docs.python.org/3/library/email.examples.html#email-examples
                msg['Subject'] = ''  # тема пустая, тк тексты ошибок туда опасно отправлять - переходы на новую строку и еще непонятно что там может быть
                msg['From'] = email_title_from + ' <' + email_user + 'u>'
                msg['To'] = email_notification
                msg.set_content(message_admin)
                server.send_message(msg)
                server.quit()
                log('Email notification to admin was sent successfully')
            except Exception as e:
                log('Email notification to admin was not sent - error with email sending: ' + str(e))


pg = create_engine('postgresql://' + pg_user + ':' + pg_pass + '@' + pg_host + '/' + pg_db)
#lpus = [{'id': '147', 'name': 'ул. Костюшко, д. 4'}, {'id': '112', 'name': 'пр. Ленинский, д. 168, к. 2'}]
#lpus = [{'id': '147', 'name': 'ул. Костюшко, д. 4'}]
lpus = [{'id': '112', 'name': 'пр. Ленинский, д. 168, к. 2'}]
#lpus = [{'id': '459', 'name': 'Поликлиника №48, ул. Благодатная 18'}]
#нужно дописать чтобы заменить заголовки - чтобы выглядели как у нормального юзера
my_headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36',
              'Referer': 'https://gorzdrav.spb.ru/service-free-schedule',
              'X-Requested-With': 'XMLHttpRequest'}  # чтобы не выглядеть как бот, будем отправлять запросы с этими заголовками

#url_spec_prefix = 'http://metalcd-altnet.ru/speciality'; url_spec_postfix = '.json';
#url_doctors_prefix = 'http://metalcd-altnet.ru/doctor'; url_doctors_postfix = '.json';
url_spec_prefix = 'https://gorzdrav.spb.ru/_api/api/v2/schedule/lpu/'; url_spec_postfix = '/specialties';
url_doctors_prefix = 'https://gorzdrav.spb.ru/_api/api/v2/schedule/lpu/'; url_doctors_middle = '/speciality/' ; url_doctors_postfix = '/doctors';
message_admin=''
# запросим records из Postgres
try:
    df_records = pandas.read_sql(sql='SELECT record_id, lpu_id, speciality_id, doctor_id, notification_days, chat_id, username FROM records WHERE date_deleting IS NULL', con=pg)
except Exception as e:
    log(f'Exit script. Error requesting records from Postgres: {e}', admin=True)
    myexit(1)

log(f'\rWe will search {len(df_records)} records ({len(df_records[df_records["speciality_id"].notnull()])} specialities, '
    f'{len(df_records[df_records["doctor_id"].notnull()])} doctors) from {df_records["chat_id"].nunique()} users')

#распарсим специальности из двух lpu gorzdrav'a
df_specialities = pandas.DataFrame()
for lpu in lpus:
    url = url_spec_prefix + lpu['id'] + url_spec_postfix
    repeat = True    # сделаем 3 попытки на запрос
    iterations = 0
    while repeat:
        try:
            iterations += 1
            r_specialities = requests.get(url, headers=my_headers)
            success = r_specialities.json()['success']
            message = ''; exceptionMessage = ''
            if success == False:
                message = r_specialities.json()['message']
                exceptionMessage = r_specialities.json()['exceptionMessage']
            df = pandas.DataFrame.from_dict(r_specialities.json()['result'])
            df['lpu_id'] = lpu['id']
            df['lpu_name'] = lpu['name']
            df_specialities = df_specialities.append(df, ignore_index=True)
            repeat = False
        except Exception as e:
            if iterations == 3:
                log(f'Exit script. Error parsing speciality url {url} to DataFrame: {e}, after {iterations} iterations, '
                    f'exceptionMessages: {message} {exceptionMessage}', admin=True)
                myexit(1)
            else:
                time.sleep(10 * iterations)

#запишем специальности в postgres
df_specialities = df_specialities.rename(columns={'id': 'speciality_id'})
if len(df_specialities) >= 8 and len(df_specialities) <= 20:  # все хорошо, обновляем список в postgres
    try:
        #df_specialities = df_specialities.rename(columns={'id': 'speciality_id'})  # было тут, а потом перенес наверх
        df_specialities_pg = df_specialities.copy()  # скопируем, тк нам в postgres нужно записать только часть полей
        df_specialities_pg.drop(['ferId', 'countFreeParticipant', 'countFreeTicket', 'lastDate', 'nearestDate'], inplace=True, axis=1)
        df_specialities_pg.to_sql(name='specialities', con=pg, if_exists='replace', index=False)  # на это изменение триггер никак не срабатывает (даже DELETE строки, а потом APPEND). Еще можно через ручной запуск функции, но это лишняя нагрузка на базу (будет все поля проходить).
    except Exception as e:
        log(f'Script continues. Error with updating {len(df_specialities)} specialities in Postgres: {e}', admin=True)
    else:
        log(f'{len(df_specialities)} specialities are successfully updated in Postgres')
else:
    log(f'Script continues. Specialities amount: {len(df_specialities)} is not normal. No update Postgres', admin=True)  # почему-то для пустого JSON выдает 1, как только не пробовал


# сначала выберем lpu_id и speciality_id, где нужно искать доктора
df_records_doctors = df_records[df_records['doctor_id'] != None].drop_duplicates(subset=['lpu_id', 'speciality_id'])
# распарсим этих докторов
df_doctors = pandas.DataFrame()
for i in df_records_doctors.index:
    url = url_doctors_prefix + df_records_doctors['lpu_id'][i] + url_doctors_middle + df_records_doctors['speciality_id'][i] + url_doctors_postfix
    try:
        r_doctors = requests.get(url, headers=my_headers)
        df = pandas.DataFrame.from_dict(r_doctors.json()['result'])
        df['lpu_id'] = df_records_doctors['lpu_id'][i]
        for lpu in lpus:
            if lpu['id'] == df_records_doctors['lpu_id'][i]:
                lpu_name = lpu['name']
        df['lpu_name'] = lpu_name
        df = df.rename(columns={'id': 'doctor_id'})
        df_doctors = df_doctors.append(df, ignore_index=True)
    except Exception as e:
        log(f'Exit script. Error parsing doctor url {url} to DataFrame: {e}', admin=True)
        myexit(1)

# так было, когда можно было запросить всех докторов учреждения одной страницей
# for lpu in lpus:
#     if len(df_records[df_records['lpu_id'] == lpu['id']]) > 0:  # если в records есть этот lpu, то распарсим его url
#         url = url_doctors_prefix + lpu['id'] + url_doctors_postfix
#         try:
#             r_doctors = requests.get(url, headers=my_headers)
#             df = pandas.DataFrame.from_dict(r_doctors.json()['result'])
#             df['lpu_id'] = lpu['id']
#             df['lpu_name'] = lpu['name']
#             df = df.rename(columns={'id': 'doctor_id'})
#             df_doctors = df_doctors.append(df, ignore_index=True)
#         except Exception as e:
#              log(f'Exit script. Error parsing doctor url to DataFrame: {e}', admin=True)
#              myexit(1)



# разберем каждый элемент records и дополним его тем, что найдем в двух списках с gorzdrav'a
df_records['available_tickets'] = None
df_records['first_date'] = None
df_records['last_date'] = None
df_records['speciality_name'] = None
df_records['doctor_name'] = None
df_records['lpu_name'] = None
records = df_records.to_dict('records')  # переведем в словарь, тк с ним читабельней код дальше. может выше при парсинге отказаться от pandas?
for record in records:
    if record['doctor_id'] == None:  # ищем специальности
        for i in df_specialities.index:  # (datetime.strptime(df_specialities['nearestDate'][i])[:10], '%Y-%m-%d')
            if df_specialities['nearestDate'][i] != None:  # иначе ошибку выдает на strptime
                # notification_days в postgres таблице records: -1 - без уведомлений. 0 - только на сегодня и т.д
                days = (datetime.strptime(str(df_specialities['nearestDate'][i])[:10], '%Y-%m-%d') - datetime.strptime((datetime.utcnow() + timedelta(hours=3)).strftime('%Y-%m-%d'), '%Y-%m-%d')).days
                if df_specialities['speciality_id'][i] == record['speciality_id'] and df_specialities['lpu_id'][i] == record['lpu_id'] \
                        and df_specialities['countFreeParticipant'][i] > 0 and days <= record['notification_days']:
                    record['available_tickets'] = df_specialities['countFreeParticipant'][i]
                    record['first_date'] = df_specialities['nearestDate'][i][:10]
                    record['last_date'] = df_specialities['lastDate'][i][:10]
                    record['speciality_name'] = df_specialities['name'][i]
                    record['lpu_name'] = df_specialities['lpu_name'][i]
    else:  # иначе ищем конкретного доктора
        for i in df_doctors.index:
            if df_doctors['nearestDate'][i] != None:  # иначе ошибку выдает на strptime
                days = (datetime.strptime(str(df_doctors['nearestDate'][i])[:10], '%Y-%m-%d') - datetime.strptime((datetime.utcnow() + timedelta(hours=3)).strftime('%Y-%m-%d'), '%Y-%m-%d')).days
                if df_doctors['doctor_id'][i] == record['doctor_id'] and df_doctors['lpu_id'][i] == record['lpu_id'] \
                        and df_doctors['freeParticipantCount'][i] > 0 and days <= record['notification_days']:
                    record['available_tickets'] = df_doctors['freeParticipantCount'][i]
                    record['first_date'] = df_doctors['nearestDate'][i][:10]
                    record['last_date'] = df_doctors['lastDate'][i][:10]
                    record['doctor_name'] = df_doctors['name'][i]
                    record['lpu_name'] = df_doctors['lpu_name'][i]
                    # название специальности я хотел хранить полем в records и обновлять по триггеру - но не получилось (см. "запишем специальности в postgres")
                    record['speciality_name'] = df_specialities[df_specialities.speciality_id == record['speciality_id']]['name'].iloc[0]

# отсюда код пишу
# разошлем уведомления в телеграм
notifications = 0
notifications_success = 0
for record in records:
    if (record['available_tickets'] != None):
        message = record['speciality_name']
        url_gorzdrav_apply = 'https://gorzdrav.spb.ru/service-free-schedule#%5B%7B%22district%22:%2211%22%7D,%7B%22lpu%22:%22' + record['lpu_id'] + '%22%7D,%7B%22speciality%22:%22' + record['speciality_id'] + '%22%7D'
        if (record['doctor_name']) != None:  # если ищется доктор, а не специальность
            message += ' ' + record['doctor_name']
            url_gorzdrav_apply += ',%7B%22doctor%22:%22' + record['doctor_id'] + '%22%7D%5D'
        else:
            url_gorzdrav_apply += '%5D'
        url_gorzdrav_apply = urllib.parse.quote(url_gorzdrav_apply)
        message += '. Доступно талонов: ' + str(record['available_tickets'])
        message += ' с ' + record['first_date'] + ' по ' + record['last_date'] + '.'
        message += ' <a href="' + url_gorzdrav_apply + '">Записаться</a> '
        message += record['lpu_name']
        url_tg = 'https://api.telegram.org/bot' + tg_bot_token + '/sendMessage?chat_id=' + str(record['chat_id']) + '&text=' + message + '&parse_mode=HTML&disable_web_page_preview=True'
        try:
            notifications += 1
            response = requests.get(url_tg)
        except Exception as e:
            log(f'Script continues. Telegram notifications sending error: {e}', admin=True)
        else:
            response_ok = ''
            if response.status_code == 200:
                try    : response_ok = response.json()['ok']
                except : pass
                else   : pass
            if response_ok == True:
                notifications_success += 1
            else:
                response_description = response.json()['description']
                if response_description == 'Forbidden: bot was blocked by the user':
                    log(f'Script continues. Telegram notification not sent, response.status_code = {response.status_code}, response json description = {response_description}. record_id: {record["record_id"]}, username: {record["username"]}')
                else:
                    log(f'Script continues. Telegram notification not sent, response.status_code = {response.status_code}, response json description = {response_description}. record_id: {record["record_id"]}, username: {record["username"]}', admin=True)

log(f'{notifications} appointments are available. {notifications_success} success notifications have been sent')
myexit()
