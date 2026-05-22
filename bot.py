import asyncio
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pytgcalls import PyTgCalls

from config import BOT_TOKEN, API_ID, API_HASH, STRING_SESSION, OWNER_IDS, DEFAULT_VOLUME

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

assistant = Client(
    "assistant_session",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION,
)

calls = PyTgCalls(assistant)

@dataclass
class Track:
    title: str
    path: str
    requested_by: str

queues: Dict[int, List[Track]] = {}
current: Dict[int, Optional[Track]] = {}
loop_mode: Dict[int, bool] = {}


def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def clean_old_files(max_age_seconds: int = 6 * 60 * 60):
    now = time.time()
    for name in os.listdir(DOWNLOAD_DIR):
        path = os.path.join(DOWNLOAD_DIR, name)
        try:
            if os.path.isfile(path) and now - os.path.getmtime(path) > max_age_seconds:
                os.remove(path)
        except Exception:
            pass


async def reply_safe(message: Message, text: str):
    try:
        await message.reply_text(text, disable_web_page_preview=True)
    except Exception:
        pass


async def download_audio(query: str) -> Track:
    clean_old_files()
    ts = int(time.time())
    out_template = os.path.join(DOWNLOAD_DIR, f"%(title).60s_{ts}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--socket-timeout", "20",
        "--retries", "3",
        "--fragment-retries", "3",
        "-o", out_template,
        query if query.startswith("http") else f"ytsearch1:{query}",
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err = stderr.decode(errors="ignore")[-500:]
        raise RuntimeError(f"İndirme hatası: {err}")

    files = [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR)]
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        raise RuntimeError("Dosya indirilemedi.")

    latest = max(files, key=os.path.getmtime)
    title = os.path.basename(latest).rsplit("_", 1)[0]
    return Track(title=title, path=latest, requested_by="")


async def ensure_assistant_in_chat(chat_id: int):
    # Asistan hesabı grupta değilse Telegram izin vermez.
    # Bu fonksiyon sadece basit kontrol yapar.
    try:
        await assistant.get_chat(chat_id)
        return True
    except Exception:
        return False


async def play_track(chat_id: int, track: Track):
    current[chat_id] = track
    # PyTgCalls 2.x doğrudan dosya yolu/URL oynatabilir.
    await calls.play(chat_id, track.path)
    try:
        await calls.change_volume_call(chat_id, DEFAULT_VOLUME)
    except Exception:
        pass


async def play_next(chat_id: int):
    if loop_mode.get(chat_id) and current.get(chat_id):
        await play_track(chat_id, current[chat_id])
        return

    q = queues.get(chat_id, [])
    if not q:
        current[chat_id] = None
        try:
            await calls.leave_call(chat_id)
        except Exception:
            pass
        return

    nxt = q.pop(0)
    await play_track(chat_id, nxt)


@bot.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    await reply_safe(message,
        "🎧 Müzik bot aktif.\n\n"
        "Komutlar:\n"
        "/play şarkı adı veya YouTube linki\n"
        "/pause - duraklat\n"
        "/resume - devam\n"
        "/skip - sıradaki\n"
        "/stop - kapat\n"
        "/queue - sıra\n"
        "/volume 1-200\n"
        "/loop - tekrar aç/kapat\n\n"
        "Not: Asistan hesabı grupta olmalı ve sesli sohbet açık olmalı."
    )


@bot.on_message(filters.command("play"))
async def play_cmd(_, message: Message):
    if not message.from_user or not is_owner(message.from_user.id):
        return await reply_safe(message, "Bu komut sadece bot sahibi içindir.")

    if len(message.command) < 2:
        return await reply_safe(message, "Kullanım: /play şarkı adı veya YouTube linki")

    if not check_ffmpeg():
        return await reply_safe(message, "Sunucuda ffmpeg yok. Önce ffmpeg kurmalısın.")

    chat_id = message.chat.id
    query = message.text.split(maxsplit=1)[1]

    ok = await ensure_assistant_in_chat(chat_id)
    if not ok:
        return await reply_safe(message, "Asistan hesabı bu grupta değil. Önce asistan hesabını gruba ekle.")

    msg = await message.reply_text("🔎 Şarkı aranıyor/indiriliyor...")
    try:
        track = await download_audio(query)
        track.requested_by = message.from_user.first_name or str(message.from_user.id)
    except Exception as e:
        return await msg.edit_text(f"❌ Hata: {e}")

    if current.get(chat_id):
        queues.setdefault(chat_id, []).append(track)
        await msg.edit_text(f"➕ Sıraya eklendi:\n{track.title}")
    else:
        try:
            await play_track(chat_id, track)
            await msg.edit_text(f"▶️ Çalıyor:\n{track.title}")
        except Exception as e:
            await msg.edit_text(
                "❌ Sese girilemedi.\n"
                "Sesli sohbet açık mı? Asistan hesap grupta mı? Yetki var mı?\n\n"
                f"Hata: {e}"
            )


