from flask import Flask, request, jsonify
from pyrogram import Client, filters
from pyrogram.errors import PhoneCodeInvalid, PhoneCodeExpired
import asyncio
import threading
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "Telegram Userbot Bridge is Running 🟢"})

@app.route('/send_code', methods=['POST'])
def send_code():
    data = request.get_json() or {}
    api_id_str = data.get('api_id')
    api_hash = data.get('api_hash')
    phone = data.get('phone')
    
    if not api_id_str or not api_hash or not phone:
        return jsonify({"status": "error", "message": "يجب إدخال API ID و API Hash ورقم الهاتف"})
    
    try:
        api_id = int(str(api_id_str).strip())
    except ValueError:
        return jsonify({"status": "error", "message": "API ID يجب أن يكون رقماً صحيحاً"})
    
    async def run_pyrogram():
        client = Client(f"temp_{phone}", api_id=api_id, api_hash=str(api_hash).strip(), in_memory=True)
        await client.connect()
        sent_code = await client.send_code(str(phone).strip())
        code_hash = sent_code.phone_code_hash
        temp_session = await client.export_session_string()
        await client.disconnect()
        return code_hash, temp_session

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        code_hash, temp_session = loop.run_until_complete(run_pyrogram())
        return jsonify({
            "status": "success", 
            "hash": code_hash, 
            "temp_session": temp_session,
            "message": "تم إرسال الكود بنجاح"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/verify_code', methods=['POST'])
def verify_code():
    data = request.get_json() or {}
    phone = data.get('phone')
    code = data.get('code')
    code_hash = data.get('hash')
    api_id_str = data.get('api_id')
    api_hash = data.get('api_hash')
    temp_session = data.get('temp_session')
    
    if not phone or not code or not code_hash or not api_id_str or not api_hash or not temp_session:
        return jsonify({"status": "error", "message": "بيانات غير مكتملة، يرجى إعادة إرسال الكود"})

    try:
        api_id = int(str(api_id_str).strip())
    except ValueError:
        return jsonify({"status": "error", "message": "API ID يجب أن يكون رقماً صحيحاً"})

    async def run_verify():
        client = Client("verify_client", session_string=str(temp_session).strip(), api_id=api_id, api_hash=str(api_hash).strip())
        await client.connect()
        
        try:
            await client.sign_in(str(phone).strip(), str(code_hash).strip(), str(code).strip())
        except PhoneCodeInvalid:
            await client.disconnect()
            raise Exception("كود التحقق غير صحيح، تأكد من الرقم ورمز التحقق.")
        except PhoneCodeExpired:
            await client.disconnect()
            raise Exception("انتهت صلاحية الكود، يرجى طلب كود جديد.")
        except Exception as sign_in_err:
            try:
                await client.disconnect()
            except:
                pass
            raise Exception(f"خطأ تيليجرام: {str(sign_in_err)}")
        
        session_string = await client.export_session_string()
        await client.disconnect()
        
        start_persistent_bot(session_string, api_id, str(api_hash).strip())
        return session_string

    try:
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
                    "persistent_userbot", 
                    api_id=api_id, 
                    api_hash=api_hash, 
                    session_string=session_string,
                    in_memory=True
                )
                
                @bot_client.on_message(filters.me & filters.command(["source", "شورس"], prefixes="."))
                async def source_command(c, message):
                    await message.edit(
                        "🤖 **معلومات السورس (Telegram API Bridge):**\n"
                        "━━━━━━━━━━━━━━━\n"
                        "• **الحالة:** متصل ويعمل في الخلفية 🟢\n"
                        "• **المطور:** Youssef"
                    )

                @bot_client.on_message(filters.me & filters.command(["ping", "بينق"], prefixes="."))
                async def ping_command(c, message):
                    await message.edit("🏓 **Pong!** السيرفر شغال وسريع ⚡")

                await bot_client.start()
                print("✅ Userbot connected and listening successfully!")
                await asyncio.get_event_loop().create_future()
            except Exception as e:
                print(f"❌ Background Bot Error: {str(e)}")

        loop.run_until_complete(main())

    t = threading.Thread(target=run_bot_thread, daemon=True)
    t.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
