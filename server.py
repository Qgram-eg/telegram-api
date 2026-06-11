from telethon import TelegramClient
from flask import Flask, request, jsonify
import asyncio
import os

app = Flask(__name__)

clients = {}

@app.route('/')
def home():
    return "Telegram API Server is running!"

@app.route('/login')
def login():
    phone = request.args.get('phone')
    api_id = int(request.args.get('api_id'))
    api_hash = request.args.get('api_hash')
    
    async def start():
        client = TelegramClient(f'session_{phone}', api_id, api_hash)
        await client.connect()
        result = await client.send_code_request(phone)
        clients[phone] = {
            'client': client,
            'phone_code_hash': result.phone_code_hash
        }
        return result.phone_code_hash
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    phone_code_hash = loop.run_until_complete(start())
    return jsonify({'status': 'code_sent', 'hash': phone_code_hash})

@app.route('/verify')
def verify():
    phone = request.args.get('phone')
    code = request.args.get('code')
    
    async def verify_code():
        data = clients[phone]
        client = data['client']
        await client.sign_in(phone=phone, code=code, phone_code_hash=data['phone_code_hash'])
        me = await client.get_me()
        return f"{me.first_name} {me.last_name or ''}"
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    name = loop.run_until_complete(verify_code())
    return jsonify({'status': 'logged_in', 'name': name})

@app.route('/change_name')
def change_name():
    phone = request.args.get('phone')
    name = request.args.get('name')
    
    async def update():
        client = clients[phone]['client']
        await client.update_profile(first_name=name)
        return 'Done'
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(update())
    return jsonify({'status': 'name_changed', 'new_name': name})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
