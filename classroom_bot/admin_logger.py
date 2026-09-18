import logging
import os
from datetime import datetime
import pytz
from typing import Optional
from telegram import User

def setup_admin_logger():
    # Создаем директорию для логов если её нет
    if not os.path.exists('logs'):
        os.makedirs('logs')
        
    admin_logger = logging.getLogger('admin_actions')
    admin_logger.setLevel(logging.INFO)
    
    # Создаем файл с датой
    handler = logging.FileHandler('logs/admin_actions.log', encoding='utf-8')
    
    # Формат: [Время] [Чат] [Админ] [Действие] [Детали]
    formatter = logging.Formatter(
        '[%(asctime)s] [%(chat_type)s] [%(admin_name)s] [%(action)s] %(message)s'
    )
    handler.setFormatter(formatter)
    admin_logger.addHandler(handler)
    return admin_logger

def log_admin_action(admin_user: User, chat_id: int, action: str, details: str):
    logger = logging.getLogger('admin_actions')
    
    # Получаем имя админа
    admin_name = admin_user.full_name
    if admin_user.username:
        admin_name += f" (@{admin_user.username})"
    
    extra = {
        'chat_type': 'admin_chat' if str(chat_id).startswith('-100') else 'private',
        'admin_name': admin_name,
        'action': action
    }
    
    # Создаем объект с дополнительными полями
    class AdminLogRecord:
        def __init__(self):
            for key, value in extra.items():
                setattr(self, key, value)
    
    logger.info(details, extra=vars(AdminLogRecord()))

def format_admin_name(admin_user: User) -> str:
    """Форматирует имя администратора для отображения в сообщениях"""
    name = admin_user.full_name
    if admin_user.username:
        return f"{name} (@{admin_user.username})"
    return name
