from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage 
import os
from dotenv import load_dotenv
import openai
from openai import OpenAI
import time
import requests

# Set up Flask app
app = Flask(__name__)

# โหลด environment variables
load_dotenv()

# LINE Messaging API credentials
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# OpenAI API Key
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)

# Create an Assistant
assistant = client.beta.assistants.create(
    name="Rules Explainer",
    instructions="คุณตอบคำถามโดยใช้ข้อมูลความรู้อ้างอิงระเบียบ, วิธีปฏิบัติ, คู่มือที่อยู่ใน PDF file เท่านั้น",
    model="gpt-4o-mini",
    tools=[{"type": "file_search"}],
)
print(f'Assistant Id: {assistant.id}')

# Vector store Id
vector_store_id = os.getenv("VECTOR_STORE_ID")

# Create a vector store
# vector_store = client.beta.vector_stores.create(name="PEA Rules")
# print(f'Vector Store Id: {vector_store.id}')

# Ready the files for upload to OpenAI
# file_paths = [r"D:\Coding\Chatbot_python\files\ระเบียบ กฟภ. ว่าด้วยวิธีปฏิบัติเกี่ยวกับมิเตอร์ พ.ศ. 2562.pdf", 
#               r"D:\Coding\Chatbot_python\files\ระเบียบการไฟฟ้าส่วนภูมิภาค ว่าด้วยการใช้ไฟฟ้าและบริการ พ.ศ. 2562.pdf",
#               r"D:\Coding\Chatbot_python\files\พรบ_จัดซื้อจัดจ้างและบริหารพัสดุภาครัฐ_2560.pdf",
#               r"D:\Coding\Chatbot_python\files\วิธีปฏิบัติเกี่ยวกับ emeter 2564.pdf",
#               r"D:\Coding\Chatbot_python\files\ประกาศ อัตราค่าไฟฟ้า มกราคม 2566.pdf"
#              ]
# file_streams = [open(path, "rb") for path in file_paths]

# Use the upload and poll SDK helper to upload the files, add them to the vector store,
# and poll the status of the file batch for completion.
# file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
#   vector_store_id=vector_store.id, files=file_streams
# )
# check status of file and counts of the batch
# print(f'file status: {file_batch.status}')
# print(f'file count: {file_batch.file_counts}')

# Update the assistant to use the new Vector Store
assistant = client.beta.assistants.update(
  assistant_id=assistant.id,
  tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}},
)
print('Assistant update with vector store!')

# Create a Thread
thread = client.beta.threads.create()
print(f'Your thread id is - {thread.id}\n\n')

# Loading Animation
def loading(user_id):
    url = "https://api.line.me/v2/bot/chat/loading/start"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}"
    }
    data = {
        "chatId": user_id
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200 or 201:
        print("Loading animation started successfully.")
    else:
        print(f"Failed to start loading animation: {response.status_code}, {response.text}")

@app.route("/callback", methods=["POST"])
def callback():

    bodys = request.get_json()
    events = bodys.get("events", [])
    for event in events:
        user_id = event.get("source", {}).get("userId")  # ดึง userId จาก event
        if user_id:
            loading(user_id)
        
    # Get X-Line-Signature header
    signature = request.headers["X-Line-Signature"]

    # Get request body as text
    body = request.get_data(as_text=True)

    # Handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return jsonify({"status": "ok"}), 200
    # return "OK"

# Handle message events
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    user_message = event.message.text  # รับ prompt จาก user

    try:
        # Use OpenAI API to generate a response
        # Add a Message to the Thread
        message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_message,
        )

        # create run and poll the status of
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id, assistant_id=assistant.id
        )
        # display responses from assistant
        messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))    
        ai_reply = messages[0].content[0].text.value
        print('Response: \n')
        print(f'{ai_reply}\n')
        print(f'Your thread id is: {thread.id}')
        print(f'Assistant Id: {assistant.id}')
        print(f'Vector Store Id: {vector_store_id}\n\n')

        # response = client.chat.completions.create(
        #     messages=[
        #         {
        #             "role": "user",
        #             "content": user_message,
        #         }
        #     ],
        #     model="gpt-4o-mini",
        # )
        # ai_reply = response.choices[0].message.content
    except Exception as e:
        ai_reply = f"Error: {str(e)}"

    # Reply to the user
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=ai_reply)
        )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

