from flask import Flask, request, jsonify
from pyrogram import Client, filters
from pyrogram.errors import PhoneCodeInvalid, PhoneCodeExpired, PhoneNumberInvalid, FloodWait
import asyncio
import threading
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "Telegram Userbot Bridge is Running 🟢"})

@app.route('/send_code', methods=['POST'])
def send_code():
    try:
        data = request.get_json(silent=True) or {}
        api_id_val = data.get('api_id')
        api_hash_val = data.get('api_hash')
        phone_val = data.get('phone')
        
        if not api_id_val or not api_hash_val or not phone_val:
            return jsonify({"status": "error", "message": "جميع الحقول (API ID, API Hash, الهاتف) إجبارية."}), 400
        
        try:
            api_id = int(str(api_id_val).strip())
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "API ID يجب أن يكون رقماً صحيحاً تماماً."}), 400
            
        api_hash = str(api_hash_val).strip()
        phone = str(phone_val).strip()
        
        async def run_pyrogram():
            # إنشاء عميل مؤقت في الذاكرة مع معرف فريد لمنع التداخل
            client = Client(f"temp_{phone}_{os.urandom(4).hex()}", api_id=api_id, api_hash=api_hash, in_memory=True)
            await client.connect()
            try:
                sent_code = await client.send_code(phone)
                code_hash = sent_code.phone_code_hash
                # تصدير جلسة الاتصال المؤقتة لضمان تطابق المفتاح عند إدخال الكود
                temp_session = await client.export_session_string()
            finally:
                await client.disconnect()
            return code_hash, temp_session

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        code_hash, temp_session = loop.run_until_complete(run_pyrogram())
        
        return jsonify({
            "status": "success", 
            "hash": code_hash, 
            "temp_session": temp_session,
            "message": "تم إرسال كود التحقق بنجاح إلى تيليجرام."
        })
        
    except FloodWait as e:
        return jsonify({"status": "error", "message": f"حظر مؤقت من تيليجرام. يرجى الانتظار {e.value} ثانية."}), 400
    except PhoneNumberInvalid:
        return jsonify({"status": "error", "message": "رقم الهاتف المدخل غير صحيح أو غير مسجل في تيليجرام."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"خطأ تقني: {str(e)}"}), 400

@app.route('/verify_code', methods=['POST'])
def verify_code():
    try:
        data = request.get_json(silent=True) or {}
        phone_val = data.get('phone')
        code_val = data.get('code')
        code_hash_val = data.get('hash')
        api_id_val = data.get('api_id')
        api_hash_val = data.get('api_hash')
        temp_session_val = data.get('temp_session')
        
        if not phone_val or not code_val or not code_hash_val or not api_id_val or not api_hash_val or not temp_session_val:
            return jsonify({"status": "error", "message": "بيانات غير مكتملة، يرجى إعادة طلب الكود."}), 400

        try:
            api_id = int(str(api_id_val).strip())
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "API ID يجب أن يكون رقماً صحيحاً."}), 400

        phone = str(phone_val).strip()
        code = str(code_val).strip()
        code_hash = str(code_hash_val).strip()
        api_hash = str(api_hash_val).strip()
        temp_session = str(temp_session_val).strip()

        async def run_verify():
            # استخدام نفس الجلسة المؤقتة السابقة لمنع خطأ انتهاء الصلاحية الفوري
            client = Client(f"verify_{phone}_{os.urandom(4).hex()}", api_id=api_id, api_hash=api_hash, session_string=temp_session, in_memory=True)
            await client.connect()
            
            try:
                await client.sign_in(phone, code_hash, code)
            except PhoneCodeInvalid:
                await client.disconnect()
                raise Exception("كود التحقق خاطئ، تأكد من الأرقام المرسلة من تيليجرام.")
            except PhoneCodeExpired:
                await client.disconnect()
                raise Exception("انتهت صلاحية الكود تماماً، يرجى طلب كود جديد.")
            
            session_string = await client.export_session_string()
            await client.disconnect()
            
            # تشغيل البوت الدائم في الخلفية
            start_persistent_bot(session_string, api_id, api_hash)
            return session_string

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        session_string = loop.run_until_complete(run_verify())
        
        return jsonify({
            "status": "success", 
            "session_string": session_string, 
            "message": "تم تسجيل الدخول بنجاح وتفعيل الحساب!"
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

def start_persistent_bot(session_string, api_id, api_hash):
    def run_bot_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def main():
            try:
                bot_client = Client(
                    f"userbot_{os.urandom(4).hex()}", 
                    api_id=api_id, 
                    api_hash=api_hash, 
                    session_string=session_string,
                    in_memory=True
                )
                
                @bot_client.on_message(filters.me & filters.command(["source", "شورس"], prefixes="."))
                async def source_command(c, message):
                    await message.edit("🤖 **Userbot Bridge**\n• الحالة: متصل ويعمل بنجاح 🟢\n• المطور: يوسف")

                @bot_client.on_message(filters.me & filters.command(["ping", "بينق"], prefixes="."))
                async def ping_command(c, message):
                    await message.edit("🏓 **Pong!** السيرفر متصل وسريع وسجّل الدخول بنجاح ⚡")

                await bot_client.start()
                await asyncio.get_event_loop().create_future()
            except Exception as e:
                print(f"Background Bot Error: {str(e)}")

        loop.run_until_complete(main())

    t = threading.Thread(target=run_bot_thread, daemon=True)
    t.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
