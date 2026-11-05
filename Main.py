# ==============================================================================
# CRYPTO TRADING BOT: 24/7 FREE WEB SERVICE EDITION
# Platform: Render.com (Free Web Service Tier)
# Integration: Alpaca Crypto API + Flask Keep-Alive Server
# ==============================================================================

import os
import sys
import time
import threading
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from flask import Flask

# ------------------------------------------------------------------------------
# 1. إعداد خادم الويب (Flask Server) لإتاحة الخطة المجانية على Render
# ------------------------------------------------------------------------------
app = Flask(__name__)

# متغيرات عامة لعرض حالة البوت الحية عبر صفحة الويب
bot_status = {
    "status": "Starting",
    "last_cycle": "None",
    "regime": "Checking...",
    "total_invested": 0.0,
    "active_positions_count": 0,
    "message": "Initializing trading bot..."
}

@app.route('/')
def home():
    """
    صفحة فحص الحالة الصحية للبوت (Health Check)
    تُبقي السيرفر مستيقظاً 24/7 عند إرسال طلب إليها
    """
    return f"""
    <html>
    <head><title>Crypto Trading Bot Status</title></head>
    <body style="font-family: Arial; padding: 30px; background-color: #0f172a; color: #f8fafc;">
        <h2 style="color: #10b981;">✓ Crypto Trading Bot is ONLINE (24/7 Free Tier)</h2>
        <hr style="border-color: #334155;">
        <p><b>حالة النظام:</b> {bot_status['status']}</p>
        <p><b>آخر فحص وتحديث:</b> {bot_status['last_cycle']}</p>
        <p><b>حالة السوق (BTC Regime):</b> {bot_status['regime']}</p>
        <p><b>إجمالي المبلغ المستثمر:</b> ${bot_status['total_invested']:,.2f} / $10,000.00</p>
        <p><b>عدد الصفقات المفتوحة:</b> {bot_status['active_positions_count']} / 3</p>
        <p><b>آخر رسالة:</b> {bot_status['message']}</p>
        <hr style="border-color: #334155;">
        <p style="color: #94a3b8; font-size: 13px;">Managed autonomously on Render.com & Alpaca Markets</p>
    </body>
    </html>
    """, 200

# ------------------------------------------------------------------------------
# 2. قراءة مفاتيح Alpaca بأمان من Environment Variables
# ------------------------------------------------------------------------------
API_KEY = os.environ.get('ALPACA_KEY')
SECRET_KEY = os.environ.get('ALPACA_SECRET')
PAPER_TRADING = os.environ.get('PAPER_TRADING', 'True').lower() in ('true', '1', 'yes')

if not API_KEY or not SECRET_KEY:
    print("[ERROR] ALPACA_KEY or ALPACA_SECRET is missing from Environment Variables!", flush=True)
    # لا نوقف التطبيق فوراً لكي تظهر صفحة الويب وتبين الخطأ في Render
    bot_status["status"] = "Error: Missing API Keys"

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

try:
    trading_client = TradingClient(API_KEY, SECRET_KEY, paper=PAPER_TRADING)
    crypto_data_client = CryptoHistoricalDataClient()
except Exception as e:
    trading_client = None
    crypto_data_client = None
    print(f"! خطأ في تهيئة Alpaca Client: {e}", flush=True)

# ------------------------------------------------------------------------------
# 3. قواعد التداول وإدارة المخاطر
# ------------------------------------------------------------------------------
MAX_TOTAL_INVESTMENT = 10000.0   # سقف الميزانية 10,000 دولار
MAX_ACTIVE_POSITIONS = 3         # أقصى عدد صفقات مفتوحة
POSITION_SIZE = 3300.0           # حجم الصفقة الواحدة (3300 دولار × 3)

TAKE_PROFIT_DOLLARS = 50.0       # هدف الربح: جني الربح فور وصول الصفقة إلى +$50
STOP_LOSS_PERCENT = -0.10        # وقف الخسارة: إغلاق الصفقة فوراً إذا هبطت -10%
CHECK_INTERVAL_SECONDS = 30      # فحص حالة الصفقات كل 30 ثانية

SYMBOLS_UNIVERSE = [
    "BTC/USD", "ETH/USD", "SOL/USD", "AVAX/USD", 
    "LINK/USD", "DOGE/USD", "AAVE/USD", "UNI/USD"
]
BENCHMARK_SYMBOL = "BTC/USD"
MOMENTUM_WINDOW_DAYS = 21
REGIME_SMA_WINDOW = 200

