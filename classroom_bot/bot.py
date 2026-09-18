import os
import datetime

os.environ['TZ'] = 'Asia/Krasnoyarsk'
os.environ['PYTHONTZ'] = 'Asia/Krasnoyarsk'

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
import os
import time
import pickle
import logging
logger = logging.getLogger(__name__)
import functools
import json
import pytz
from typing import Dict, List
from dotenv import load_dotenv
from telegram import (
    Update, 
    ReplyKeyboardMarkup, 
    ReplyKeyboardRemove, 
    KeyboardButton,
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    User
)
from telegram.ext import Application, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, JobQueue
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


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
import pickle
import bot_utils

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

ENTER_DATE = 0
ENTER_TIME = 1
ENTER_DESCRIPTION = 2
CONFIRM_BOOKING = 3
VIEWING_BOOKINGS = 4

BTN_BOOK = '📅 Забронировать аудиторию'
BTN_BOOKED_TIMES = '📋 Посмотреть забронированное время'
BTN_CONTINUE = '▶️ Продолжить'
BTN_MAIN_MENU = '🏠 Вернуться в главное меню'

BTN_VIEW_BOOKINGS = '📃 Просмотр заявок'
BTN_CANCEL_BOOKING = '❌ Отменить бронь'
BTN_SETTINGS = '⚙️ Настройки'

BTN_NEXT = '➡️ Следующая'
BTN_PREV = '⬅️ Предыдущая'
BTN_APPROVE = '✅ Одобрить'
BTN_REJECT = '❌ Отклонить'
BTN_BACK = '⬅️ Назад'


pending_bookings: Dict[str, dict] = None

def format_datetime_iso8601(dt):
    utc_dt = dt.astimezone(pytz.UTC)
    return utc_dt.isoformat().replace('+00:00', 'Z')

def parse_datetime(date_str, time_str, format='%d.%m.%Y'):
    tz = pytz.timezone('Asia/Krasnoyarsk')
    naive_dt = datetime.datetime.strptime(f'{date_str} {time_str.strip()}', f'{format} %H:%M')
    return tz.localize(naive_dt)

def check_calendar_events_in_range(service, start_dt, end_dt):
    try:
        start_iso = format_datetime_iso8601(start_dt)
        end_iso = format_datetime_iso8601(end_dt)

        calendar_id = os.getenv('GOOGLE_CALENDAR_ID')
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_iso,
            timeMax=end_iso,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])
    except Exception as e:
        logger.error(f'Error checking calendar events: {str(e)}')
        return None

def load_pending_bookings():
    global pending_bookings
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'pending_bookings.json')
        logger.info(f'Loading bookings from {file_path}')
        logger.info(f'File exists: {os.path.exists(file_path)}')
        
        if not os.path.exists(file_path):
            logger.warning('No pending bookings file found, creating empty file')
            pending_bookings = {}
            save_pending_bookings()
            return pending_bookings
        
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
            logger.info(f'File content length: {len(file_content)}')
            if not file_content.strip():
                logger.warning('Empty bookings file')
                pending_bookings = {}
                return pending_bookings
            
            try:
                pending_bookings = json.loads(file_content)
                logger.info(f'Loaded {len(pending_bookings)} pending bookings')
                logger.info(f'Current bookings: {json.dumps(pending_bookings, ensure_ascii=False, indent=2)}')
                return pending_bookings
            except json.JSONDecodeError as e:
                logger.error(f'Error decoding JSON: {str(e)}')
                logger.error(f'Content that failed to decode: {file_content}')
                pending_bookings = {}
                return pending_bookings
    except Exception as e:
        logger.error(f'Unexpected error loading bookings: {str(e)}')
        pending_bookings = {}
        return pending_bookings

def save_pending_bookings():
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'pending_bookings.json')
        logger.info(f'Saving bookings to {file_path}')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(pending_bookings, f, ensure_ascii=False, indent=2)
        logger.info(f'Saved {len(pending_bookings)} pending bookings')
        logger.info(f'Current bookings after save: {json.dumps(pending_bookings, ensure_ascii=False, indent=2)}')
    except Exception as e:
        logger.error(f'Error saving pending bookings: {str(e)}')

def get_admin_group_id() -> int:
    group_id = os.getenv('ADMIN_GROUP_ID')
    return int(group_id) if group_id else None

async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, message: str, reply_markup=None):
    # Отправляем в группу администраторов
    group_id = get_admin_group_id()
    if group_id:
        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f'Error sending message to admin group: {str(e)}')
    
    # Отправляем личные сообщения администраторам
    try:
        with open('admin_users.csv', 'r') as f:
            admin_ids = [int(line.strip()) for line in f.readlines() if line.strip()]
            
        for admin_id in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f'Error sending message to admin {admin_id}: {str(e)}')
    except Exception as e:
        logger.error(f'Error reading admin IDs: {str(e)}')

async def send_user_notification(context: ContextTypes.DEFAULT_TYPE, booking: dict, message: str):
    """Отправляет уведомление пользователю в зависимости от источника заявки"""
    source = booking.get('source', 'telegram')
    platform_user_id = booking.get('platform_user_id')
    
    if source == 'telegram' and platform_user_id:
        try:
            await context.bot.send_message(
                chat_id=platform_user_id,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f'Error sending Telegram notification to user {platform_user_id}: {str(e)}')
    elif source == 'max' and platform_user_id:
        try:
            from max_notifier import max_notifier
            await max_notifier.send_message(platform_user_id, message)
        except Exception as e:
            logger.error(f'Error sending MAX notification to user {platform_user_id}: {str(e)}')
    else:
        logger.warning(f'Unknown source {source} for booking {booking.get("id")}')

def get_user_info(user: User) -> dict:
    """Получает информацию о пользователе для отображения в сообщениях"""
    return {
        'id': user.id,
        'name': f'{user.first_name} {user.last_name if user.last_name else ""}',
        'username': user.username
    }

def is_admin_chat(chat_id: int) -> bool:
    """Проверяет, является ли чат админ-чатом"""
    try:
        admin_group_id = int(os.getenv('ADMIN_GROUP_ID', '0'))
        return chat_id == admin_group_id
    except Exception as e:
        logger.error(f'Error checking admin chat status: {e}')
        return False

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    import csv
    csv_path = os.path.join(os.path.dirname(__file__), 'admin_users.csv')
    logger.info(f'Checking admin status for user_id: {user_id}')
    logger.info(f'Admin CSV path: {csv_path}')
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            admin_ids = {row[0] for row in reader if row and not row[0].startswith('#')}
            logger.info(f'Found admin IDs in CSV: {admin_ids}')
            result = str(user_id) in admin_ids
            logger.info(f'Is user {user_id} admin? {result}')
            return result
    except FileNotFoundError:
        logger.error(f'Admin users file not found: {csv_path}')
        return False
    except Exception as e:
        logger.error(f'Error checking admin status: {str(e)}')
        return False

async def send_to_admin_group(context: ContextTypes.DEFAULT_TYPE, message: str, reply_markup=None, user_info: dict = None):
    """Отправляет сообщение в группу администраторов

    Args:
        context: Контекст бота
        message: Сообщение для отправки
        reply_markup: Кнопки для сообщения (опционально)
        user_info: Информация о пользователе, выполнившем действие (опционально)
    """
    group_id = get_admin_group_id()
    if group_id:
        try:
            # Добавляем информацию о пользователе в конец сообщения
            if user_info:
                user_name = user_info.get('name', 'неизвестный пользователь')
                user_id = user_info.get('id', 'неизвестен')
                user_username = user_info.get('username', '')
                
                user_text = f"\n\nДействие выполнено: {user_name}"
                if user_username:
                    user_text += f" (@{user_username})"
                user_text += f" (ID: {user_id})"
                message += user_text
            
            await context.bot.send_message(
                chat_id=group_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f'Error sending message to admin group: {str(e)}')

