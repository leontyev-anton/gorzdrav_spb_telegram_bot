# gorzdrav_spb
Скрипт мониторит свободную запись к врачу, и присылает уведомление на почту при ее появлении

Веб-адрес сервиса для записи к врачу - https://gorzdrav.spb.ru/service-free-schedule
Смотрим в историю запросов, и находим, что данные подгружаются из JSON, которые используется в текущем скрипте.

На сервере нужно настроить cron для регулярного запуска примерно такого shell скрипта:

sleep 7 #чтобы не было в одно время с другими возможными ботами
cd /home/Dropbox/PycharmProjects/gorzdrav/
current_date=$(date +"%Y-%m-%d")
filename='logs/'$current_date'.log'
python3 gorzdrav_email.py >> $filename
