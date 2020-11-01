sleep 7 #чтобы не было в одно время с другими возможными ботами
cd /home/Dropbox/PycharmProjects/gorzdrav/ #папка куда положили скрипт
current_date=$(date +"%Y-%m-%d")
filename='logs/'$current_date'.log'
python3 gorzdrav_email.py >> $filename