def admin_required(func):
    @functools.wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Разрешаем доступ если:
        # 1. Пользователь является администратором
        # 2. Сообщение пришло из группы администраторов
        is_from_admin_chat = is_admin_chat(chat_id)
        
        if not (is_admin(user_id) or is_from_admin_chat):
            logger.warning(f'Unauthorized access attempt to {func.__name__} by user {user_id} in chat {chat_id}')
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text('❔ Эта команда доступна только администратору или в админ-чате.')
            return
        
        # Добавляем информацию о контексте выполнения
        context.user_data['is_from_admin_chat'] = is_from_admin_chat
        context.user_data['is_admin_user'] = is_admin(user_id)
        
        logger.info(f'Admin access granted for {func.__name__} to user {user_id} in chat {chat_id} (admin_chat: {is_from_admin_chat}, admin_user: {context.user_data["is_admin_user"]})')
        return await func(update, context, *args, **kwargs)
    return wrapped


    if user_id not in usage_stats['users']:
        usage_stats['users'][user_id] = {
            'username': username,
            'bookings': 0,
            'checks': 0,
            'last_action': None
        }
    
    if action == 'booking':
        usage_stats['total_bookings'] += 1
        usage_stats['users'][user_id]['bookings'] += 1
    elif action == 'check':
        usage_stats['total_checks'] += 1
        usage_stats['users'][user_id]['checks'] += 1
    
    usage_stats['users'][user_id]['last_action'] = datetime.datetime.now(datetime.timezone.utc).isoformat()

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.events.readonly',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def get_calendar_service():
    logger.info('Starting Google Calendar authentication')
    logger.info(f'Current working directory: {os.getcwd()}')
    creds = None
    
    try:
        if not os.path.exists('credentials.json'):
            logger.error('credentials.json not found')
            raise FileNotFoundError('credentials.json not found')

        if os.path.exists('token.pickle'):
            logger.info('Found existing token.pickle')
            try:
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
                logger.info('Successfully loaded credentials from token.pickle')
            except Exception as e:
                logger.error(f'Error loading token.pickle: {str(e)}')
                creds = None
                if os.path.exists('token.pickle'):
                    os.remove('token.pickle')
                    logger.info('Removed invalid token.pickle')
        else:
            logger.info('No token.pickle found')

        if not creds or not creds.valid:
            logger.info('Need to get new credentials')
            if creds and creds.expired and creds.refresh_token:
                logger.info('Refreshing expired credentials')
                creds.refresh(Request())
            else:
                logger.info('Starting new authentication flow')
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
                logger.info('Successfully completed authentication flow')

            try:
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
                logger.info('Successfully saved new credentials to token.pickle')
            except Exception as e:
                logger.error(f'Error saving token.pickle: {str(e)}')

        logger.info('Building Google Calendar service')
        service = build('calendar', 'v3', credentials=creds)

        calendar_id = os.getenv('GOOGLE_CALENDAR_ID')
        service.calendars().get(calendarId=calendar_id).execute()
        logger.info('Successfully tested Google Calendar service')
        
        return service
        
    except Exception as e:
        logger.error(f'Error in Google Calendar setup: {str(e)}')
        if os.path.exists('token.pickle'):
            os.remove('token.pickle')
            logger.info('Removed token.pickle due to error')
        raise



