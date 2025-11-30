import requests

# Pilih mau cek server mana (Uncomment salah satu)
# BASE_URL = "https://fapi.binance.com"          # SERVER ASLI (LIVE)
BASE_URL = "https://testnet.binancefuture.com"   # SERVER TESTNET (DEMO)

def get_futures_symbols():
    print(f"Sedang mengambil data dari: {BASE_URL} ...")
    
    try:
        # Endpoint Public untuk info exchange
        url = f"{BASE_URL}/fapi/v1/exchangeInfo"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            symbols = []
            
            # Filter hanya pair USDT yang statusnya TRADING (Aktif)
            for s in data['symbols']:
                if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING':
                    symbols.append(s['symbol'])
            
            symbols.sort() # Urutkan abjad
            
            print(f"\n✅ Ditemukan {len(symbols)} Pair USDT-Futures:")
            print("=" * 60)
            
            # Print rapi berbaris
            line = ""
            for sym in symbols:
                # Format ulang BTCUSDT jadi BTC/USDT agar mudah dibaca
                formatted = sym.replace("USDT", "/USDT")
                line += f"{formatted:<15}"
                if len(line) > 60:
                    print(line)
                    line = ""
            if line: print(line)
            
            print("=" * 60)
            print("\nCara pakai di command line:")
            # Contoh ambil 5 random
            sample = ",".join([s.replace("USDT", "/USDT") for s in symbols[:5]])
            print(f"--symbols {sample}")
            
        else:
            print(f"Error: {response.status_code}")
            
    except Exception as e:
        print(f"Koneksi Gagal: {e}")

if __name__ == "__main__":
    get_futures_symbols()