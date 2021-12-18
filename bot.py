# бот для общения с пользователем -> он должен быть всегда запущенным на сервере и запускаться при его перезагрузке

import logging
import pandas
import psycopg2
from sqlalchemy import create_engine
from config import tg_bot_token, tg_author_name, pg_host, pg_user, pg_pass, pg_db
from aiogram import Bot, Dispatcher, executor, types
from aiogram.utils.helper import Helper, HelperMode, ListItem
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, filename='bot.log', filemode='w', format='%(levelname)s: %(name)s:    %(message)s')

# Initialize bot and dispatcher   https://surik00.gitbooks.io/aiogram-lessons/content/  https://mastergroosha.github.io/telegram-tutorial/docs/lesson_14/
bot = Bot(token=tg_bot_token)
dp = Dispatcher(bot, storage=MemoryStorage())  # состояния будут храниться в памяти
pg = create_engine('postgresql://' + pg_user + ':' + pg_pass + '@' + pg_host + '/' + pg_db)

class States(StatesGroup):
    new_waiting_speciality = State()
    new_waiting_lpu = State()
    new_waiting_doctor = State()
    new_waiting_notification_days = State()
    new_waiting_confirmation = State()
    del_waiting_number = State()
    del_waiting_confirmation = State()

##################### мои функции

def log(text):
    datetime_now = datetime.utcnow() + timedelta(hours=3)
    datetime_now = datetime_now.strftime('%Y-%m-%d %H:%M:%S')
    logging.info(datetime_now + ': ' + text)

def read_records(chat_id, username):  # функция для чтения текущих записей человека (2 раза используется)
    global pg
    records = []
    try:
        df = pandas.read_sql(con=pg, sql=  # psycopg2 выдает результат без названий колонок, да и строк кода больше при запросе
            'SELECT '
                's.lpu_name AS lpu_name, '
                's.name AS speciality_name, '
                'd.name AS doctor_name, '
                'r.notification_days AS notification_days, '
                'r.record_id AS record_id '
            'FROM records AS r '
            'LEFT JOIN specialities AS s ON s.lpu_id=r.lpu_id AND s.speciality_id=r.speciality_id '
            'LEFT JOIN doctors AS d ON d.lpu_id=r.lpu_id AND d.speciality_id=r.speciality_id AND d.doctor_id=r.doctor_id '
            'WHERE r.date_deleting IS NULL AND chat_id=' + str(chat_id) +
            'ORDER BY r.record_id')  # сортировка нужна тк нумеруем записи для вывода пользователем и поиска record_id потом
    except Exception as e:
        log(f'Error requesting records from Postgres for user:{username}, chat_id:{chat_id} at chat /start or /del: {e}')  # переписать эти уведомления нормально
        return [{'num': '-1', 'id': -1, 'text':''}]
    else:
        for i in df.index:
            text = ''
            text += str(i+1) + ') ' + df['speciality_name'][i]
            if df['doctor_name'][i] == None:
                text += ' (Любой доктор), '
            else:
                text += ' (' + df['doctor_name'][i] + '), '
            text += df['lpu_name'][i] + '. Ближайшие ' + str(df['notification_days'][i]) + ' дн.'
            records.append({'num': i+1, 'id': df['record_id'][i], 'text':text})
        return records

####################### new

@dp.message_handler(commands=['new'], state="*")
async def new_step_1(message: types.Message, state: FSMContext):
    try:
        df_specialities = pandas.read_sql(con=pg, sql='SELECT speciality_id, name, lpu_id, lpu_name FROM specialities')
        df_doctors = pandas.read_sql(con=pg, sql='SELECT comment, doctor_id, name, speciality_id, speciality_name, lpu_id FROM doctors')
    except Exception as e:
        log(f'Error requesting from Postgres command /new for user:{message.from_user.username}, chat_id:{message.chat.id}: {e}')
        await message.answer('Произошла ошибка. Попробуйте заново, или напишите автору бота.')
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        specialities_array = df_specialities['name'].unique()
        for speciality in specialities_array:
            keyboard.add(speciality)
        await state.update_data(df_specialities=df_specialities, specialities_array=specialities_array, df_doctors=df_doctors)
        await message.answer('Доступные специальности:', reply_markup=keyboard)
        await States.new_waiting_speciality.set()
        # здесь еще дописать нормальный лог со временем