def get_user_keyboard():
    keyboard = [
        [KeyboardButton(BTN_BOOK)],
        [KeyboardButton(BTN_BOOKED_TIMES)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    keyboard = [
        [KeyboardButton(BTN_VIEW_BOOKINGS)],
        [KeyboardButton(BTN_CANCEL_BOOKING)],
        [KeyboardButton(BTN_SETTINGS)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)




async def booked_times_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        service = get_calendar_service()
        now = datetime.datetime.now(datetime.timezone.utc)
        time_min = now.isoformat()
        time_max = (now + datetime.timedelta(days=30)).isoformat()
        events_result = service.events().list(
            calendarId=os.getenv('GOOGLE_CALENDAR_ID'),
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        if not events:
            await update.message.reply_text('🟢 В ближайший месяц всё свободно!')
            return
        text = bot_utils.format_booked_times(events)
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text('❌ Ошибка при получении расписания.')
        logging.exception(e)

async def check_free_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f'User {update.effective_user.id} requested free time check')
    logger.info(f'Current working directory: {os.getcwd()}')
    logger.info(f'Checking credentials.json exists: {os.path.exists("credentials.json")}')
    logger.info(f'Checking token.pickle exists: {os.path.exists("token.pickle")}')
    
    try:
        # Проверяем наличие ID календаря
        calendar_id = os.getenv('GOOGLE_CALENDAR_ID')
        if not calendar_id:
            logger.error('GOOGLE_CALENDAR_ID not found in environment variables')
            await update.message.reply_text('❌ Ошибка конфигурации: не найден ID календаря')
            return

        # Получаем сервис календаря
        try:
            service = get_calendar_service()
            logger.info('Successfully got calendar service')

            # Проверяем доступ к календарю
            try:
                calendar = service.calendars().get(calendarId=calendar_id).execute()
                logger.info(f'Successfully accessed calendar: {calendar.get("summary", "Unknown")}')
            except Exception as e:
                logger.error(f'Failed to access calendar: {str(e)}')
                logger.error(f'Calendar ID: {calendar_id}')
                await update.message.reply_text('❌ Ошибка доступа к календарю. Проверьте настройки доступа.')
                return

            # Устанавливаем временной диапазон
            now = datetime.datetime.now(datetime.timezone.utc)
            time_min = now.isoformat()
            time_max = (now + datetime.timedelta(days=30)).isoformat()
            logger.info(f'Checking calendar from {time_min} to {time_max}')

        except Exception as e:
            logger.error(f'Failed to get calendar service: {str(e)}')
            if 'invalid_grant' in str(e).lower():
                if os.path.exists('token.pickle'):
                    os.remove('token.pickle')
                    logger.info('Removed invalid token.pickle')
                await update.message.reply_text('❌ Требуется повторная авторизация. Пожалуйста, попробуйте снова.')
            else:
                await update.message.reply_text('❌ Ошибка авторизации Google Calendar. Пожалуйста, перейдите по ссылке и авторизуйтесь.')
            return

            # Получаем список событий
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                await update.message.reply_text('🟢 Аудитория свободна на все время в ближайший месяц!')
                return

            # Группируем события по дням
            events_by_day = {}
            for event in events:
                try:
                    start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    end = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    start = start.astimezone(datetime.timezone(datetime.timedelta(hours=7)))
                    end = end.astimezone(datetime.timezone(datetime.timedelta(hours=7)))
                    day_str = start.strftime('%d.%m.%Y')
                    
                    if day_str not in events_by_day:
                        events_by_day[day_str] = []
                        
                    event_summary = event.get('summary', '').split(' - ')[0]  # Берем только описание, без ФИО
                    events_by_day[day_str].append(f"❌ {start.strftime('%H:%M')} - {end.strftime('%H:%M')} | {event_summary}")
                except Exception as e:
                    logger.error(f'Error processing event: {str(e)}')
                    continue

            # Формируем и отправляем сообщение
            try:
                message_parts = ['📅 Расписание на ближайшие 7 дней:']
                current_date = datetime.datetime.now().date()
                week_later = current_date + datetime.timedelta(days=7)
                
                for day, times in sorted(events_by_day.items()):
                    try:
                        event_date = datetime.datetime.strptime(day, '%d.%m.%Y').date()
                        if current_date <= event_date <= week_later:
                            message_parts.append(f'\n📆 {day}:')
                            message_parts.extend(times)
                    except ValueError as e:
                        logger.error(f'Error parsing date {day}: {str(e)}')
                        continue

                if len(message_parts) > 1:  # Если есть события на ближайшие 7 дней
                    await update.message.reply_text('\n'.join(message_parts))
                else:
                    await update.message.reply_text('🟢 Аудитория свободна на ближайшие 7 дней!')
                    
            except Exception as e:
                logger.error(f'Error formatting message: {str(e)}')
                await update.message.reply_text('❌ Ошибка при формировании расписания.')
                
    except Exception as e:
        logger.error(f'Error in check_free_time: {str(e)}')
        await update.message.reply_text('❌ Ошибка при проверке расписания.')

async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.user_data.get('booking_step') and not context.user_data.get('step'):
        months = get_available_months()
        months_str = [f'{RUSSIAN_MONTHS[month]} {year}' for year, month in months]

        keyboard = [
            [BTN_CONTINUE],
            [BTN_MAIN_MENU]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        message = ('Доступные месяцы для бронирования:\n' + '\n'.join(f'- {m}' for m in months_str))
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        return

    if context.user_data.get('awaiting_cancel_reason'):
        try:
            event_id = context.user_data.get('cancel_event_id')
            reason = text
            from bot import get_calendar_service, pending_bookings, save_pending_bookings, get_admin_keyboard
            import logging, os
            logger = logging.getLogger(__name__)
            service = get_calendar_service()
            user_info = {'user_id': None, 'date': '—', 'time_range': '—', 'description': '—', 'summary': '—'}

            # Находим бронирование для удаления
            booking_to_delete = None
            for booking_id, booking in pending_bookings.items():
                if booking.get('event_id') == event_id:
                    user_info.update({
                        'user_id': booking.get('user_id'),
                        'date': booking.get('date', '—'),
                        'time_range': f"{booking.get('start_time', '—')}-{booking.get('end_time', '—')}",
                        'description': booking.get('description', '—'),
                        'summary': booking.get('summary', '—')
                    })
                    booking_to_delete = booking_id
                    break

            # Удаляем событие из календаря
            calendar_id = os.getenv('GOOGLE_CALENDAR_ID')
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

            # Проверяем, что событие действительно удалено
            try:
                service.events().get(calendarId=calendar_id, eventId=event_id).execute()
                raise Exception('Событие не было удалено')
            except Exception as e:
                if 'not found' not in str(e).lower():
                    raise

            # Удаляем бронирование из списка ожидающих
            if booking_to_delete:
                del pending_bookings[booking_to_delete]
                save_pending_bookings()

            # Отправляем уведомление пользователю
            if user_info['user_id']:
                try:
                    await context.bot.send_message(
                        chat_id=user_info['user_id'],
                        text=(
                            f'❌ Ваша бронь отменена администратором!\n'
                            f'Дата: {user_info["date"]}\n'
                            f'Время: {user_info["time_range"]}\n'
                            f'Описание: {user_info["description"]}\n'
                            f'Причина отмены: {reason}'
                        )
                    )
                except Exception as e:
                    logger.warning(f'Не удалось уведомить пользователя: {e}')

            await update.message.reply_text('✅ Бронь успешно удалена!', reply_markup=get_admin_keyboard())

        except Exception as e:
            logger.error(f'Ошибка удаления бронирования: {e}')
            await update.message.reply_text('❌ Ошибка при удалении бронирования.', reply_markup=get_admin_keyboard())

        finally:
            # Очищаем данные пользователя в любом случае
            context.user_data.pop('awaiting_cancel_reason', None)
            context.user_data.pop('cancel_event_id', None)
            for k in ['booking_step', 'step', 'fullname', 'date', 'start_time', 'end_time', 'description']:
                context.user_data.pop(k, None)
            return



    if context.user_data.get('awaiting_reject_reason'):
        await handle_reject_reason(update, context, text)
        return

@admin_required
async def handle_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str):
    try:
        global pending_bookings
        pending_bookings = load_pending_bookings()
        logger.info(f'Handling reject reason. Reason: {reason}')
        logger.info(f'Context data: {context.user_data}')
        
        admin_user = update.effective_user
        booking_id = context.user_data.get('reject_booking_id')
        
        if not booking_id:
            logger.error('No reject_booking_id in context')
            await update.message.reply_text('❌ Ошибка: не найден ID заявки.', reply_markup=get_admin_keyboard())
            return
        
        import datetime
        
        booking = pending_bookings.get(booking_id)
        if not booking or booking['status'] != 'pending':
            await update.message.reply_text('❌ Заявка не найдена или уже обработана.', reply_markup=get_admin_keyboard())
            return

        if booking.get('event_id'):
            try:
                service = get_calendar_service()
                calendar_id = os.getenv('GOOGLE_CALENDAR_ID')
                service.events().delete(calendarId=calendar_id, eventId=booking['event_id']).execute()
                del booking['event_id']
            except Exception as e:
                logger.error(f'Error deleting calendar event: {str(e)}')

        booking['status'] = 'rejected'
        booking['rejected_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        booking['reject_reason'] = reason
        booking['rejected_by'] = admin_user.username or str(admin_user.id)
        save_pending_bookings()

        # Отправляем уведомление пользователю
        user_message = (
            f'❌ Ваша заявка на бронирование отклонена.\n\n'
            f'📅 Дата: {booking.get("date", "—")}\n'
            f'⏰ Время: {booking.get("start_time", "")} - {booking.get("end_time", "—")}\n'
            f'📝 Описание: {booking.get("description", "—")}\n'
            f'❗️ Причина отказа: {reason}'
        )

        await send_user_notification(context, booking, user_message)

        # Логируем успешное отклонение
        log_admin_action(
            admin_user,
            update.effective_chat.id,
            'REJECT_BOOKING_SUCCESS',
            f'Заявка {booking_id} отклонена. Причина: {reason}'
        )
        
        # Формируем сообщение с полной информацией
        admin_info = format_admin_name(admin_user)
        
        admin_message = (
            f'❌ Заявка отклонена\n\n'
            f'📝 Описание: {booking["description"]}\n'
            f'👤 Пользователь: {booking["fullname"]} (@{booking["username"]})\n'
            f'📅 Дата: {booking["date"]}\n'
            f'⏰ Время: {booking["time_range"]}\n'
            f'❗️ Причина: {reason}\n'
            f'👤 Администратор: {admin_info}'
        )

        # Отправляем уведомление в админ-чат
        await send_to_admin_group(
            context,
            admin_message
        )

        await update.message.reply_text(
            admin_message,
            reply_markup=get_admin_keyboard()
        )

        # Очищаем данные контекста
        context.user_data.pop('awaiting_reject_reason', None)
        context.user_data.pop('reject_booking_id', None)
        for k in ['booking_step', 'step', 'fullname', 'date', 'start_time', 'end_time', 'description']:
            context.user_data.pop(k, None)
            
    except Exception as e:
        logger.error(f'Error handling reject reason: {str(e)}')
        await update.message.reply_text('❌ Ошибка при обработке причины отклонения.', reply_markup=get_admin_keyboard())



async def process_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = update.message.text
    
    try:
        date_obj = datetime.datetime.strptime(date, '%d.%m')
        date_obj = date_obj.replace(year=datetime.datetime.now(datetime.timezone.utc).year)

        if date_obj.date() < datetime.datetime.now(datetime.timezone.utc).date():
            await update.message.reply_text('❌ Дата не может быть в прошлом.')
            return

        context.user_data['booking_date'] = date_obj
        context.user_data['date_str'] = date

        await update.message.reply_text('Введите время в формате ЧЧ:ММ-ЧЧ:ММ (например, 14:00-15:30):')

        context.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_time
            ),
            group=1
        )
        
    except ValueError:
        await update.message.reply_text('❌ Неверный формат даты. Введите дату в формате ДД.ММ (например, 25.04).')

async def process_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_range = update.message.text
    
    try:
        start_time, end_time = time_range.split('-')
        start_dt = datetime.datetime.strptime(start_time.strip(), '%H:%M')
        end_dt = datetime.datetime.strptime(end_time.strip(), '%H:%M')

        if start_dt >= end_dt:
            await update.message.reply_text('❌ Время начала должно быть раньше времени окончания.')
            return

        date = context.user_data['booking_date']
        context.user_data['start_time'] = start_dt.strftime('%H:%M')
        context.user_data['end_time'] = end_dt.strftime('%H:%M')
        context.user_data['time_range'] = time_range

        tz = pytz.timezone('Asia/Krasnoyarsk')
        start_datetime = date.replace(hour=start_dt.hour, minute=start_dt.minute).replace(tzinfo=tz)
        end_datetime = date.replace(hour=end_dt.hour, minute=end_dt.minute).replace(tzinfo=tz)
        
        if not bot_utils.is_time_available(start_datetime, end_datetime):
            from telegram import ReplyKeyboardRemove
            await update.message.reply_text('❌ Это время уже занято. Попробуйте другое.', reply_markup=ReplyKeyboardRemove())
            await update.message.reply_text('Выберите действие:', reply_markup=get_user_keyboard())
            return
        
        context.user_data['start_datetime'] = start_datetime.isoformat()
        context.user_data['end_datetime'] = end_datetime.isoformat()

        await update.message.reply_text('Введите описание бронирования:', reply_markup=get_user_keyboard())

        context.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_description
            ),
            group=1
        )
        
    except (ValueError, IndexError):
        await update.message.reply_text('❌ Неверный формат времени. Введите время в формате ЧЧ:ММ-ЧЧ:ММ (например, 14:00-15:30).')

