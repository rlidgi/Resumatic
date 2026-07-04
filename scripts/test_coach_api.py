import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app import app, User, users

client = app.test_client()
uid = "test_user_coach"
users[uid] = User(uid, "Test", "test@example.com", email_verified=True)

with client.session_transaction() as sess:
    sess["_user_id"] = uid
    sess["_fresh"] = True

resp = client.post(
    "/api/ai/job-search-coach",
    json={"messages": [{"role": "user", "content": "What should I focus on this week?"}]},
)
print("status", resp.status_code)
print("content-type", resp.content_type)
print(resp.get_data(as_text=True)[:1500])
