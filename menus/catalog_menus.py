from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def region_menu():
    keyboard = [
        # pattern="^region_usa$" looks for this:
        [InlineKeyboardButton("🇺🇸 USA", callback_data="region_usa")],
        # pattern="^back_to_main$" looks for this:
        [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def plan_menu():
    keyboard = [
        [
            InlineKeyboardButton("1 Month", callback_data="plan_1m"),
            InlineKeyboardButton("2 Months", callback_data="plan_2m")
        ],
        [
            InlineKeyboardButton("3 Months", callback_data="plan_3m"),
            InlineKeyboardButton("4 Months", callback_data="plan_4m")
        ],
        
        [
            InlineKeyboardButton("5 Months", callback_data="plan_5m"),
            InlineKeyboardButton("6 Months", callback_data="plan_6m")
        ],
        
        
        
        [InlineKeyboardButton("1 Year", callback_data="plan_1y")],
        [InlineKeyboardButton("⬅️ Back to Regions", callback_data="back_to_regions")]
    ]
    return InlineKeyboardMarkup(keyboard)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def deposit_menu():
    # 2 buttons in one row: [Deposit] [Cancel]
    keyboard = [
        [
            InlineKeyboardButton("💎 Deposit Now", callback_data="start_topup"),
            InlineKeyboardButton("❌ Cancel", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def crypto_menu():
    keyboard = [
        [InlineKeyboardButton("₿ BTC", callback_data="pay_btc"), 
         InlineKeyboardButton("💎 TON", callback_data="pay_ton")],
         
        [InlineKeyboardButton("◎ SOL", callback_data="pay_sol"), 
         # 👇 CHANGED: Now triggers the sub-menu instead of direct payment
         InlineKeyboardButton("₮ USDT", callback_data="show_usdt_networks")], 
         
        [InlineKeyboardButton("Ł LTC", callback_data="pay_ltc"), 
         InlineKeyboardButton("Ξ ETH", callback_data="pay_eth")],
         
        [InlineKeyboardButton("🔗 TRON", callback_data="pay_trx"), 
         InlineKeyboardButton("⬅️ Back", callback_data="start_topup")]
    ]
    return InlineKeyboardMarkup(keyboard)