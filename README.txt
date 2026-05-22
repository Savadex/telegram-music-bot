TELEGRAM SESLİ SOHBET MÜZİK BOTU

ÖNEMLİ:
- Telegram bot tokeni tek başına sesli sohbete giremez.
- Seste müzik için bir asistan Telegram hesabı gerekir.
- API_ID ve API_HASH my.telegram.org adresinden alınır.
- STRING_SESSION için make_session.py çalıştırılır.
- Sunucuda ffmpeg kurulu olmalıdır.
- PythonAnywhere free genelde sesli müzik botu için uygun değildir. FPS.ms/VPS daha iyi.

KURULUM:
1) Zipi sunucuya yükle ve çıkar.
2) config.py dosyasını aç, BOT_TOKEN, API_ID, API_HASH, STRING_SESSION ve OWNER_IDS doldur.
3) Kur:
   pip3 install --user -r requirements.txt

FFMPEG:
- VPS Ubuntu:
   sudo apt update && sudo apt install -y ffmpeg
- FPS.ms panelinde paket yoksa ffmpeg destekli imaj kullan.

STRING_SESSION ALMA:
   python3 make_session.py
Telefon kodunu gir, çıkan uzun yazıyı config.py içindeki STRING_SESSION alanına koy.

ÇALIŞTIRMA:
   python3 bot.py

KOMUTLAR:
/play şarkı adı veya YouTube linki
/pause
/resume
/skip
/stop
/queue
/volume 1-200
/loop

GRUPTA YAPILACAKLAR:
- Botu gruba ekle.
- Asistan hesabı da gruba ekli olsun.
- Grupta sesli sohbeti başlat.
- /play şarkı adı yaz.