# ------------------------------------------------------------------------------
# 4. دوال سحب البيانات وفحص الزخم والسوق
# ------------------------------------------------------------------------------
def fetch_daily_closes(symbols, days=250):
    start_time = datetime.utcnow() - timedelta(days=days)
    request_params = CryptoBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start_time
    )
    bars = crypto_data_client.get_crypto_bars(request_params)
    df = bars.df.reset_index()
    pivoted = df.pivot(index='timestamp', columns='symbol', values='close')
    return pivoted.dropna(how='all')

def check_market_regime(prices_df):
    btc_series = prices_df[BENCHMARK_SYMBOL].dropna()
    if len(btc_series) < REGIME_SMA_WINDOW:
        return True
    sma200 = btc_series.rolling(window=REGIME_SMA_WINDOW).mean().iloc[-1]
    current_btc = btc_series.iloc[-1]
    return current_btc > sma200

def get_top_momentum_symbols(prices_df):
    ret_21d = (prices_df.iloc[-1] / prices_df.iloc[-MOMENTUM_WINDOW_DAYS]) - 1.0
    altcoins = [s for s in prices_df.columns if s != BENCHMARK_SYMBOL]
    ranked = ret_21d[altcoins].sort_values(ascending=False)
    return ranked

# ------------------------------------------------------------------------------
# 5. دوال متابعة الصفقات وجني الأرباح واقتناص الفرص
# ------------------------------------------------------------------------------
def monitor_and_manage_positions():
    positions = trading_client.get_all_positions()
    total_invested = 0.0
    active_symbols = []
    
    if not positions:
        print("  [المراكز الحالية]: لا توجد صفقات مفتوحة حالياً.", flush=True)
        return 0.0, []
        
    print("\n  [متابعة الصفقات المفتوحة]:", flush=True)
    print(f"  {'الرمز':<10} | {'القيمة':<10} | {'الدخول':<10} | {'الحالي':<10} | {'الربح ($)':<12} | {'الربح (%)':<10} | {'الحالة'}", flush=True)
    print("  " + "-" * 80, flush=True)
    
    for p in positions:
        sym = p.symbol
        active_symbols.append(sym)
        market_val = float(p.market_value)
        total_invested += market_val
        entry_price = float(p.avg_entry_price)
        curr_price = float(p.current_price)
        unrealized_pl = float(p.unrealized_pl)
        unrealized_plpc = float(p.unrealized_plpc)
        
        # 1. فحص هدف الربح (+50 دولار)
        if unrealized_pl >= TAKE_PROFIT_DOLLARS:
            status_note = f"🎯 جني ربح (+${unrealized_pl:,.2f}) -> إغلاق المركز"
            print(f"  {sym:<10} | ${market_val:<9.2f} | ${entry_price:<9.2f} | ${curr_price:<9.2f} | +${unrealized_pl:<11.2f} | +{unrealized_plpc*100:<8.2f}% | {status_note}", flush=True)
            try:
                trading_client.close_position(sym)
                total_invested -= market_val
                active_symbols.remove(sym)
                print(f"  ✓ تم جني الأرباح بنجاح لصفقة {sym}.", flush=True)
            except Exception as e:
                print(f"  ! خطأ في إغلاق الصفقة {sym}: {e}", flush=True)
            continue
            
        # 2. فحص وقف الخسارة (-10%)
        elif unrealized_plpc <= STOP_LOSS_PERCENT:
            status_note = f"🛑 وقف خسارة ({unrealized_plpc*100:.1f}%) -> إغلاق لحماية رأس المال"
            print(f"  {sym:<10} | ${market_val:<9.2f} | ${entry_price:<9.2f} | ${curr_price:<9.2f} | -${abs(unrealized_pl):<11.2f} | {unrealized_plpc*100:<8.2f}% | {status_note}", flush=True)
            try:
                trading_client.close_position(sym)
                total_invested -= market_val
                active_symbols.remove(sym)
                print(f"  ✓ تم تفعيل وقف الخسارة لصفقة {sym}.", flush=True)
            except Exception as e:
                print(f"  ! خطأ في إغلاق الصفقة {sym}: {e}", flush=True)
            continue
            
        else:
            print(f"  {sym:<10} | ${market_val:<9.2f} | ${entry_price:<9.2f} | ${curr_price:<9.2f} | {unrealized_pl:+,.2f}${'':<6} | {unrealized_plpc*100:+,.2f}%{'':<3} | قيد المراقبة", flush=True)
            
    return total_invested, active_symbols

