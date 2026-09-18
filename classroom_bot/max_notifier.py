import os
import logging
import maxbot
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

class MaxNotifier:
    """Класс для отправки уведомлений через MAX API"""
    
    def __init__(self):
        self.token = os.getenv('MAX_BOT_TOKEN')
        self.bot = None
        if self.token:
            try:
                self.bot = maxbot.Bot(self.token)
                logger.info('MAX Notifier initialized')
            except Exception as e:
                logger.error(f'Failed to initialize MAX Notifier: {str(e)}')
        else:
            logger.warning('MAX_BOT_TOKEN not found, MAX notifications disabled')
    
    async def send_message(self, user_id: int, text: str):
        """Отправка сообщения пользователю через MAX"""
        if not self.bot:
            logger.warning('MAX bot not initialized, cannot send message')
            return False
        
        try:
            await self.bot.send_message(
                user_id=user_id,
                text=text,
                notify=True
            )
            logger.info(f'MAX notification sent to user {user_id}')
            return True
        except Exception as e:
            logger.error(f'Error sending MAX notification to user {user_id}: {str(e)}')
            return False

# Глобальный экземпляр для использования в bot.py
max_notifier = MaxNotifier()