@dp.message_handler(state=States.new_waiting_speciality, content_types=types.ContentTypes.TEXT)
async def new_step_2(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.text not in user_data['specialities_array']:  # проверим правильность ввода
        await message.answer("Выберите специальность из списка:")
        return
    await state.update_data(selected_speciality_name=message.text)
    # теперь нужно выбрать lpu
    df_specialities = user_data['df_specialities']
    df_doctors = user_data['df_doctors']
    df_spec = df_specialities[df_specialities['name'] == message.text]
    if len(df_spec) == 1:  # если только 1 lpu, то даем выбрать доктора
        await state.update_data(selected_lpu_id=df_spec['lpu_id'].iloc[0])
        await state.update_data(selected_lpu_name=df_spec['lpu_name'].iloc[0])
        await message.answer(message.text + ' доступен только в одном отделении: ' + df_spec['lpu_name'].iloc[0])
        df_doct = df_doctors[(df_doctors['lpu_id'] == df_spec['lpu_id'].iloc[0]) & (df_doctors['speciality_name'] == message.text)]
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        doctors_array = []
        keyboard.add('Любой')
        doctors_array.append('Любой')
        for i in df_doct.index:
            keyboard.add(df_doct['name'][i])
            doctors_array.append(df_doct['name'][i])
        await state.update_data(doctors_array=doctors_array)
        await message.answer('Выберите доктора:', reply_markup=keyboard)
        await States.new_waiting_doctor.set()
    else:                       # если больше 1 lpu, то даем выбрать lpu
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        lpus_array = []
        for i in df_spec.index:
            keyboard.add(df_spec['lpu_name'][i])
            lpus_array.append(df_spec['lpu_name'][i])
        await state.update_data(lpus_array=lpus_array)
        await message.answer('Выберите отделение:', reply_markup=keyboard)
        await States.new_waiting_lpu.set()


@dp.message_handler(state=States.new_waiting_lpu, content_types=types.ContentTypes.TEXT)
async def new_step_3(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.text not in user_data['lpus_array']:  # проверим правильность ввода
        await message.answer("Выберите отделение из списка:")
        return
    #тут пишем
    df_specialities = user_data['df_specialities']
    df_lpu = df_specialities[df_specialities['lpu_name'] == message.text]
    lpu_id = df_lpu['lpu_id'].iloc[0]
    await state.update_data(selected_lpu_id=lpu_id)
    await state.update_data(selected_lpu_name=message.text)
    df_doctors = user_data['df_doctors']
    df_doct = df_doctors[(df_doctors['lpu_id'] == lpu_id) & (df_doctors['speciality_name'] == user_data['selected_speciality_name'])]
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    doctors_array = []
    keyboard.add('Любой')
    doctors_array.append('Любой')
    for i in df_doct.index:
        keyboard.add(df_doct['name'][i])
        doctors_array.append(df_doct['name'][i])
    await state.update_data(doctors_array=doctors_array)
    await message.answer('Выберите доктора:', reply_markup=keyboard)
    await States.new_waiting_doctor.set()


@dp.message_handler(state=States.new_waiting_doctor, content_types=types.ContentTypes.TEXT)
async def new_step_5(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.text not in user_data['doctors_array']:  # проверим правильность ввода
        await message.answer("Выберите доктора из списка:")
        return
    await state.update_data(selected_doctor_name=message.text)
    await message.answer('На сколько дней вперед интересуют талончики (0 - только на текущий, '
                         '1 - на текущий и следующий, и т.д. до 100)?', reply_markup=types.ReplyKeyboardRemove())
    await States.new_waiting_notification_days.set()


@dp.message_handler(state=States.new_waiting_notification_days, content_types=types.ContentTypes.TEXT)
async def new_step_6(message: types.Message, state: FSMContext):
    notification_days = int(message.text) if message.text.isdigit() else None  # проверим правильность ввода
    if notification_days == None or notification_days < 0 or notification_days > 100:  # проверим правильность ввода
        await message.answer("Введите число от 0 до 100:")
        return
    await state.update_data(selected_notification_days=notification_days)
    user_data = await state.get_data()
    await message.answer('Будем мониторить талончики: ' + user_data['selected_speciality_name'] + ', ' + \
                         user_data['selected_lpu_name'] + ', доктор: ' + user_data['selected_doctor_name'] + ' на ' + \
                         str(notification_days) + ' дня вперед. Если все верно, введите да/y/yes. Чтобы отменить - любое другое сообщение.')
    await States.new_waiting_confirmation.set()

@dp.message_handler(state=States.new_waiting_confirmation, content_types=types.ContentTypes.TEXT)
async def new_step_7(message: types.Message, state: FSMContext):
    if (message.text.lower() in ['да','y','yes']):
        user_data = await state.get_data()
        # найдем speciality_id здесь, тк ранее его нужно искать в двух местах
        df_specialities = user_data['df_specialities']
        df_spec = df_specialities[(df_specialities['lpu_id'] == user_data['selected_lpu_id']) & (df_specialities['name'] == user_data['selected_speciality_name'])]
        speciality_id = df_spec['speciality_id'].iloc[0]
        # найдем доктора
        if (user_data['selected_doctor_name']=='Любой'):
            doctor_id = None
        else:
            df_doctors = user_data['df_doctors']
            df_doct = df_doctors[(df_doctors['lpu_id'] == user_data['selected_lpu_id']) & (df_doctors['speciality_name']
                == user_data['selected_speciality_name']) & (df_doctors['name'] == user_data['selected_doctor_name'])]
            doctor_id = df_doct['doctor_id'].iloc[0]
        lpu_id = user_data['selected_lpu_id']
        notification_days = user_data['selected_notification_days']
        date_creating = datetime.utcnow() + timedelta(hours=3)
        try:
            conn = psycopg2.connect(database=pg_db, user=pg_user, password=pg_pass, host=pg_host)
            cursor = conn.cursor()
            query = 'INSERT INTO records (lpu_id, speciality_id, doctor_id, notification_days, chat_id, username, '\
                     'date_creating, date_deleting) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'
            data = (lpu_id, speciality_id, doctor_id, notification_days, str(message.chat.id), message.from_user.username, date_creating, None)
            cursor.execute(query, data)
            conn.commit()
            conn.close()
        except Exception as e:
            log(f'Error inserting new record in Postgres for user:{message.from_user.username}, chat_id:{message.chat.id}: {e}')
            await message.answer('Произошла ошибка. Попробуйте заново, или напишите автору бота.')
        else:
            await message.answer('Запись сохранена. При появлении свободных талончиков на gorzdrav.spb.ru вам придут уведомления в этот чат.')
    else:
        await message.answer('Сбросили введенные значения.')
    await state.finish()


################### del

@dp.message_handler(commands=['del'], state="*")
async def del_step_1(message: types.Message, state: FSMContext):
    records = read_records(message.chat.id, message.from_user.username)
    if len(records) == 0:
        await message.answer ('Сейчас у вас не настроен поиск талончиков, поэтому удалять нечего.')
        await state.finish()
    elif records[0]['id'] == '-1':
        await message.answer('Произошла ошибка при поиске текущих записей. Попробуйте заново, или напишите автору бота.')
        await state.finish()
    else:
        records_text = ''
        for record in records: records_text += record['text'] + '\n'
        await message.answer('Введите номер записи для удаления:\n' + records_text)
        await state.update_data(records=records)
        await States.del_waiting_number.set()


@dp.message_handler(state=States.del_waiting_number, content_types=types.ContentTypes.TEXT)
async def del_step_2(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    record_nums = []
    for record in user_data['records']: record_nums.append(str(record['num']))
    if message.text not in record_nums:  # проверим правильность ввода
        await message.answer("Введите номер из списка выше:")
        return
    await state.update_data(deleted_record_num=int(message.text))
    await message.answer('Для подтверждения удаления записи №' + message.text + ' введите да/y/yes. Чтобы отменить - любое другое сообщение.')
    await States.del_waiting_confirmation.set()


@dp.message_handler(state=States.del_waiting_confirmation, content_types=types.ContentTypes.TEXT)
async def del_step_3(message: types.Message, state: FSMContext):
    if (message.text.lower() in ['да','y','yes']):
        try:
            user_data = await state.get_data()
            record_id = user_data['records'][user_data['deleted_record_num'] - 1]['id']
            conn = psycopg2.connect(database=pg_db, user=pg_user, password=pg_pass, host=pg_host)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM records WHERE record_id=' + str(record_id))
            conn.commit()
            conn.close()
        except Exception as e:
            log(f'Error deleting record in Postgres for user:{message.from_user.username}, chat_id:{message.chat.id}: {e}')
            await message.answer('При попытке удаления произошла ошибка. Попробуйте заново, или напишите автору бота.')
        else:
            await message.answer('Запись успешно удалена')
    else:
        await message.answer('Сбросили введенные значения.')
    await state.finish()

################### любое сообщение

@dp.message_handler()  # любое другое сообщение или команда
async def echo(message: types.Message):
    records = read_records(message.chat.id, message.from_user.username)
    if len(records) == 0:
        records_text_print = 'Сейчас у вас не настроен поиск талончиков.\n'
    elif records[0]['id'] == -1:
        records_text_print = 'Произошла ошибка при поиске текущих записей. Попробуйте заново, или напишите автору бота.\n'
    else:
        records_text_print = 'У вас настроен поиск талончиков к:\n'
        for record in records: records_text_print += record['text'] + '\n'

    text = 'Привет! Этот бот позволяет мониторить появление свободных талончиков на сервисе gorzdrav.spb.ru ' \
           'в два отделения 35 детской поликлиники Московского района СПб. Бот опрашивает сервис каждые несколько минут, ' \
           'и, при появлении свободного талончика отправляет уведомление в этот чат.\n\n' + records_text_print + '\n' \
           'Для создания нового введите команду /new\n' \
           'Для удаления введите /del\n' \
           'Автор бота: ' + tg_author_name
    await message.answer(text)
    datetime_now = datetime.utcnow() + timedelta(hours=3)
    datetime_now = datetime_now.strftime('%Y-%m-%d %H:%M:%S')
    log(f'Hello message for user:{message.from_user.username}, chat_id: {message.chat.id} has been sent successfully')


if __name__ == '__main__':
    log('Start')
    executor.start_polling(dp, skip_updates=True)

    log('Finish')
