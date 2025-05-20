from pathlib import Path

BOT_DATA_PATH = Path('/bot_data')

ROOT_DOWNLOADS_PATH = BOT_DATA_PATH / 'downloads'
ROOT_DOWNLOADS_PATH.mkdir(exist_ok=True, parents=True)
