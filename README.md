The script monitors the free doctor’s appointments and sends a notification to Telegram when they occur (@gorzdrav_spb_35_bot)

Web address of the service for making a doctor’s appointment - https://gorzdrav.spb.ru/service-free-schedule . Select district and medical facility, then look at the developer’s tools(Browser - Inspect) and find out, that the data is loaded from JSON. It will be exactly used in the current scripts. 

You need to set up cron on the server for a regularly run of shell scripts gorzdrav.sh and update_doctors_specialities.sh. 
bot.py must always be running on the server.

RUS: Скрипт мониторит свободную запись к врачу, и присылает уведомление в телеграм при ее появлении (@gorzdrav_spb_35_bot)

Веб-адрес сервиса для записи к врачу - https://gorzdrav.spb.ru/service-free-schedule
Выбираем район и медучреждение, потом смотрим в инструменты разработчика, и находим, что данные подгружаются из JSON. Его и будем использовать в текущих скриптах.

На сервере нужно настроить cron для регулярного запуска shell скриптов gorzdrav.sh и update_doctors_specialities.sh.
На сервере должен быть всегда запущен bot.py
