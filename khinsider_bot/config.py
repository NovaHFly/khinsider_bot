import os

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'no-token')
WEBSERVER_HOST = os.getenv('HOSTNAME', 'localhost')
WEBSERVER_PORT = int(os.getenv('PORT', '80'))
TELEGRAM_WEBHOOK_URL = os.getenv('WEBHOOK_URL', '/')
TELEGRAM_SECRET_TOKEN = os.getenv('WEBHOOK_TOKEN', 'no-token')
