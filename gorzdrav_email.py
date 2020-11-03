import requests
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

# пишет лог в stdout и добавляет содержание письма для последующей отправки (переменные email_subject и email_body)
def log(text, stdout=True, e_subject=False, e_body=False, end=''):
    if stdout: print(text, end=end)
    global email_subject
    global email_body
    if e_subject: email_subject = email_subject + text
    if e_body: email_body = email_body = email_body + text + end

# отправляет письмо с содержанием из глобальных переменных email_subject, email_body
def send_email(body_delete_first_line=False):
    global email_body
    if body_delete_first_line:
        email_body = email_body[email_body.find('\n')+1:]  # убираем первую строку
        email_body = email_body[email_body.find('\n')+1:]  # убираем первую строку еще раз
    try:
        server = smtplib.SMTP_SSL('smtp.mail.ru', 465)
        server.login('...', '...')
        msg = EmailMessage()  # дока https://docs.python.org/3/library/email.examples.html#email-examples
        msg['Subject'] = email_subject
        msg['From'] = 'Gorzdrav Spb Bot <...>'
        msg['To'] = '...'
        msg.set_content(email_body)
        server.send_message(msg)  # не комментируй эту строку! а то забудешь раскомментировать
        server.quit()
        log('    Email notification was sent successfully\r\n')
    except Exception as e:
        log('    Email notification was not sent - error with email sending: ' + str(e) + '\r\n')


email_subject = ''
email_body = ''
datetime_now = datetime.utcnow() + timedelta(hours=3)
log('Start:  ' + datetime_now.strftime('%Y-%m-%d %H:%M:%S'), e_body=True, end='\r\n')
# https://gorzdrav.spb.ru/service-free-schedule#%5B%7B%22district%22:%2211%22%7D,%7B%22lpu%22:%22147%22%7D%5D
gorzdrav_url = 'https://gorzdrav.spb.ru/_api/api/lpu/147/speciality'
#gorzdrav_url = 'http://metalcd-altnet.ru/'  # response.encoding = 'windows-1251'
#gorzdrav_url = 'http://metalcd-altnet.ru/speciality.json'
# специальности которые будем искать. при парсинге будем заполнять этот массив словарей, поэтому некоторые значения изначально None.
# notification_days - отправлять уведомления, только если талончики есть в эти ближайшие дни. -1 - без уведомлений. 0 - только на сегодня и т.д
specialities = [{'id': '81', 'notification_days': 10, 'tickets': None, 'name': None},  # Травматолог-ортопед
                {'id': '48', 'notification_days': 10, 'tickets': None, 'name': None},  # Отоларинголог
                {'id': '52', 'notification_days': -1, 'tickets': None, 'name': None}]  # Педиатр
                #{'id': '555','notification_days': 10, 'tickets': None, 'name': None}]  # Несуществующий

response = requests.get(gorzdrav_url)  # print(response.headers)
if response.status_code == 200:
    try:
        json = response.json()
        json = json['result']
    except Exception as e:
        log('Finish: ' + (datetime.utcnow() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S'), e_body=True, end='\r\n')
        log('    ')
        log(f'Error parsing gorzdrav page to JSON: {e}', e_subject=True, end='\r\n')
        log('\r\n' + gorzdrav_url + '\r\n\r\nResponse Text =' + response.text, stdout=False, e_body=True, end='\r\n')
        send_email()
    else:
        for j in json:  # разберем каждый элемент JSON
            for speciality in specialities:
                if speciality['id'] == j['id']:    # в искомый массив specialities пропишем данные из JSON
                    speciality['name'] = j['name']
                    speciality['tickets'] = j['countFreeParticipant']
                    if j['nearestDate'] is not None: speciality['first_date'] = str(j['nearestDate'])[:10]
                    if j['lastDate'] is not None: speciality['last_date'] = str(j['lastDate'])[:10]
        email_subject_flag_free_ticket = False  # признак что нашелся свободный талончик - нужно отправить email и указать это в Заголовке
        email_subject_flag_not_find = False     # признак что в JSON не нашлась какая-то специальность - то есть в исходных данных вероятно ошибка - нужно отправить email и указать это в Заголовке
        log('Finish: ' + (datetime.utcnow() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S'), e_body=True, end='\r\n')

        for speciality in specialities:  # разберем что мы там нашли
            log(f"    {speciality['name']} id={speciality['id']}")
            if speciality['tickets'] is not None:     # нашлась такая специальность в JSON
                log(f": {speciality['tickets']} tickets")
            else:                                     # такой специльности нет в JSON - ошибочные исходные данные
                email_subject_flag_not_find = True
                log(f"id={speciality['id']}: Not found at {gorzdrav_url}", stdout=False, e_body=True)
            if speciality['tickets'] is not None and speciality['tickets'] > 0:  # нашлась такая специальность и есть свободный талончик
                log(f". Dates: {speciality['first_date']} - {speciality['last_date']}")
                days = (datetime.strptime(speciality['first_date'], '%Y-%m-%d') - datetime.strptime(datetime_now.strftime('%Y-%m-%d'), '%Y-%m-%d')).days
                if days <= speciality['notification_days']:  # если первая доступная дата подходит для отправки уведомления
                     log('. Need notification')
                     email_subject_flag_free_ticket = True
                     log(f"id={speciality['id']} {speciality['name']}: {speciality['tickets']} tickets, "
                         f"Dates: {speciality['first_date']} - {speciality['last_date']}", stdout=False, e_body=True, end='\r\n')
                else:
                    log('. No Notification')
            log('\r\n')

        if email_subject_flag_free_ticket:
            log('Available free tickets ', stdout=False, e_subject=True)
            log('\r\n\r\nMake an appointment: https://gorzdrav.spb.ru/service-free-schedule#%5B%7B%22district%22:%2211%22%7D,%7B%22lpu%22:%22147%22%7D%5D', stdout=False, e_body=True, end='\r\n')
        if email_subject_flag_not_find:
            log('Warning: invalid speciality', stdout=False, e_subject=True)
        if email_subject_flag_free_ticket or email_subject_flag_not_find:
            send_email(body_delete_first_line=True)
else:
    log('Finish: ' + (datetime.utcnow() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S'), e_body=True, end='\r\n')
    log('    ')
    log(f'Error reguesting gorzdrav url. Response Status Code = {response.status_code}', e_subject=True, end='\r\n')
    log('\r\n' + gorzdrav_url + '\r\n\r\nResponse Text =' + response.text, stdout=False, e_body=True, end='\r\n')
    send_email()



