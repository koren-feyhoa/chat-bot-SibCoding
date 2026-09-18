import os
import datetime
import json
import logging
import pytz
from typing import Dict, Optional
from dotenv import load_dotenv
from maxbot.bot import Bot
from maxbot.dispatcher import Dispatcher
from maxbot.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

RUSSIAN_MONTHS = {
    1: 'Январь',
    2: 'Февраль',
    3: 'Март',
    4: 'Апрель',
    5: 'Май',
    6: 'Июнь',
    7: 'Июль',
    8: 'Август',
    9: 'Сентябрь',
    10: 'Октябрь',
    11: 'Ноябрь',
    12: 'Декабрь'
}

# Общие константы с Telegram ботом
BOOKING_FILE = os.path.join(os.path.dirname(__file__), 'pending_bookings.json')

# Кнопки
BTN_BOOK = '📅 Забронировать аудиторию'
BTN_BOOKED_TIMES = '📋 Посмотреть забронированное время'
BTN_MAIN_MENU = '🏠 Вернуться в главное меню'
BTN_CONTINUE = '▶️ Продолжить'

# Состояния FSM
STATE_WAITING_FULLNAME = 'waiting_fullname'
STATE_WAITING_DATE = 'waiting_date'
STATE_WAITING_TIME = 'waiting_time'
STATE_WAITING_DESCRIPTION = 'waiting_description'

def get_available_months():
    now = datetime.datetime.now(datetime.timezone.utc)
    current_month = now.month
    current_year = now.year
    current_day = now.day
    
    months = []
    months.append((current_year, current_month))
    
    next_month = current_month + 1
    next_year = current_year
    if next_month > 12:
        next_month = 1
        next_year += 1
    months.append((next_year, next_month))
    
    if current_day >= 20:
        next_next_month = next_month + 1
        next_next_year = next_year
        if next_next_month > 12:
            next_next_month = 1
            next_next_year += 1
        months.append((next_next_year, next_next_month))
    
    return months

def load_pending_bookings() -> Dict:
    try:
        if not os.path.exists(BOOKING_FILE):
            return {}
        
        with open(BOOKING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f'Error loading bookings: {str(e)}')
        return {}

def save_pending_bookings(bookings: Dict):
    try:
        with open(BOOKING_FILE, 'w', encoding='utf-8') as f:
            json.dump(bookings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f'Error saving bookings: {str(e)}')

def is_date_available(date_str: str) -> bool:
    try:
        try:
            date = datetime.datetime.strptime(date_str, '%d.%m.%Y').date()
        except ValueError:
            date = datetime.datetime.strptime(date_str, '%d.%m').date()
            date = date.replace(year=datetime.datetime.now(datetime.timezone.utc).year)

        available_months = get_available_months()
        date_key = (date.year, date.month)
        return date_key in available_months
    except Exception:
        return False

class MaxBookingBot:
    def __init__(self, token: str):
        self.token = token
        self.bot = Bot(token)
        self.dispatcher = Dispatcher(self.bot)
        self._register_handlers()
        logger.info('MAX Bot initialized')
    
    def _register_handlers(self):
        """Регистрация обработчиков сообщений"""
        
        @self.dispatcher.message()
        async def handle_start(message):
            """Обработка команды /start"""
            if message.text == '/start':
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=BTN_BOOK, callback_data='book')],
                    [InlineKeyboardButton(text=BTN_BOOKED_TIMES, callback_data='booked_times')]
                ])
                
                user_name = message.sender.name or 'Пользователь'
                text = (
                    f'👋 Привет, {user_name}!\n\n'
                    'Я помогу забронировать СибКодинг.\n\n'
                    'Чтобы начать, выберите одно из действий ниже:'
                )
                
                await self.bot.send_message(
                    user_id=message.sender.id,
                    text=text,
                    reply_markup=keyboard,
                    notify=True
                )
                logger.info(f'Start command processed for user {message.sender.id}')
        
        @self.dispatcher.callback()
        async def handle_book_callback(callback):
            """Обработка кнопки бронирования"""
            if callback.payload == 'book':
                months = get_available_months()
                months_str = [f'{RUSSIAN_MONTHS[month]} {year}' for year, month in months]
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=BTN_CONTINUE, callback_data='continue_booking')],
                    [InlineKeyboardButton(text=BTN_MAIN_MENU, callback_data='main_menu')]
                ])
                
                text = 'Доступные месяцы для бронирования:\n' + '\n'.join(f'- {m}' for m in months_str)
                
                await self.bot.send_message(
                    user_id=callback.user.id,
                    text=text,
                    reply_markup=keyboard,
                    notify=True
                )
                logger.info(f'Booking started for user {callback.user.id}')
        
        @self.dispatcher.callback()
        async def handle_booked_times_callback(callback):
            """Обработка кнопки просмотра забронированного времени"""
            if callback.payload == 'booked_times':
                # TODO: Интегрировать с bot_utils.is_time_available
                text = '📋 Функция просмотра забронированного времени в разработке'
                
                await self.bot.send_message(
                    user_id=callback.user.id,
                    text=text,
                    notify=True
                )
                logger.info(f'Booked times requested by user {callback.user.id}')
        
        @self.dispatcher.callback()
        async def handle_main_menu_callback(callback):
            """Обработка кнопки главного меню"""
            if callback.payload == 'main_menu':
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=BTN_BOOK, callback_data='book')],
                    [InlineKeyboardButton(text=BTN_BOOKED_TIMES, callback_data='booked_times')]
                ])
                
                text = '🏠 Главное меню'
                
                await self.bot.send_message(
                    user_id=callback.user.id,
                    text=text,
                    reply_markup=keyboard,
                    notify=True
                )
    
    async def create_booking(self, user_id: int, user_name: str, username: str, 
                           date: str, start_time: str, end_time: str, 
                           description: str) -> str:
        """Создание заявки на бронирование"""
        bookings = load_pending_bookings()
        
        booking_id = f'{user_id}_{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}'
        
        booking = {
            'id': booking_id,
            'user_id': user_id,
            'username': username,
            'fullname': user_name,
            'date': date,
            'start_time': start_time,
            'end_time': end_time,
            'description': description,
            'start_datetime': f'{date}T{start_time}:00+07:00',
            'end_datetime': f'{date}T{end_time}:00+07:00',
            'status': 'pending',
            'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'event_id': None,
            'source': 'max',
            'platform_user_id': user_id
        }
        
        bookings[booking_id] = booking
        save_pending_bookings(bookings)
        
        logger.info(f'Booking created: {booking_id} for user {user_id} via MAX')
        return booking_id
    
    async def run(self):
        """Запуск бота с Long Polling"""
        logger.info('Starting MAX bot with Long Polling...')
        await self.dispatcher.run_polling()

async def main():
    token = os.getenv('MAX_BOT_TOKEN')
    if not token:
        logger.error('MAX_BOT_TOKEN not found in environment variables')
        return
    
    bot = MaxBookingBot(token)
    
    # Проверяем подключение к MAX API
    try:
        me = await bot.bot.get_me()
        logger.info(f'Connected to MAX API as: {me}')
    except Exception as e:
        logger.error(f'Failed to connect to MAX API: {str(e)}')
        return
    
    # Запускаем бота с Long Polling
    await bot.run()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
