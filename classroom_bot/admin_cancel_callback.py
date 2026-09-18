from telegram import Update
from telegram.ext import ContextTypes
import os
import datetime
from bot import get_calendar_service, pending_bookings, save_pending_bookings, get_admin_keyboard
import logging
from admin_logger import log_admin_action, format_admin_name

logger = logging.getLogger(__name__)

async def admin_cancel_booking_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    admin_user = update.effective_user
    chat_id = update.effective_chat.id
    
    from bot import is_admin
    if not query or not data.startswith('cancel_') or not is_admin(admin_user.id):
        await query.answer('Недоступно')
        return
        
    event_id = data.replace('cancel_', '')
    
    # Логируем начало действия
    log_admin_action(
        admin_user,
        chat_id,
        'CANCEL_BOOKING_START',
        f'Начата отмена брони {event_id}'
    )
    
    service = get_calendar_service()
    
    try:
        event = service.events().get(
            calendarId=os.getenv('GOOGLE_CALENDAR_ID'),
            eventId=event_id
        ).execute()
        
        import pytz
        from datetime import datetime
        
        tz = pytz.timezone('Asia/Krasnoyarsk')
        now = datetime.now(tz)
        start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')).astimezone(tz)
        
        if start <= now:
            log_admin_action(
                admin_user,
                chat_id,
                'CANCEL_BOOKING_FAIL',
                f'Попытка отменить уже начавшуюся бронь {event_id}'
            )
            await query.answer('❌ Нельзя отменить уже начавшуюся бронь')
            return
        
        description = event.get('description', '')
        user_id = None
        for line in description.split('\n'):
            if line.startswith('user_id:'):
                try:
                    user_id = int(line.split(':')[1].strip())
                except:
                    pass
                break
        
        context.user_data['awaiting_cancel_reason'] = True
        context.user_data['cancel_event_id'] = event_id
        context.user_data['cancel_user_id'] = user_id
        context.user_data['admin_user'] = {
            'id': admin_user.id,
            'name': format_admin_name(admin_user)
        }
        
        summary = event.get('summary', '—')
        end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00')).astimezone(tz)
        
        msg = f'Введите причину отмены для бронирования:\n'
        msg += f'Название: {summary}\n'
        msg += f'Дата и время: {start.strftime("%d.%m.%Y %H:%M")} - {end.strftime("%H:%M")}\n'
        if user_id:
            msg += f'ID пользователя: {user_id}\n'
        msg += f'Описание: {description}'
        
        await query.edit_message_text(msg)
        
    except Exception as e:
        logger.error(f'Ошибка получения события для отмены: {e}')
        log_admin_action(
            admin_user,
            chat_id,
            'CANCEL_BOOKING_ERROR',
            f'Ошибка при отмене брони {event_id}: {str(e)}'
        )
        await query.edit_message_text('❌ Не удалось получить данные бронирования.')
        return

