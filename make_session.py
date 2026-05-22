from pyrogram import Client

API_ID = int(input("API_ID: ").strip())
API_HASH = input("API_HASH: ").strip()

with Client("create_session", api_id=API_ID, api_hash=API_HASH) as app:
    print("\nSTRING_SESSION:\n")
    print(app.export_session_string())
