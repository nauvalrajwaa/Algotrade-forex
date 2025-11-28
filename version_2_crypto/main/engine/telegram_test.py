# main/engine/telegram_test.py

import sys
import os

# --- FIX PATH: Agar bisa baca config.py di folder luar ---
# Ambil lokasi file ini berada
current_dir = os.path.dirname(os.path.abspath(__file__))
# Naik 2 level ke atas (dari main/engine -> ke root folder project)
root_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(root_dir)
# ---------------------------------------------------------

try:
    import config
    import requests
except ImportError as e:
    print(f"❌ ERROR IMPORT: {e}")
    print("Pastikan Anda menjalankan script ini di environment yang benar.")
    print(f"Python mencari config di: {sys.path}")
    sys.exit()

def test_connection():
    print("--- DIAGNOSTIC START ---")
    print(f"📂 Root Directory terdeteksi: {root_dir}")
    
    # 1. Cek Config
    use_tg = getattr(config, 'USE_TELEGRAM', 'Tidak ditemukan')
    print(f"1. USE_TELEGRAM status: {use_tg}")
    
    token = getattr(config, "TELEGRAM_BOT_TOKEN", "KOSONG")
    chat_id = getattr(config, "TELEGRAM_CHAT_ID", "KOSONG")
    
    print(f"2. Token Check: {'OK' if len(str(token)) > 20 else 'TERLIHAT SALAH/PENDEK'}")
    print(f"3. Chat ID Check: {chat_id}")

    # 2. Cek Library Requests
    print("4. Library 'requests': TERINSTALL")

    # 3. Coba Kirim Pesan Real
    print("5. Mencoba mengirim pesan test ke Telegram...")
    
    if not token or token == "KOSONG":
        print("❌ ERROR: Token belum diisi di config.py")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": "✅ <b>TEST BERHASIL!</b>\nBot Trading Anda terhubung ke Telegram.",
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        res_json = response.json()
        
        if response.status_code == 200 and res_json.get("ok"):
            print("\n✅ SUKSES! Cek Telegram Anda, pesan seharusnya sudah masuk.")
        else:
            print(f"\n❌ GAGAL! Telegram menolak.")
            print(f"Status Code: {response.status_code}")
            print(f"Error Message: {res_json.get('description')}")
            
            if "Chat not found" in str(res_json):
                print("👉 SOLUSI: Anda belum klik START di bot Telegram Anda.")
            elif "Unauthorized" in str(res_json):
                print("👉 SOLUSI: Token Bot di config.py salah/kurang lengkap.")

    except Exception as e:
        print(f"\n❌ ERROR KONEKSI: {e}")
        print("Pastikan internet Anda lancar (tidak diblokir firewall/proxy).")

if __name__ == "__main__":
    test_connection()