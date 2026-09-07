from flask import Flask, request, jsonify
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
import asyncio
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "Telegram API Bridge with Commands is Working!"})

# تخزين الجلسات النشطة مؤقتاً
active_clients = {}

@app.route('/send_code', methods=['POST'])
def send_code():
    data = request.get_json() or {}
    api_id_str = data.get('api_id')
    api_hash = data.get('api_hash')
    phone = data.get('phone')
    
    if not api_id_str or not api_hash or not phone:
        return jsonify({"status": "error", "message": "يجب إدخال API ID و API Hash ورقم الهاتف"})
    
    try:
        api_id = int(api_id_str)
    except ValueError:
        return jsonify({"status": "error", "message": "API ID يجب أن يكون رقماً صحيحاً"})
    
    async def run_pyrogram():
        client = Client(f"session_{phone}", api_id=api_id, api_hash=api_hash, in_memory=True)
        await client.connect()
        sent_code = await client.send_code(phone)
        
        active_clients[phone] = {
            "client": client,
            "hash": sent_code.phone_code_hash
        }
        return sent_code.phone_code_hash

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        code_hash = loop.run_until_complete(run_pyrogram())
        return jsonify({"status": "success", "hash": code_hash, "message": "تم إرسال الكود بنجاح"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/verify_code', methods=['POST'])
def verify_code():
    data = request.get_json() or {}
    phone = data.get('phone')
    code = data.get('code')
    
    if not phone or not code:
        return jsonify({"status": "error", "message": "بيانات غير مكتملة"})

    async def run_verify():
        session_data = active_clients.get(phone)
        if not session_data:
            raise Exception("انتهت الجلسة أو لم تقم بإرسال الكود أولاً")
        
        client = session_data["client"]
        phone_code_hash = session_data["hash"]
        
        await client.sign_in(phone, phone_code_hash, code)
        
        # --- إضافة الأوامر التفاعلية (يعمل عند إرسالها من حسابك الشخصي) ---
        
        @client.on_message(filters.me & filters.command(["source", "شورس"], prefixes="."))
        async def source_command(c, message):
            await message.edit(
                "🤖 **معلومات السورس (Telegram API Bridge):**\n"
                "━━━━━━━━━━━━━━━\n"
                "• **الحالة:** يعمل بكفاءة تامة 🟢\n"
                "• **المنصة:** مستضاف على Railway\n"
                "• **المطور:** Youssef\n"
                "• **التقنية:** Python, Flask & Pyrogram"
            )

        @client.on_message(filters.me & filters.command(["ping", "بينق"], prefixes="."))
        async def ping_command(c, message):
            await message.edit("🏓 **Pong!** السيرفر شغال وسريع جداً ⚡")

        return "تم تسجيل الدخول وتفعيل الأوامر (Source & Ping) بنجاح!"

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_verify())
        return jsonify({"status": "success", "message": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