def search_and_enter_new_trades(total_invested, active_symbols, prices_df):
    remaining_budget = MAX_TOTAL_INVESTMENT - total_invested
    
    if remaining_budget < POSITION_SIZE * 0.9 or len(active_symbols) >= MAX_ACTIVE_POSITIONS:
        return
        
    is_bull = check_market_regime(prices_df)
    if not is_bull:
        print("  [تنبيه السوق]: البيتكوين تحت متوسط 200 يوم. لن يتم فتح صفقات جديدة حتى يستقر السوق.", flush=True)
        return
        
    ranked_momentum = get_top_momentum_symbols(prices_df)
    
    for symbol_slash, mom_val in ranked_momentum.items():
        alpaca_sym = symbol_slash.replace("/", "")
        if alpaca_sym in active_symbols:
            continue
            
        trade_amount = round(min(POSITION_SIZE, remaining_budget), 2)
        if trade_amount < 500:
            break
            
        print(f"\n  ⚡ [فرصة جديدة]: رصد زخم في {alpaca_sym} (زخم: {mom_val*100:+.2f}%)", flush=True)
        print(f"  -> إرسال أمر شراء فوري بقيمة ${trade_amount:,.2f}...", flush=True)
        
        try:
            order = MarketOrderRequest(
                symbol=alpaca_sym,
                notional=trade_amount,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC
            )
            trading_client.submit_order(order)
            print(f"  ✓ تم تنفيذ أمر الشراء بنجاح لـ {alpaca_sym}.", flush=True)
            active_symbols.append(alpaca_sym)
            total_invested += trade_amount
            remaining_budget -= trade_amount
            time.sleep(2)
        except Exception as e:
            print(f"  ! تعذر فتح صفقة {alpaca_sym}: {e}", flush=True)
            
        if len(active_symbols) >= MAX_ACTIVE_POSITIONS or remaining_budget < 500:
            break

# ------------------------------------------------------------------------------
# 6. الخيط المستقل لتشغيل حلقة التداول في الخلفية (Background Thread)
# ------------------------------------------------------------------------------
def run_trading_worker():
    print("[Worker] بدء تشغيل محرك التداول الآلي في الخلفية...", flush=True)
    cycle = 0
    cached_prices = None
    last_fetch = 0
    
    while True:
        cycle += 1
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"\n[{now_str}] --- الدورة رقم #{cycle} ---", flush=True)
        
        try:
            if time.time() - last_fetch > 1800 or cached_prices is None:
                print("  [تحديث البيانات]: جلب أحدث أسعار الإغلاق ومؤشرات الزخم...", flush=True)
                cached_prices = fetch_daily_closes(list(set(SYMBOLS_UNIVERSE + [BENCHMARK_SYMBOL])), days=250)
                last_fetch = time.time()
                
            total_inv, active_syms = monitor_and_manage_positions()
            search_and_enter_new_trades(total_inv, active_syms, cached_prices)
            
            # تحديث لوحة حالة الويب
            bot_status["status"] = "Active & Running (24/7)"
            bot_status["last_cycle"] = now_str
            bot_status["regime"] = "Bull (Trading Allowed)" if check_market_regime(cached_prices) else "Bear (Capital Protected)"
            bot_status["total_invested"] = total_inv
            bot_status["active_positions_count"] = len(active_syms)
            bot_status["message"] = f"Monitoring {len(active_syms)} positions. Next check in 30s."
            
        except Exception as e:
            print(f"  ! تنبيه أثناء الدورة: {e}", flush=True)
            bot_status["message"] = f"Warning: {e}"
            
        time.sleep(CHECK_INTERVAL_SECONDS)

# ------------------------------------------------------------------------------
# نقطة الانطلاق الرئيسية
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    if not API_KEY or not SECRET_KEY:
        print("[HALT] يرجى تعيين ALPACA_KEY و ALPACA_SECRET في إعدادات Render!", flush=True)
    else:
        # تشغيل محرك التداول في خيط منفصل بالخلفية
        worker_thread = threading.Thread(target=run_trading_worker, daemon=True)
        worker_thread.start()
        
    # تشغيل خادم الويب على المنفذ المحدد من قِبل Render (افتراضياً 10000)
    port = int(os.environ.get("PORT", 10000))
    print(f"[Web Server] خادم الويب يعمل على المنفذ {port}...", flush=True)
    app.run(host="0.0.0.0", port=port)