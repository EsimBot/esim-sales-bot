import os
from dotenv import load_dotenv

load_dotenv() # This loads the .env file

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
PLISIO_API_KEY = os.getenv("PLISIO_API_KEY")
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()]
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
PENDING_GROUP_ID = int(os.getenv("PENDING_GROUP_ID")) if os.getenv("PENDING_GROUP_ID") else None
DELIVERED_GROUP_ID = int(os.getenv("DELIVERED_GROUP_ID")) if os.getenv("DELIVERED_GROUP_ID") else None
PAYMENT_ALERTS_GROUP_ID = int(os.getenv("PAYMENT_ALERTS_GROUP_ID")) if os.getenv("PAYMENT_ALERTS_GROUP_ID") else None
SUPPORT_BOT_TOKEN = os.getenv("SUPPORT_BOT_TOKEN")
SUPPORT_GROUP_ID = int(os.getenv("SUPPORT_GROUP_ID")) if os.getenv("SUPPORT_GROUP_ID") else None
SUPPORT_BOT_URL = os.getenv("SUPPORT_BOT_URL")
CHECK_ACTIVATION = os.getenv("CHECK_ACTIVATION", "True").lower() == "true"