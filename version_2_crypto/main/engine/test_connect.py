import requests
import pandas as pd
import time
import datetime as dt

# --- KONFIGURASI MANUAL ---
# Kita gunakan URL Testnet Futures sesuai dokumentasi
BASE_URL = 'https://testnet.binancefuture.com'
SYMBOL = 'BTCUSDT' # Tanpa garis miring untuk Raw API

print(f"--- UJI COBA MARKET DATA (RAW API) ---")
print(f"Target Server: {BASE_URL}")
print(f"Target Symbol: {SYMBOL}")
print("-" * 40)

def test_server_time():
    print("\n1. [TEST] Cek Server Time (/fapi/v1/time)...")
    try:
        url = f"{BASE_URL}/fapi/v1/time"
        start = time.time()
        response = requests.get(url)
        latency = (time.time() - start) * 1000
        
        if response.status_code == 200:
            server_time = response.json()['serverTime']
            local_time = int(time.time() * 1000)
            diff = server_time - local_time
            
            print(f"✅ SUKSES! (Latency: {latency:.2f}ms)")
            print(f"   Server Time : {server_time}")
            print(f"   Local Time  : {local_time}")
            print(f"   Selisih     : {diff} ms")
        else:
            print(f"❌ GAGAL. Status: {response.status_code}")
    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_ticker_price():
    print("\n2. [TEST] Cek Harga Realtime (/fapi/v1/ticker/price)...")
    try:
        url = f"{BASE_URL}/fapi/v1/ticker/price"
        params = {'symbol': SYMBOL}
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            price = float(data['price'])
            print(f"✅ SUKSES!")
            print(f"   Harga {SYMBOL} : {price}")
        else:
            print(f"❌ GAGAL. Status: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_klines():
    print("\n3. [TEST] Cek Candle/Klines (/fapi/v1/klines)...")
    try:
        url = f"{BASE_URL}/fapi/v1/klines"
        # Kita minta 5 candle terakhir timeframe 15 menit
        params = {
            'symbol': SYMBOL,
            'interval': '15m',
            'limit': 5
        }
        
        print(f"   Requesting: {params}")
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUKSES! Diterima {len(data)} candle.")
            
            # --- PARSING MANUAL (Penting untuk Engine) ---
            # Format Binance: [OpenTime, Open, High, Low, Close, Vol, ...]
            ohlcv = []
            for row in data:
                ohlcv.append([
                    int(row[0]),      # Timestamp
                    float(row[1]),    # Open
                    float(row[2]),    # High
                    float(row[3]),    # Low
                    float(row[4]),    # Close
                    float(row[5])     # Volume
                ])
            
            # Buat DataFrame
            df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            # Convert time agar bisa dibaca manusia
            df['date_str'] = pd.to_datetime(df['time'], unit='ms')
            
            print("\n   Sample Data (DataFrame):")
            print(df[['date_str', 'close', 'volume']].to_string(index=False))
            print("\n✅ Parsing OK. Siap masuk strategi.")
            
        else:
            print(f"❌ GAGAL. Status: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_server_time()
    test_ticker_price()
    test_klines()