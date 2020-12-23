sleep 7 #чтобы не было в одно время с другими возможными ботами
cd /home/Dropbox/PycharmProjects/gorzdrav/
current_date=$(date +"%Y-%m-%d")
filename='logs/'$current_date'.log'
# echo $filename
python3 gorzdrav.py >> $filename