@bot.on_message(filters.command("pause"))
async def pause_cmd(_, message: Message):
    if not message.from_user or not is_owner(message.from_user.id):
        return
    try:
        await calls.pause_stream(message.chat.id)
        await reply_safe(message, "⏸ Duraklatıldı.")
    except Exception as e:
        await reply_safe(message, f"Hata: {e}")


@bot.on_message(filters.command("resume"))
async def resume_cmd(_, message: Message):
    if not message.from_user or not is_owner(message.from_user.id):
        return
    try:
        await calls.resume_stream(message.chat.id)
        await reply_safe(message, "▶️ Devam ediyor.")
    except Exception as e:
        await reply_safe(message, f"Hata: {e}")


@bot.on_message(filters.command("skip"))
async def skip_cmd(_, message: Message):
    if not message.from_user or not is_owner(message.from_user.id):
        return
    try:
        await play_next(message.chat.id)
        if current.get(message.chat.id):
            await reply_safe(message, f"⏭ Geçildi. Şimdi:\n{current[message.chat.id].title}")
        else:
            await reply_safe(message, "Sıra bitti, sesten çıkıldı.")
    except Exception as e:
        await reply_safe(message, f"Hata: {e}")


@bot.on_message(filters.command("stop"))
async def stop_cmd(_, message: Message):
    if not message.from_user or not is_owner(message.from_user.id):
        return
    chat_id = message.chat.id
    queues[chat_id] = []
    current[chat_id] = None
    try:
        await calls.leave_call(chat_id)
    except Exception:
        pass
    await reply_safe(message, "⏹ Müzik kapatıldı, sıra temizlendi.")


@bot.on_message(filters.command("queue"))
async def queue_cmd(_, message: Message):
    chat_id = message.chat.id
    q = queues.get(chat_id, [])
    now = current.get(chat_id)
    text = "🎶 Şu an: " + (now.title if now else "Yok") + "\n\n"
    if not q:
        text += "Sıra boş."
    else:
        text += "📜 Sıra:\n" + "\n".join([f"{i+1}. {t.title}" for i, t in enumerate(q[:15])])
    await reply_safe(message, text)


@bot.on_message(filters.command("volume"))
async def volume_cmd(_, message: Message):
    if not message.from_user or not is_owner(message.from_user.id):
        return
    if len(message.command) < 2:
        return await reply_safe(message, "Kullanım: /volume 1-200")
    try:
        vol = max(1, min(200, int(message.command[1])))
        await calls.change_volume_call(message.chat.id, vol)
        await reply_safe(message, f"🔊 Ses seviyesi: {vol}")
    except Exception as e:
        await reply_safe(message, f"Hata: {e}")


@bot.on_message(filters.command("loop"))
async def loop_cmd(_, message: Message):
    if not message.from_user or not is_owner(message.from_user.id):
        return
    chat_id = message.chat.id
    loop_mode[chat_id] = not loop_mode.get(chat_id, False)
    await reply_safe(message, "🔁 Loop: " + ("Açık" if loop_mode[chat_id] else "Kapalı"))


async def main():
    if not BOT_TOKEN or "BURAYA" in BOT_TOKEN:
        raise SystemExit("config.py içinde BOT_TOKEN doldurulmamış.")
    if not API_ID or "BURAYA" in API_HASH or "BURAYA" in STRING_SESSION:
        raise SystemExit("config.py içinde API_ID, API_HASH, STRING_SESSION doldurulmalı.")

    print("Asistan başlatılıyor...")
    await assistant.start()
    print("Ses sistemi başlatılıyor...")
    await calls.start()
    print("Bot başlatılıyor...")
    await bot.start()
    print("Müzik bot aktif.")
    await idle()
    await bot.stop()
    await calls.stop()
    await assistant.stop()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