async def process_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text

    user = update.effective_user
    booking_id = f'{user.id}_{int(time.time())}'[-20:]
    
    booking = {
        'id': booking_id,
        'user_id': user.id,
        'username': user.username,
        'fullname': f'{user.first_name} {user.last_name if user.last_name else ""}',
        'date': context.user_data['date_str'],
        'time_range': context.user_data['time_range'],
        'description': description,
        'start_datetime': context.user_data['start_datetime'],  # ISO 8601 with timezone
        'end_datetime': context.user_data['end_datetime'],      # ISO 8601 with timezone
        'status': 'pending',
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source': 'telegram',
        'platform_user_id': user.id
    }
    
    pending_bookings[booking_id] = booking
    save_pending_bookings()

    await update.message.reply_text(
        'Ваша заявка принята и отправлена на рассмотрение администратору. '
        'Вы получите уведомление, когда она будет рассмотрена.',
        reply_markup=ReplyKeyboardMarkup([[BTN_MAIN_MENU]], resize_keyboard=True)
    )
    
    # Создаем клавиатуру для одобрения/отклонения
    keyboard = [
        [InlineKeyboardButton(BTN_APPROVE, callback_data=f'approve_{booking_id}'),
         InlineKeyboardButton(BTN_REJECT, callback_data=f'reject_{booking_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Формируем и отправляем уведомление администраторам
    source = booking.get('source', 'telegram')
    source_emoji = '📱' if source == 'telegram' else '💬'
    source_name = 'Telegram' if source == 'telegram' else 'MAX'
    
    admin_message = (
        f'ℹ️ <b>Новая заявка на бронирование</b>\n\n'
        f'👤 Пользователь: {booking["fullname"]} (@{booking["username"]})\n'
        f'{source_emoji} Источник: {source_name}\n'
        f'📅 Дата: {booking["date"]}\n'
        f'⏰ Время: {booking["time_range"]}\n'
        f'📝 Описание: {booking["description"]}'
    )
    
    await send_admin_notification(context, admin_message, reply_markup)  
    # Отправляем сообщение в группу администраторов
    await send_to_admin_group(context, admin_message, reply_markup)
    
    # Также отправляем личные сообщения администраторам
    def is_admin_chat(chat_id: int) -> bool:
        """Проверяет, является ли чат админ-чатом"""
        try:
            admin_group_id = int(os.getenv('ADMIN_GROUP_ID', '0'))
            return chat_id == admin_group_id
        except Exception as e:
            logger.error(f'Error checking admin chat status: {e}')
            return False

    def is_admin(user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором"""
        try:
            with open('admin_users.csv', 'r') as f:
                admin_ids = [int(line.strip()) for line in f.readlines() if line.strip()]
                return user_id in admin_ids
        except Exception as e:
            logger.error(f'Error checking admin status: {e}')
            return False

    admin_ids = []
    try:
        with open('admin_users.csv', 'r') as f:
            admin_ids = [int(line.strip()) for line in f.readlines() if line.strip()]
    except Exception as e:
        logger.error(f'Error reading admin IDs: {str(e)}')
    
    for admin_id in admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f'Error sending message to admin {admin_id}: {str(e)}')
    

async def cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '❌ Бронирование отменено.',
        reply_markup=get_user_keyboard()
    )
    return ConversationHandler.END

@admin_required
async def handle_cancel_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('awaiting_cancel_reason'):
            return
        
        event_id = context.user_data.get('cancel_event_id')
        user_id = context.user_data.get('cancel_user_id')
        admin_user = update.effective_user
        
        if not event_id:
            await update.message.reply_text('❌ Ошибка: не найден ID бронирования.')
            return
        
        reason = update.message.text
        if not reason:
            await update.message.reply_text('❌ Пожалуйста, укажите причину отмены.')
            return

        service = get_calendar_service()
        try:
            event = service.events().get(
                calendarId=os.getenv('GOOGLE_CALENDAR_ID'),
                eventId=event_id
            ).execute()

            tz = pytz.timezone('Asia/Krasnoyarsk')
            start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')).astimezone(tz)
            end = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00')).astimezone(tz)

            # Удаляем событие из календаря
            service.events().delete(
                calendarId=os.getenv('GOOGLE_CALENDAR_ID'),
                eventId=event_id
            ).execute()

            # Отправляем уведомление пользователю
            user_message = (
                f'❌ Ваша бронь была отменена\n\n'
                f'📅 Дата: {start.strftime("%d.%m.%Y")}\n'
                f'⏰ Время: {start.strftime("%H:%M")} - {end.strftime("%H:%M")}\n'
                f'📝 Описание: {event.get("description", "—")}\n'
                f'❗️ Причина отмены: {reason}'
            )

            # Находим booking для получения информации о source
            booking_for_notification = None
            for bid, b in pending_bookings.items():
                if b.get('event_id') == event_id:
                    booking_for_notification = b
                    break
            
            if booking_for_notification:
                await send_user_notification(context, booking_for_notification, user_message)
            elif user_id:
                # Fallback для старых заявок без поля source
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=user_message,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f'Error sending cancellation notification to user {user_id}: {str(e)}')
            
            # Очищаем данные контекста
            context.user_data.pop('awaiting_cancel_reason', None)
            context.user_data.pop('cancel_event_id', None)
            context.user_data.pop('cancel_user_id', None)
            
            # Формируем сообщение с полной информацией
            admin_info = context.user_data.get('admin_user', {}).get('name') or format_admin_name(admin_user)
            
            # Получаем информацию о событии
            start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')).astimezone(pytz.timezone('Asia/Krasnoyarsk'))
            end = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00')).astimezone(pytz.timezone('Asia/Krasnoyarsk'))
            
            success_message = (
                '✅ Бронирование успешно отменено.\n\n'
                f'📝 Описание: {event.get("description", "—")}\n'
                f'📅 Дата: {start.strftime("%d.%m.%Y")}\n'
                f'⏰ Время: {start.strftime("%H:%M")} - {end.strftime("%H:%M")}\n'
                f'❗️ Причина: {reason}\n'
                f'👤 Администратор: {admin_info}'
            )
            
            await update.message.reply_text(
                success_message,
                reply_markup=get_admin_keyboard()
            )
            
        except Exception as e:
            logger.error(f'Error deleting event from calendar: {str(e)}')
            log_admin_action(
                admin_user,
                chat_id,
                'CANCEL_BOOKING_ERROR',
                f'Ошибка удаления события {event_id} из календаря: {str(e)}'
            )
            await update.message.reply_text('❌ Ошибка при отмене бронирования в календаре.')
            return
        
    except Exception as e:
        logger.error(f'Error in handle_cancel_reason: {str(e)}')
        log_admin_action(
            admin_user,
            chat_id,
            'CANCEL_BOOKING_ERROR',
            f'Общая ошибка при отмене брони: {str(e)}'
        )
        await update.message.reply_text('❌ Произошла ошибка при отмене бронирования.')

@admin_required
async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings_message = [
        '⚙️ Настройки:',
        f'\n📅 ID календаря: {os.getenv("GOOGLE_CALENDAR_ID")}',
        f'👤 ID администратора: {os.getenv("ADMIN_USER_ID")}',
    ]
    
    await update.message.reply_text('\n'.join(settings_message))

@admin_required
async def view_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bookings = get_pending_bookings_list()
    if not bookings:
        await update.message.reply_text('Нет заявок на рассмотрение.')
        return
    context.user_data['booking_idx'] = 0
    await show_booking(update, context)

def get_pending_bookings_list():
    """Get list of pending booking IDs"""
    global pending_bookings
    logger.info(f'Getting pending bookings list. Current pending_bookings: {pending_bookings}')
    
    if pending_bookings is None:
        logger.info('pending_bookings is None, loading from file...')
        load_pending_bookings()
        logger.info(f'Loaded pending_bookings: {pending_bookings}')
    
    # Фильтруем только заявки в статусе 'pending'
    result = [booking_id for booking_id, booking in pending_bookings.items() if booking.get('status') == 'pending']
    logger.info(f'Filtered pending booking IDs: {result}')
    return result

def get_admin_booking_inline_keyboard(idx, total):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = []
    if total > 1:
        nav_row = [
            InlineKeyboardButton('⬅️', callback_data='admin_prev'),
            InlineKeyboardButton('➡️', callback_data='admin_next')
        ]
        keyboard.append(nav_row)

    bookings = get_pending_bookings_list()
    if not bookings or idx >= len(bookings):
        return InlineKeyboardMarkup(keyboard)
    
    booking_id = bookings[idx]
    action_row = [
        InlineKeyboardButton('✅ Одобрить', callback_data=f'approve_{booking_id}'),
        InlineKeyboardButton('❌ Отклонить', callback_data=f'reject_{booking_id}')
    ]
    keyboard.append(action_row)
    return InlineKeyboardMarkup(keyboard)


async def show_booking(update, context, edit=False):
    try:
        bookings = get_pending_bookings_list()
        idx = context.user_data.get('booking_idx', 0)
        
        if not bookings:
            text = 'ℹ️ Нет заявок на рассмотрение.'
            if edit and hasattr(update, 'callback_query'):
                await update.callback_query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        if idx >= len(bookings):
            idx = 0
            context.user_data['booking_idx'] = idx
        
        booking_id = bookings[idx]
        booking = pending_bookings[booking_id]
        
        # Формируем временной диапазон
        time_range = booking.get('time_range', '—')
        if not time_range or time_range == '—':
            start_time = booking.get('start_time', '')
            end_time = booking.get('end_time', '')
            if start_time and end_time:
                time_range = f'{start_time}-{end_time}'
        
        # Формируем сообщение о заявке
        try:
            source = booking.get('source', 'telegram')
            source_emoji = '📱' if source == 'telegram' else '💬'
            source_name = 'Telegram' if source == 'telegram' else 'MAX'
            
            text = (
                f'📣 <b>Заявка на бронирование</b>\n\n'
                f'👤 Пользователь: {booking.get("fullname", "—")} (@{booking.get("username", "—")})\n'
                f'{source_emoji} Источник: {source_name}\n'
                f'📅 Дата: {booking.get("date", "—")}\n'
                f'⏰ Время: {time_range}\n'
                f'📝 Описание: {booking.get("description", "—")}\n\n'
                f'🔹 ID заявки: <code>{booking_id}</code>'
            )
        except Exception as e:
            logger.error(f'Error formatting booking message: {str(e)}')
            text = '❌ Ошибка при формировании сообщения.'
        
        # Создаем кнопки управления
        reply_markup = get_admin_booking_inline_keyboard(idx, len(bookings))
        
        # Отправляем или обновляем сообщение
        if edit and hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
            
    except Exception as e:
        logger.error(f'Error in show_booking: {str(e)}')
        error_text = '❌ Ошибка при показе заявки.'
        if edit and hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)


@admin_required
async def admin_booking_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle navigation between pending bookings"""
    try:
        query = update.callback_query
        action = query.data  # 'admin_prev' or 'admin_next'
        
        bookings = get_pending_bookings_list()
        if not bookings:
            await query.edit_message_text('ℹ️ Нет заявок на рассмотрение.')
            return
        
        current_idx = context.user_data.get('booking_idx', 0)
        
        if action == 'admin_prev':
            current_idx = (current_idx - 1) if current_idx > 0 else len(bookings) - 1
        else:  # admin_next
            current_idx = (current_idx + 1) if current_idx < len(bookings) - 1 else 0
        
        context.user_data['booking_idx'] = current_idx
        await show_booking(update, context, edit=True)
        
    except Exception as e:
        logger.error(f'Error in admin_booking_nav: {str(e)}')
        await update.callback_query.edit_message_text('❌ Ошибка при навигации по заявкам.')

def check_calendar_event(service, booking):
    try:
        date_str = booking['date']

        if 'time_range' in booking:
            time_range = booking['time_range']
            start_time, end_time = time_range.split('-')
        else:
            start_time = booking['start_time']
            end_time = booking['end_time']
        
        # Пытаемся сначала с форматом dd.mm.yyyy
        try:
            start_dt = datetime.datetime.strptime(f'{date_str} {start_time.strip()}', '%d.%m.%Y %H:%M')
            end_dt = datetime.datetime.strptime(f'{date_str} {end_time.strip()}', '%d.%m.%Y %H:%M')
        except ValueError:
            # Если не получилось, пробуем формат yyyy-mm-dd
            start_dt = datetime.datetime.strptime(f'{date_str} {start_time.strip()}', '%Y-%m-%d %H:%M')
            end_dt = datetime.datetime.strptime(f'{date_str} {end_time.strip()}', '%Y-%m-%d %H:%M')
        finally:
            # Добавляем часовой пояс к датам
            tz = pytz.timezone('Asia/Krasnoyarsk')
            start_dt = tz.localize(start_dt)
            end_dt = tz.localize(end_dt)

        # Проверяем доступность в календаре
        return check_calendar_events_in_range(service, start_dt, end_dt)
        
    except Exception as e:
        logger.error(f'Error checking calendar events: {str(e)}')
        return None

@admin_required
async def admin_approve_booking(update: Update, context: ContextTypes.DEFAULT_TYPE, booking_id: str = None):
    try:
        is_callback = hasattr(update, 'callback_query')
        message = update.callback_query.message if is_callback else update.message
        admin_user = update.callback_query.from_user if is_callback else update.effective_user

        # Извлекаем booking_id из callback_data или аргументов команды
        if is_callback:
            try:
                if not booking_id:
                    data = update.callback_query.data
                    if data.startswith('approve_'):
                        booking_id = data.replace('approve_', '')
            except Exception as e:
                logger.error(f'Error processing callback data: {str(e)}')
                return False
        elif not booking_id and context.args:
            booking_id = context.args[0]

        if not booking_id:
            error_text = '❌ Укажите ID заявки.'
            if is_callback:
                await message.edit_text(error_text)
            else:
                await message.reply_text(error_text)
            return False

        global pending_bookings
        pending_bookings = load_pending_bookings()

        if booking_id not in pending_bookings:
            error_text = '❌ Заявка не найдена.'
            if is_callback:
                await message.edit_text(error_text)
            else:
                await message.reply_text(error_text)
            return False

        booking = pending_bookings[booking_id]
        if booking['status'] != 'pending':
            error_text = '❌ Эта заявка уже обработана.'
            if is_callback:
                await message.edit_text(error_text)
            else:
                await message.reply_text(error_text)
            return False

        # Создаем событие в календаре
        service = get_calendar_service()
        calendar_id = os.getenv('GOOGLE_CALENDAR_ID')

        date_str = booking['date']
        start_time = booking['start_time']
        end_time = booking['end_time']

        # Преобразуем дату и время в datetime
        start_dt = datetime.datetime.strptime(f'{date_str} {start_time}', '%d.%m.%Y %H:%M')
        end_dt = datetime.datetime.strptime(f'{date_str} {end_time}', '%d.%m.%Y %H:%M')

        # Добавляем часовой пояс
        tz = pytz.timezone('Asia/Krasnoyarsk')
        start = tz.localize(start_dt)
        end = tz.localize(end_dt)

        event = {
            'summary': booking.get('title', 'Бронирование аудитории'),
            'description': f'user_id: {booking["user_id"]}\n{booking["description"]}',
            'start': {
                'dateTime': start.isoformat(),
                'timeZone': 'Asia/Krasnoyarsk',
            },
            'end': {
                'dateTime': end.isoformat(),
                'timeZone': 'Asia/Krasnoyarsk',
            },
        }

        try:
            event = service.events().insert(calendarId=calendar_id, body=event).execute()
            event_id = event['id']

            # Обновляем статус заявки
            booking['status'] = 'approved'
            booking['approved_by'] = admin_user.username or str(admin_user.id)
            booking['event_id'] = event_id
            save_pending_bookings(pending_bookings)

            # Отправляем уведомление пользователю
            user_message = (
                f'✅ Ваша заявка одобрена!\n\n'
                f'📅 Дата: {booking["date"]}\n'
                f'⏰ Время: {booking["time_range"]}\n'
                f'📝 Описание: {booking["description"]}'
            )

            await send_user_notification(context, booking, user_message)

            # Логируем успешное одобрение
            log_admin_action(
                admin_user,
                message.chat_id,
                'APPROVE_BOOKING_SUCCESS',
                f'Заявка {booking_id} одобрена'
            )
            
            # Формируем сообщение с полной информацией
            admin_info = format_admin_name(admin_user)
            
            admin_message = (
                f'✅ Заявка одобрена!\n\n'
                f'📝 Описание: {booking["description"]}\n'
                f'👤 Пользователь: {booking["fullname"]} (@{booking["username"]})\n'
                f'📅 Дата: {booking["date"]}\n'
                f'⏰ Время: {booking["time_range"]}\n'
                f'👤 Администратор: {admin_info}'
            )
            
            if is_callback:
                await message.edit_text(admin_message, parse_mode='HTML')
            else:
                await message.reply_text(admin_message, parse_mode='HTML')
            
            # Отправляем уведомление в группу администраторов
            await send_to_admin_group(
                context,
                admin_message,
                parse_mode='HTML',
                user_info=user_info
            )
            
            return True
            
        except Exception as e:
            logger.error(f'Error creating calendar event: {str(e)}')
            error_text = '❌ Ошибка при создании события в календаре.'
            if is_callback:
                await message.edit_text(error_text)
            else:
                await message.reply_text(error_text)
            return False
            
    except Exception as e:
        logger.error(f'Error in admin_approve_booking: {str(e)}')
        error_text = '❌ Ошибка при обработке заявки.'
        if is_callback:
            await message.edit_text(error_text)
        else:
            await message.reply_text(error_text)
        return False

@admin_required
async def admin_reject_booking(update: Update, context: ContextTypes.DEFAULT_TYPE, booking_id: str = None):
    try:
        global pending_bookings
        pending_bookings = load_pending_bookings()
        logger.info(f'Starting admin_reject_booking for booking_id: {booking_id}')
        logger.info(f'Current pending bookings: {json.dumps(pending_bookings, ensure_ascii=False, indent=2)}')

        is_callback = hasattr(update, 'callback_query')
        message = update.callback_query.message if is_callback else update.message
        admin_user = update.callback_query.from_user if is_callback else update.effective_user

        if not booking_id and context.args:
            booking_id = context.args[0]
        if not booking_id:
            error_text = '❌ Укажите ID заявки.'
            logger.error(f'No booking ID provided')
            if is_callback:
                await message.edit_text(error_text)
            else:
                await message.reply_text(error_text)
            return False
        
        logger.info(f'Checking booking ID: {booking_id}')
        if booking_id not in pending_bookings:
            error_text = '❌ Заявка не найдена.'
            logger.error(f'Booking {booking_id} not found in pending_bookings')
            if is_callback:
                await message.edit_text(error_text)
            else:
                await message.reply_text(error_text)
            return False
        
        booking = pending_bookings[booking_id]
        if booking['status'] != 'pending':
            error_text = '❌ Эта заявка уже обработана.'
            if is_callback:
                await message.edit_text(error_text)
            else:
                await message.reply_text(error_text)
            return False

        context.user_data['awaiting_reject_reason'] = True
        context.user_data['reject_booking_id'] = booking_id

        prompt_text = (
            f'Введите причину отклонения заявки:\n'
            f'Дата: {booking.get("date", "—")}\n'
            f'Время: {booking.get("start_time", "")} - {booking.get("end_time", "—")}\n'
            f'Описание: {booking.get("description", "—")}\n'
            f'Пользователь: {booking.get("fullname", "—")} (@{booking.get("username", "—")})\n\n'
            'Введите причину:'
        )
        if is_callback:

            await update.callback_query.answer()
            await context.bot.send_message(chat_id=update.callback_query.from_user.id, text=prompt_text)
            await message.edit_text('❗️ Ожидается ввод причины отклонения...')
        else:
            await message.reply_text(prompt_text)
        return True
        
    except Exception as e:
        logger.error(f'Error in admin_reject_booking: {str(e)}')
        error_text = '❌ Произошла ошибка при отклонении заявки.'
        if is_callback:
            await message.edit_text(error_text)
        else:
            await message.reply_text(error_text)
        return False

@admin_required
async def admin_cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        service = get_calendar_service()

        tz = pytz.timezone('Asia/Krasnoyarsk')
        now = datetime.datetime.now(datetime.timezone.utc).astimezone(tz)
        events_result = service.events().list(
            calendarId=os.getenv('GOOGLE_CALENDAR_ID'),
            timeMin=now.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            await update.message.reply_text('ℹ️ Нет активных бронирований.')
            return

        bookings = []
        for event in events:
            if 'dateTime' not in event['start'] or 'dateTime' not in event['end']:
                continue

            start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')).astimezone(tz)
            if start <= now:
                continue

            end = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00')).astimezone(tz)
            description = event.get('description', '')
            user_id = None
            for line in description.split('\n'):
                if line.startswith('user_id:'):
                    try:
                        user_id = int(line.split(':')[1].strip())
                    except:
                        pass
                    break
                    
            bookings.append({
                'id': event['id'],
                'summary': event['summary'],
                'start': start.strftime('%d.%m %H:%M'),
                'end': end.strftime('%H:%M'),
                'description': description,
                'user_id': user_id
            })
        
        if not bookings:
            await update.message.reply_text('ℹ️ Нет предстоящих бронирований.')
            return
        keyboard = []
        for booking in bookings:
            user_info = f" (ID: {booking['user_id']})" if booking['user_id'] else ""
            button_text = f"{booking['start']}-{booking['end']} {booking['summary']}{user_info}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f'cancel_{booking["id"]}')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            'Выберите бронирование для отмены:',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f'Error in admin_cancel_booking: {str(e)}')
        await update.message.reply_text('❌ Произошла ошибка при отмене бронирования.')

@admin_required
async def admin_process_cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.user_data.get('awaiting_cancel_booking'):
            return
        
        text = update.message.text
        
        if text == BTN_BACK:
            context.user_data.pop('awaiting_cancel_booking', None)
            context.user_data.pop('bookings', None)
            await update.message.reply_text(
                'Отмена операции.',
                reply_markup=get_admin_keyboard()
            )
            return
        
        event_id = context.user_data['bookings'].get(text)
        if not event_id:
            await update.message.reply_text('❌ Бронирование не найдено.', reply_markup=get_admin_keyboard())
            return
        service = get_calendar_service()
        try:
            service.events().delete(
                calendarId=os.getenv('GOOGLE_CALENDAR_ID'),
                eventId=event_id
            ).execute()
        except Exception as e:
            logger.error(f'Error deleting event from calendar: {str(e)}')
            await update.message.reply_text('❌ Ошибка при отмене бронирования в календаре.', reply_markup=get_user_keyboard())
            return

        for booking in pending_bookings.values():
            if booking.get('event_id') == event_id:
                booking['status'] = 'cancelled'
                booking['cancelled_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                booking['cancelled_by'] = update.effective_user.id

                # Отправляем уведомление пользователю
                user_message = (
                    f'❌ Ваша заявка на бронирование была отменена администратором.\n'
                    f'Дата: {booking["date"]}\n'
                    f'Время: {booking["start_time"]}-{booking["end_time"]}\n'
                    f'Описание: {booking["description"]}'
                )
                
                await send_user_notification(context, booking, user_message)
                
                # Отправляем уведомление в админ-чат
                admin_message = (
                    f'❌ Бронирование отменено!\n\n'
                    f'👤 Пользователь: {booking["fullname"]} (@{booking["username"]})\n'
                    f'📅 Дата: {booking["date"]}\n'
                    f'⏰ Время: {booking["start_time"]}-{booking["end_time"]}\n'
                    f'📝 Описание: {booking["description"]}'
                )
                
                # Информация о пользователе, выполнившем действие
                user_info = get_user_info(update.effective_user)
                
                await send_to_admin_group(
                    context,
                    admin_message,
                    parse_mode='HTML',
                    user_info=user_info
                )
                
                break

        save_pending_bookings()

        context.user_data.pop('awaiting_cancel_booking', None)
        context.user_data.pop('bookings', None)
        
        is_admin = str(update.effective_user.id) == os.getenv('ADMIN_USER_ID')
        await update.message.reply_text(
            '✅ Бронирование успешно отменено.',
            reply_markup=get_admin_keyboard() if is_admin else get_user_keyboard()
        )
        
    except Exception as e:
        logger.error(f'Error in admin_process_cancel_booking: {str(e)}')
        is_admin_flag = is_admin(update.effective_user.id)
        await update.message.reply_text('❌ Произошла ошибка при отмене бронирования.', reply_markup=get_admin_keyboard() if is_admin_flag else get_user_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f'Start command received from user {update.effective_user.id}')
    try:
        user = update.effective_user
        logger.info(f'User info: id={user.id}, name={user.full_name}')

        is_admin_flag = is_admin(user.id)
        logger.info(f'Is admin: {is_admin_flag}')
        keyboard = get_admin_keyboard() if is_admin_flag else get_user_keyboard()
        
        await update.message.reply_text(
            f'👋 Привет, {user.full_name}!\n\n'
            'Я помогу забронировать СибКодинг.\n\n'
            'Чтобы начать, выберите одно из действий ниже:',
            reply_markup=keyboard
        )
        logger.info('Start command processed successfully')
    except Exception as e:
        logger.error(f'Error in start command: {str(e)}')
        await update.message.reply_text('❌ Произошла ошибка при запуске бота.')

async def check_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        service = get_calendar_service()
        now = datetime.datetime.now(datetime.timezone.utc)
        events_result = service.events().list(
            calendarId=os.getenv('GOOGLE_CALENDAR_ID'),
            timeMin=now.isoformat(),
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            await update.message.reply_text('📅 Нет запланированных занятий.')
            return
        
        bookings = []
        for event in events:
            # Берём только события с dateTime (не all-day)
            if 'dateTime' not in event['start'] or 'dateTime' not in event['end']:
                continue
            # Сравниваем время окончания в UTC
            end_utc = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
            if end_utc <= now:
                continue
            # Для вывода — преобразуем в локальное время (UTC+7)
            start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')).astimezone(datetime.timezone(datetime.timedelta(hours=7)))
            end = end_utc.astimezone(datetime.timezone(datetime.timedelta(hours=7)))
            bookings.append({
                'id': event['id'],
                'summary': event['summary'],
                'start': start.strftime('%d.%m %H:%M'),
                'end': end.strftime('%H:%M'),
                'description': event.get('description', '')
            })
        
        # Создаем клавиатуру с бронированиями
        keyboard = []
        for booking in bookings:
            button_text = f"{booking['start']}-{booking['end']} {booking['summary']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f'cancel_{booking["id"]}')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            'Выберите бронирование для отмены:',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f'Error in check_schedule: {str(e)}')
        await update.message.reply_text('❌ Произошла ошибка при получении расписания.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin_flag = is_admin(update.effective_user.id)
    
    help_text = [
        '📖 Доступные команды:',
        '/start - Начать работу с ботом',
        '/help - Показать это сообщение'
    ]
    
    if is_admin_flag:
        help_text.extend([
            '\n🔑 Команды администратора:',
            '/settings - Настройки бота',
            '/cancel_booking - Отменить бронирование',
            '/approve <id> - Одобрить заявку',
            '/reject <id> - Отклонить заявку'
        ])
    
    await update.message.reply_text(
        '\n'.join(help_text),
        reply_markup=get_admin_keyboard() if is_admin_flag else get_user_keyboard()
    )


def get_pending_bookings_list():
    return [bid for bid, b in pending_bookings.items() if b.get('status', 'pending') == 'pending']

def get_all_bookings_list(status: str = None):
    if status:
        return [bid for bid, b in pending_bookings.items() if b.get('status', 'pending') == status]
    return list(pending_bookings.keys())

async def process_booking_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('awaiting_reject_reason'):
        logger.info(f'Processing rejection reason: {text}')
        from bot import handle_reject_reason
        await handle_reject_reason(update, context, text)
        return
        
    if context.user_data.get('awaiting_cancel_reason'):
        logger.info(f'Processing cancel reason: {text}')
        await handle_cancel_reason(update, context)
        return
    
    if context.user_data.get('awaiting_cancel_booking'):
        return
    
    if text in [BTN_BOOK, BTN_BOOKED_TIMES, BTN_MAIN_MENU]:
        return  
    
    user_data = context.user_data
    step = user_data.get('step')
    
    if text == BTN_CONTINUE:
        context.user_data['step'] = 'fullname'
        await update.message.reply_text('Пожалуйста, введите ФИО полностью (например, Иванов Иван Иванович):', reply_markup=ReplyKeyboardRemove())
        return
    
    if step == 'fullname' and is_admin(user_id):
        await update.message.reply_text('Выберите действие:', reply_markup=get_admin_keyboard())
        return
    if step == 'fullname':
        user_data['fullname'] = text
        await update.message.reply_text('Введите дату бронирования в формате ДД.ММ (или ДД.ММ.ГГГГ):')
        user_data['step'] = 'date'
    elif step == 'date':
        try:
            if not is_date_available(text):
                months = get_available_months()
                months_str = [datetime.datetime(year, month, 1).strftime('%B %Y') for year, month in months]
                await update.message.reply_text(
                    '❌ Дата недоступна для бронирования.\n'
                    'Доступные месяцы:\n' + '\n'.join(f'- {m}' for m in months_str)
                )
                return
            
            if len(text.split('.')) == 3:
                date = datetime.datetime.strptime(text, '%d.%m.%Y').date()
            else:
                date = datetime.datetime.strptime(text, '%d.%m').date().replace(year=datetime.datetime.now(datetime.timezone.utc).year)
        except ValueError:
            await update.message.reply_text('❌ Неверный формат даты. Введите в формате ДД.ММ или ДД.ММ.ГГГГ.')
            return
        
        user_data['date'] = date.strftime('%Y-%m-%d')
        await update.message.reply_text('Введите время в формате ЧЧ:ММ-ЧЧ:ММ:')
        user_data['step'] = 'time'
    elif step == 'time':
        try:
            start, end = text.replace(' ', '').split('-')
            start_time = datetime.datetime.strptime(start, '%H:%M').time()
            end_time = datetime.datetime.strptime(end, '%H:%M').time()
        except Exception:
            await update.message.reply_text('❌ Неверный формат времени. Введите в формате ЧЧ:ММ-ЧЧ:ММ.')
            return
        if start_time >= end_time:
            await update.message.reply_text('❌ Время начала должно быть раньше времени окончания.')
            return
        user_data['start_time'] = start_time.strftime('%H:%M')
        user_data['end_time'] = end_time.strftime('%H:%M')
        await update.message.reply_text('Введите описание цели бронирования:')
        user_data['step'] = 'description'
    elif step == 'description':
        user_data['description'] = text
        tz = pytz.timezone('Asia/Krasnoyarsk')
        date_str = user_data['date']
        start_time = user_data['start_time']
        end_time = user_data['end_time']
        year = datetime.datetime.now(datetime.timezone.utc).year
        dt_start = dt_end = None
        try:
            dt_start = datetime.datetime.strptime(f'{date_str}.{year} {start_time}', '%d.%m.%Y %H:%M').replace(tzinfo=tz)
            dt_end = datetime.datetime.strptime(f'{date_str}.{year} {end_time}', '%d.%m.%Y %H:%M').replace(tzinfo=tz)
        except Exception as e1:
            try:
                dt_start = datetime.datetime.strptime(f'{date_str} {start_time}', '%Y-%m-%d %H:%M').replace(tzinfo=datetime.timezone(datetime.timedelta(hours=7)))
                dt_end = datetime.datetime.strptime(f'{date_str} {end_time}', '%Y-%m-%d %H:%M').replace(tzinfo=datetime.timezone(datetime.timedelta(hours=7)))
            except Exception as e2:
                logger.error(f'Ошибка парсинга даты для Google Calendar: {e1} | {e2} | date_str={date_str}, start_time={start_time}, end_time={end_time}')
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text=f'Ошибка парсинга даты для Google Calendar: {e1} | {e2} | date_str={date_str}, start_time={start_time}, end_time={end_time}'
                )
                raise
        if not bot_utils.is_time_available(dt_start, dt_end):
            await update.message.reply_text('❌ Это время уже занято. Попробуйте другое.')
            await update.message.reply_text('Выберите действие:', reply_markup=get_user_keyboard())
            user_data.clear()
            return
        user = update.effective_user
        booking_id = f'{user.id}_{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}'
        booking = {
            'id': booking_id,
            'user_id': user.id,
            'username': user.username,
            'fullname': user_data['fullname'],
            'date': user_data['date'],
            'start_time': user_data['start_time'],
            'end_time': user_data['end_time'],
            'description': user_data['description'],
            'start_datetime': dt_start.isoformat(),  # ISO 8601 with timezone
            'end_datetime': dt_end.isoformat(),      # ISO 8601 with timezone
            'status': 'pending',
            'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'event_id': None,
            'source': 'telegram',
            'platform_user_id': user.id
        }
        pending_bookings[booking_id] = booking
        save_pending_bookings()

        def get_admin_ids():
            import csv
            csv_path = os.path.join(os.path.dirname(__file__), 'admin_users.csv')
            admin_ids = []
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if row and row[0].strip().isdigit():
                            admin_ids.append(int(row[0].strip()))
            except Exception as e:
                logger.warning(f'Не удалось загрузить список админов: {e}')
            return admin_ids

        admin_ids = get_admin_ids()
        if admin_ids:
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton('✅ Одобрить', callback_data=f'approve_{booking_id}'),
                    InlineKeyboardButton('❌ Отклонить', callback_data=f'reject_{booking_id}')
                ]
            ])
            for admin_id in admin_ids:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            '🚨 <b>НОВАЯ ЗАЯВКА!</b> 🚨\n'
                            '━━━━━━━━━━━━━━━━━━\n'
                            f'<b>ФИО:</b> {booking["fullname"]}\n'
                            f'<b>Дата:</b> {booking["date"]}\n'
                            f'<b>Время:</b> {booking["start_time"]}-{booking["end_time"]}\n'
                            f'<b>Описание:</b> {booking["description"]}\n'
                            f'<b>От:</b> @{user.username or user.id}\n'
                            '━━━━━━━━━━━━━━━━━━\n'
                            '<b>‼️ Не забудьте обработать заявку! ‼️</b>'
                        ),
                        reply_markup=kb,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.warning(f'Ошибка отправки уведомления админу {admin_id}: {e}')
        await update.message.reply_text('✅ Ваша заявка отправлена на рассмотрение администратору.', reply_markup=get_user_keyboard())
        context.user_data.clear()

async def admin_booking_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    admin = update.effective_user
    if data == 'admin_prev':
        idx = context.user_data.get('booking_idx', 0)
        if idx > 0:
            context.user_data['booking_idx'] = idx - 1
        await show_booking(update, context, edit=True)
        await query.answer()
        return
    elif data == 'admin_next':
        bookings = get_pending_bookings_list()
        idx = context.user_data.get('booking_idx', 0)
        if idx < len(bookings) - 1:
            context.user_data['booking_idx'] = idx + 1
        await show_booking(update, context, edit=True)
        await query.answer()
        return
    elif data.startswith('approve_'):
        booking_id = data.split('_', 1)[1]
        if not booking_id:
            await query.answer('Некорректный ID заявки')
            return
        
        success = await admin_approve_booking(update, context, booking_id)
        
        if success:
            await query.answer('Заявка успешно одобрена!')
            bookings = get_pending_bookings_list()
            if bookings:
                context.user_data['booking_idx'] = min(context.user_data.get('booking_idx', 0), len(bookings)-1)
                await show_booking(update, context, edit=True)
            else:
                await query.edit_message_text('Нет заявок на рассмотрение.')
    elif data.startswith('reject_'):
        booking_id = data.split('_', 1)[1]
        if not booking_id or booking_id not in pending_bookings:
            await query.answer('Заявка не найдена.')
            return
        await admin_reject_booking(update, context, booking_id)
    else:
        await query.answer('Неизвестное действие.')


def format_booking_message(booking):
    return (f"ФИО: {booking.get('fullname', '—')}\n"
            f"Дата: {booking.get('date', '—')}\n"
            f"Время: {booking.get('time_range', '—')}\n"
            f"Описание: {booking.get('description', '—')}\n"
            f"Статус: {booking.get('status', 'pending')}")

async def handle_booking_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == BTN_NEXT:
        current_index = context.user_data.get('current_booking_index', 0)
        pending_list = get_pending_bookings_list()
        
        if current_index + 1 < len(pending_list):
            current_index += 1
            context.user_data['current_booking_index'] = current_index
            booking_id, booking = pending_list[current_index]
            await update.message.reply_text(
                format_booking_message(booking),
                reply_markup=get_booking_navigation_keyboard(current_index, len(pending_list))
            )
        else:
            await update.message.reply_text('ℹ️ Вы достигли конца списка.')
    
    elif text == BTN_PREV:
        current_index = context.user_data.get('current_booking_index', 0)
        pending_list = get_pending_bookings_list()
        
        if current_index > 0:
            current_index -= 1
            context.user_data['current_booking_index'] = current_index
            booking_id, booking = pending_list[current_index]
            await update.message.reply_text(
                format_booking_message(booking),
                reply_markup=get_booking_navigation_keyboard(current_index, len(pending_list))
            )
        else:
            await update.message.reply_text('ℹ️ Вы находитесь в начале списка.')
    
    elif text == BTN_BACK:
        context.user_data.pop('current_booking_index', None)
        await update.message.reply_text(
            'Выберите действие:',
            reply_markup=get_admin_keyboard()
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f'Exception while handling an update: {context.error}')
    if update and update.effective_message:
        await update.effective_message.reply_text('❌ Произошла ошибка. Попробуйте позже.')

def main():
    logger.info('Starting bot initialization')
    logger.info(f'Current working directory: {os.getcwd()}')
    logger.info(f'Token: {os.getenv("TELEGRAM_BOT_TOKEN")[:5]}... Calendar ID: {os.getenv("GOOGLE_CALENDAR_ID")[:5]}...')
    logger.info(f'Checking credentials.json exists: {os.path.exists("credentials.json")}')
    logger.info(f'Checking token.pickle exists: {os.path.exists("token.pickle")}')
    
    # Загружаем заявки
    global pending_bookings
    pending_bookings = load_pending_bookings()
    
    # Подключаемся к Google Calendar
    try:
        service = get_calendar_service()
        calendar_id = os.getenv('GOOGLE_CALENDAR_ID')
        service.events().list(calendarId=calendar_id, maxResults=1).execute()
        logger.info('Successfully connected to Google Calendar')
    except Exception as e:
        logger.error(f'Error connecting to Google Calendar: {str(e)}')
        return

    # Создаем приложение
    logger.info(f'Building application with token: {os.getenv("TELEGRAM_BOT_TOKEN")[:5]}...')
    application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
    logger.info('Application built successfully')

    # Добавляем обработчики команд
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('admin_approve', admin_approve_booking))
    application.add_handler(CommandHandler('admin_reject', admin_reject_booking))
    application.add_handler(CommandHandler('check_schedule', check_schedule))
    
    # Обработчики кнопок пользователя
    application.add_handler(MessageHandler(filters.Text([BTN_BOOK]), start_booking))
    application.add_handler(MessageHandler(filters.Text([BTN_BOOKED_TIMES]), booked_times_handler))
    
    # Обработчики кнопок админа
    application.add_handler(MessageHandler(filters.Text([BTN_VIEW_BOOKINGS]), view_bookings))
    application.add_handler(MessageHandler(filters.Text([BTN_CANCEL_BOOKING]), admin_cancel_booking))
    application.add_handler(MessageHandler(filters.Text([BTN_SETTINGS]), admin_settings))
    
    # Обработчики кнопок навигации
    application.add_handler(MessageHandler(filters.Text([BTN_NEXT, BTN_PREV, BTN_BACK]), handle_booking_navigation))
    
    # Обработчики колбэков
    application.add_handler(CallbackQueryHandler(admin_approve_booking, pattern='^approve_'))
    application.add_handler(CallbackQueryHandler(admin_reject_booking, pattern='^reject_'))
    application.add_handler(CallbackQueryHandler(admin_process_cancel_booking, pattern='^cancel_'))
    application.add_handler(CallbackQueryHandler(admin_booking_nav, pattern='^nav_'))
    
    # Общий обработчик текста
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Text(
        [BTN_BOOK, BTN_BOOKED_TIMES, BTN_VIEW_BOOKINGS, BTN_CANCEL_BOOKING, BTN_SETTINGS, BTN_NEXT, BTN_PREV, BTN_BACK]
    ), process_booking_input))

    logger.info('Starting polling')
    application.run_polling(drop_pending_updates=True)
    logger.info('Bot started successfully')

if __name__ == '__main__':
    main()
