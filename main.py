# -*- coding: utf-8 -*-
"""
بوت التداول الآلي السحابي لمنصة Render + UptimeRobot + Alpaca API
اسم الملف: main.py
المميزات:
1. مزود بسيرفر ويب خفيف (Flask) لاستقبال نداءات UptimeRobot كل 5 دقائق لمنع إغلاق Render المجاني.
2. يعمل في الخلفية (Background Thread) لفحص أسعار الأسهم وعقود الأوبشن اليومية (0 DTE) بانتظام.
3. يسحب المفاتيح بأمان من متغيرات البيئة (Environment Variables) في لوحة تحكم Render.
4. ملتزم بسقف 10,000 دولار لجميع الصفقات: TSLA, META, PLTR, AMD, NVDA.
"""

import os
import time
import threading
from datetime import datetime
from flask import Flask, jsonify
import pandas as pd

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetOptionContractsRequest,
    MarketOrderRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, ContractType
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

# ==============================================================================
# 1. إعداد تطبيق الويب (Flask) للاستجابة لـ UptimeRobot
# ==============================================================================
app = Flask(__name__)

bot_status = {
    "status": "Running",
    "last_check": None,
    "total_spent": 0.0,
    "executed_orders": []
}

@app.route("/")
def home():
    """هذا الرابط الذي يراقبه UptimeRobot لإبقاء السيرفر نشطاً 24/7"""
    return jsonify({
        "message": "Alpaca 0-DTE Trading Bot is LIVE & Active",
        "bot_status": bot_status,
        "server_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }), 200

@app.route("/health")
def health():
    return "OK", 200

# ==============================================================================
# 2. سحب المفاتيح من متغيرات البيئة (Render Environment Variables)
# ==============================================================================
API_KEY = os.getenv("ALPACA_KEY", "").strip()
SECRET_KEY = os.getenv("ALPACA_SECRET", "").strip()

if not API_KEY or not SECRET_KEY:
    print("⚠️ تحذير: تأكد من إضافة ALPACA_KEY و ALPACA_SECRET في قسم Environment في Render!")

trading_client = TradingClient(api_key=API_KEY, secret_key=SECRET_KEY, paper=True)
stock_data_client = StockHistoricalDataClient(api_key=API_KEY, secret_key=SECRET_KEY)

# ==============================================================================
# 3. إعدادات إدارة رأس المال وصفقات التحليل الفني
# ==============================================================================
MAX_TOTAL_BUDGET = 10000.00

SETUPS = {
    "TSLA": {
        "name": "Tesla, Inc.",
        "type": ContractType.CALL,
        "target_strike": 385.0,
        "underlying_entry_trigger": 380.0,
        "trigger_condition": "ABOVE",
        "budget_allocation": 2500.00,
    },
    "META": {
        "name": "Meta Platforms",
        "type": ContractType.PUT,
        "target_strike": 635.0,
        "underlying_entry_trigger": 639.0,
        "trigger_condition": "BELOW",
        "budget_allocation": 2500.00,
    },
    "PLTR": {
        "name": "Palantir Technologies",
        "type": ContractType.CALL,
        "target_strike": 172.5,
        "underlying_entry_trigger": 170.0,
        "trigger_condition": "ABOVE",
        "budget_allocation": 2000.00,
    },
    "AMD": {
        "name": "Advanced Micro Devices",
        "type": ContractType.PUT,
        "target_strike": 505.0,
        "underlying_entry_trigger": 518.0,
        "trigger_condition": "NEAR",
        "budget_allocation": 1500.00,
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "type": ContractType.PUT,
        "target_strike": 175.0,
        "underlying_entry_trigger": 175.5,
        "trigger_condition": "BELOW",
        "budget_allocation": 1500.00,
    }
}

# ==============================================================================
# 4. دوال البحث والتنفيذ لعقود أوبشن اليوم (0 DTE)
# ==============================================================================
def get_today_option_contract(underlying_symbol: str, contract_type: ContractType, target_strike: float):
    today_str = datetime.now().strftime("%Y-%m-%d")
    req = GetOptionContractsRequest(
        underlying_symbols=[underlying_symbol],
        expiration_date=today_str,
        contract_type=contract_type,
        limit=100
    )
    try:
        res = trading_client.get_option_contracts(req)
        contracts = res.option_contracts
        if not contracts:
            req_next = GetOptionContractsRequest(
                underlying_symbols=[underlying_symbol],
                contract_type=contract_type,
                limit=50
            )
            contracts = trading_client.get_option_contracts(req_next).option_contracts
            
        if not contracts:
            return None
        return min(contracts, key=lambda c: abs(float(c.strike_price) - target_strike))
    except Exception as e:
        print(f"[{underlying_symbol}] خطأ في جلب العقود: {e}")
        return None

def check_and_execute_trades():
    """حلقة الفحص التي تعمل في الخلفية بانتظام"""
    bot_status["last_check"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    for symbol, setup in SETUPS.items():
        if bot_status["total_spent"] >= MAX_TOTAL_BUDGET:
            break

        if symbol in bot_status["executed_orders"]:
            continue

        try:
            # 1. فحص سعر السهم
            quote_req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quote = stock_data_client.get_stock_latest_quote(quote_req)[symbol]
            price = float(quote.ask_price if setup["trigger_condition"] == "ABOVE" else quote.bid_price)

            # 2. التحقق من الشرط الفني
            triggered = False
            if setup["trigger_condition"] == "ABOVE" and price >= setup["underlying_entry_trigger"]:
                triggered = True
            elif setup["trigger_condition"] == "BELOW" and price <= setup["underlying_entry_trigger"]:
                triggered = True
            elif setup["trigger_condition"] == "NEAR" and price >= setup["underlying_entry_trigger"]:
                triggered = True

            if triggered:
                print(f"🚀 إشارة دخول مؤكدة لسهم {symbol} عند سعر ${price:.2f}")
                contract = get_today_option_contract(symbol, setup["type"], setup["target_strike"])
                if not contract:
                    continue

                # حساب التكلفة والكمية
                estimated_premium = 3.00 if symbol in ["TSLA", "META"] else 1.50
                contract_cost = estimated_premium * 100
                rem_budget = MAX_TOTAL_BUDGET - bot_status["total_spent"]
                alloc = min(setup["budget_allocation"], rem_budget)

                if alloc < contract_cost:
                    continue

                num_contracts = max(1, int(alloc // contract_cost))
                trade_cost = num_contracts * contract_cost

                # إرسال الأمر
                order = MarketOrderRequest(
                    symbol=contract.symbol,
                    qty=num_contracts,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                )
                res = trading_client.submit_order(order)
                print(f"✅ تم تنفيذ شراء أوبشن {contract.symbol} بعدد {num_contracts} عقود!")
                
                bot_status["total_spent"] += trade_cost
                bot_status["executed_orders"].append(symbol)

        except Exception as e:
            print(f"خطأ أثناء فحص {symbol}: {e}")

def background_trading_loop():
    """حلقة تكرار فحص السوق كل 60 ثانية أثناء عمل السيرفر"""
    print("🤖 بدأت حلقة التداول الآلي في الخلفية بنجاح.")
    while True:
        try:
            check_and_execute_trades()
        except Exception as e:
            print(f"خطأ في حلقة التداول: {e}")
        time.sleep(60)

# تشغيل حلقة التداول في خيط مستقل (Thread)
trading_thread = threading.Thread(target=background_trading_loop, daemon=True)
trading_thread.start()

# ==============================================================================
# 5. تشغيل خادم الويب على المنفذ المطلوب لمنصة Render
# ==============================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
