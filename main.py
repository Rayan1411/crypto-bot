# ==============================================================================
# CRYPTO TRADING BOT: 24/7 ADVANCED WEB DASHBOARD EDITION
# Platform: Render.com (Free Web Service Tier)
# Integration: Alpaca Crypto API + Rich Real-Time Web Dashboard
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
# 1. إعداد خادم الويب (Flask Server) مع لوحة تحكم تفصيلية وتحديث تلقائي
# ------------------------------------------------------------------------------
app = Flask(__name__)

# متغيرات عامة لعرض كافة تفاصيل الصفقات المفتوحة مباشرة عبر المتصفح
bot_status = {
    "status": "Starting",
    "last_cycle": "None",
    "regime": "Checking...",
    "btc_price": 0.0,
    "btc_sma200": 0.0,
    "total_invested": 0.0,
    "active_positions_count": 0,
    "message": "Initializing trading bot...",
    "positions_list": []  # تفاصيل كل صفقة مفتوحة
}

@app.route('/')
def home():
    """
    لوحة تحكم تفاعلية متكاملة تعرض أسعار العملات وتفاصيل الأرباح وتتحدث تلقائياً
    """
    # بناء صفوف جدول الصفقات المفتوحة
    rows_html = ""
    if bot_status["positions_list"]:
        for pos in bot_status["positions_list"]:
            pnl_val = pos["unrealized_pl"]
            pnl_pct = pos["unrealized_plpc"] * 100
            
            # تلوين الأرباح بالأخضر والخسائر بالأحمر
            color = "#10b981" if pnl_val >= 0 else "#ef4444"
            sign = "+" if pnl_val >= 0 else ""
            
            # حساب المتبقي على هدف الربح (50$)
            target_diff = 50.0 - pnl_val
            target_str = f"حققت الهدف!" if target_diff <= 0 else f"متبقي ${target_diff:.2f}"
            
            rows_html += f"""
            <tr style="border-bottom: 1px solid #334155;">
                <td style="padding: 12px; font-weight: bold; color: #38bdf8;">{pos['symbol']}</td>
                <td style="padding: 12px;">${pos['market_value']:,.2f}</td>
                <td style="padding: 12px;">${pos['entry_price']:,.4f}</td>
                <td style="padding: 12px;">${pos['current_price']:,.4f}</td>
                <td style="padding: 12px; color: {color}; font-weight: bold;">{sign}${pnl_val:,.2f}</td>
                <td style="padding: 12px; color: {color}; font-weight: bold;">{sign}{pnl_pct:.2f}%</td>
                <td style="padding: 12px; font-size: 13px; color: #94a3b8;">{target_str}</td>
            </tr>
            """
    else:
        rows_html = """
        <tr>
            <td colspan="7" style="padding: 20px; text-align: center; color: #94a3b8;">
                لا توجد صفقات مفتوحة حالياً (رأس المال متوفر في وضع النقد / Cash).
            </td>
        </tr>
        """

    remaining_cap = max(0.0, 10000.0 - bot_status['total_invested'])

    return f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <!-- تحديث تلقائي للصفحة كل 15 ثانية لمتابعة الأرباح لحظة بلحظة -->
        <meta http-equiv="refresh" content="15">
        <title>لوحة تداول العملات الرقمية الحية</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background-color: #0b1120;
                color: #f1f5f9;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 1000px;
                margin: auto;
            }}
            .card {{
                background-color: #1e293b;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
                border: 1px solid #334155;
            }}
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                border-bottom: 1px solid #334155;
                padding-bottom: 15px;
                margin-bottom: 15px;
            }}
            .badge-live {{
                background-color: #065f46;
                color: #34d399;
                padding: 6px 14px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: bold;
                display: inline-flex;
                align-items: center;
                gap: 6px;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }}
            .stat-box {{
                background-color: #0f172a;
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #334155;
            }}
            .stat-title {{
                color: #94a3b8;
                font-size: 13px;
                margin-bottom: 5px;
            }}
            .stat-value {{
                font-size: 20px;
                font-weight: bold;
                color: #f8fafc;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                text-align: right;
            }}
            th {{
                background-color: #0f172a;
                padding: 12px;
                color: #94a3b8;
                font-size: 13px;
            }}
            .pulse {{
                width: 8px;
                height: 8px;
                background-color: #34d399;
                border-radius: 50%;
                display: inline-block;
                box-shadow: 0 0 8px #34d399;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="header">
                    <div>
                        <h2 style="margin: 0; color: #38bdf8;">⚡ لوحة تحكم بوت الكريبتو (24/7 مباشر)</h2>
                        <span style="font-size: 13px; color: #94a3b8;">تحديث حي تلقائي كل 15 ثانية | Alpaca API</span>
                    </div>
                    <div>
                        <span class="badge-live"><span class="pulse"></span> متصل ونشط 24/7</span>
                    </div>
                </div>

                <!-- شبكة الإحصائيات العامة -->
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="stat-title">إجمالي المستثمر حالياً</div>
                        <div class="stat-value" style="color: #38bdf8;">${bot_status['total_invested']:,.2f}</div>
                        <span style="font-size: 12px; color: #94a3b8;">من سقف $10,000.00</span>
                    </div>
                    <div class="stat-box">
                        <div class="stat-title">السيولة النقدية المتبقية</div>
                        <div class="stat-value">${remaining_cap:,.2f}</div>
                        <span style="font-size: 12px; color: #94a3b8;">جاهزة للفرص الجديدة</span>
                    </div>
                    <div class="stat-box">
                        <div class="stat-title">حالة السوق (BTC Regime)</div>
                        <div class="stat-value" style="color: #10b981;">{bot_status['regime']}</div>
                        <span style="font-size: 12px; color: #94a3b8;">BTC: ${bot_status['btc_price']:,.0f} | SMA200: ${bot_status['btc_sma200']:,.0f}</span>
                    </div>
                    <div class="stat-box">
                        <div class="stat-title">الصفقات المفتوحة</div>
                        <div class="stat-value">{bot_status['active_positions_count']} <span style="font-size: 14px; color: #94a3b8;">/ 3 صفقات</span></div>
                        <span style="font-size: 12px; color: #94a3b8;">الهدف: +$50 | الوقف: -10%</span>
                    </div>
                </div>

                <div style="font-size: 13px; color: #94a3b8; margin-bottom: 15px;">
                    <b>آخر فحص للدورة:</b> {bot_status['last_cycle']} | <b>رسالة النظام:</b> {bot_status['message']}
                </div>
            </div>

            <!-- جدول الصفقات المفتوحة بالتفصيل -->
            <div class="card" style="padding: 0; overflow-x: auto;">
                <div style="padding: 18px; border-bottom: 1px solid #334155;">
                    <h3 style="margin: 0; color: #f8fafc;">تفاصيل الصفقات المفتوحة وأرباحها اللحظية</h3>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>العملة</th>
                            <th>قيمة الصفقة</th>
                            <th>سعر الدخول</th>
                            <th>السعر الحالي</th>
                            <th>الربح اللحظي ($)</th>
                            <th>النسبة المئوية (%)</th>
                            <th>الهدف (+50$)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>

            <p style="text-align: center; color: #64748b; font-size: 12px;">
                النظام يعمل آلياً بالكامل | يتم جني الأرباح تلقائياً فور بلوغ +$50 وإغلاق الصفقة وتجديد الفرص.
            </p>
        </div>
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
        return True, 0.0, 0.0
    sma200 = btc_series.rolling(window=REGIME_SMA_WINDOW).mean().iloc[-1]
    current_btc = btc_series.iloc[-1]
    return (current_btc > sma200), current_btc, sma200

def get_top_momentum_symbols(prices_df):
    ret_21d = (prices_df.iloc[-1] / prices_df.iloc[-MOMENTUM_WINDOW_DAYS]) - 1.0
    altcoins = [s for s in prices_df.columns if s != BENCHMARK_SYMBOL]
    ranked = ret_21d[altcoins].sort_values(ascending=False)
    return ranked

# ------------------------------------------------------------------------------
# 5. دوال متابعة الصفقات وجني الأرباح وتحديث بيانات لوحة الويب
# ------------------------------------------------------------------------------
def monitor_and_manage_positions():
    positions = trading_client.get_all_positions()
    total_invested = 0.0
    active_symbols = []
    positions_summary_list = []
    
    if not positions:
        print("  [المراكز الحالية]: لا توجد صفقات مفتوحة حالياً.", flush=True)
        bot_status["positions_list"] = []
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
        
        # حفظ تفاصيل المركز لتقديمه في صفحة الويب
        pos_info = {
            "symbol": sym,
            "market_value": market_val,
            "entry_price": entry_price,
            "current_price": curr_price,
            "unrealized_pl": unrealized_pl,
            "unrealized_plpc": unrealized_plpc
        }
        positions_summary_list.append(pos_info)
        
        # 1. فحص هدف الربح (+50 دولار)
        if unrealized_pl >= TAKE_PROFIT_DOLLARS:
            status_note = f"🎯 جني ربح (+${unrealized_pl:,.2f}) -> إغلاق المركز"
            print(f"  {sym:<10} | ${market_val:<9.2f} | ${entry_price:<9.2f} | ${curr_price:<9.2f} | +${unrealized_pl:<11.2f} | +{unrealized_plpc*100:<8.2f}% | {status_note}", flush=True)
            try:
                trading_client.close_position(sym)
                total_invested -= market_val
                active_symbols.remove(sym)
                positions_summary_list.remove(pos_info)
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
                positions_summary_list.remove(pos_info)
                print(f"  ✓ تم تفعيل وقف الخسارة لصفقة {sym}.", flush=True)
            except Exception as e:
                print(f"  ! خطأ في إغلاق الصفقة {sym}: {e}", flush=True)
            continue
            
        else:
            print(f"  {sym:<10} | ${market_val:<9.2f} | ${entry_price:<9.2f} | ${curr_price:<9.2f} | {unrealized_pl:+,.2f}${'':<6} | {unrealized_plpc*100:+,.2f}%{'':<3} | قيد المراقبة", flush=True)
            
    # تحديث القائمة في لوحة الويب
    bot_status["positions_list"] = positions_summary_list
    return total_invested, active_symbols

def search_and_enter_new_trades(total_invested, active_symbols, prices_df):
    remaining_budget = MAX_TOTAL_INVESTMENT - total_invested
    
    if remaining_budget < POSITION_SIZE * 0.9 or len(active_symbols) >= MAX_ACTIVE_POSITIONS:
        return
        
    is_bull, btc_cur, btc_sma = check_market_regime(prices_df)
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
# 6. الخيط المستقل لتشغيل حلقة التداول في الخلفية
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
                
            is_bull, btc_cur, btc_sma = check_market_regime(cached_prices)
            total_inv, active_syms = monitor_and_manage_positions()
            search_and_enter_new_trades(total_inv, active_syms, cached_prices)
            
            # تحديث لوحة حالة الويب
            bot_status["status"] = "Active & Trading (24/7)"
            bot_status["last_cycle"] = now_str
            bot_status["regime"] = "Bull (سوق صاعد - الشراء مسموح)" if is_bull else "Bear (سوق هابط - حماية رأس المال)"
            bot_status["btc_price"] = btc_cur
            bot_status["btc_sma200"] = btc_sma
            bot_status["total_invested"] = total_inv
            bot_status["active_positions_count"] = len(active_syms)
            bot_status["message"] = f"مراقبة {len(active_syms)} صفقات. الفحص القادم بعد 30 ثانية."
            
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
        worker_thread = threading.Thread(target=run_trading_worker, daemon=True)
        worker_thread.start()
        
    port = int(os.environ.get("PORT", 10000))
    print(f"[Web Server] خادم الويب يعمل على المنفذ {port}...", flush=True)
    app.run(host="0.0.0.0", port=port)
