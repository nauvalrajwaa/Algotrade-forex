import requests
import json
import os
import time

class MarketScanner:
    def __init__(self, json_path="universe.json"):
        self.json_path = json_path
        
        # --- UPDATE PENTING ---
        # Ganti ke URL TESTNET agar tidak kena blokir Internet Positif
        # URL Lama (Live): "https://fapi.binance.com/fapi/v1/ticker/24hr"
        self.base_url = "https://testnet.binancefuture.com/fapi/v1/ticker/24hr" 

    def load_universe(self):
        # Cek path file
        if not os.path.exists(self.json_path):
            # Coba cari di folder strategies jika path saat ini salah
            alt_path = os.path.join("main", "strategies", "universe.json")
            if os.path.exists(alt_path):
                self.json_path = alt_path
            else:
                print(f"File {self.json_path} tidak ditemukan!")
                return []
        
        with open(self.json_path, 'r') as f:
            return json.load(f)

    def get_top_volatile(self, limit=10):
        """
        Mengambil Top N koin dengan pergerakan (Volatility) tertinggi.
        """
        universe = self.load_universe()
        if not universe: return []

        print(f"🔍 Scanning volatilitas dari {len(universe)} koin di Universe (via Testnet)...")

        try:
            # Ambil data semua ticker
            # Timeout dinaikkan jadi 20 detik buat Wifi Kos yang lemot
            response = requests.get(self.base_url, timeout=20) 
            
            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code}")
                return []

            data = response.json()
            
            # Filter hanya koin yang ada di universe.json
            # Note: Di Testnet, simbolnya mungkin tidak lengkap, jadi kita filter yang ada aja
            filtered_data = [
                item for item in data 
                if item['symbol'] in universe
            ]
            
            if not filtered_data:
                print("⚠️ Tidak ada data koin yang cocok di Testnet. Cek universe.json.")
                return []

            # Sorting Logic: Cari yang perubahan harganya paling besar (Naik/Turun)
            sorted_data = sorted(
                filtered_data, 
                key=lambda x: abs(float(x['priceChangePercent'])), 
                reverse=True
            )
            
            # Ambil Top N
            top_n = sorted_data[:limit]
            
            # Format output
            final_symbols = []
            print(f"\n📊 TOP {limit} VOLATILITY (TESTNET 24H):")
            print(f"{'SYMBOL':<10} | {'CHANGE %':<10} | {'VOLUME':<15}")
            print("-" * 45)
            
            for item in top_n:
                sym_formatted = item['symbol'].replace("USDT", "/USDT")
                final_symbols.append(sym_formatted)
                
                change = float(item['priceChangePercent'])
                vol = float(item['quoteVolume'])
                print(f"{sym_formatted:<10} | {change:>8.2f}% | {vol:,.0f}")
                
            return final_symbols

        except requests.exceptions.Timeout:
            print("❌ Koneksi Timeout. Server Testnet lambat merespon.")
            return []
        except requests.exceptions.ConnectionError:
            print("❌ Koneksi Error. Cek internet atau DNS Anda.")
            return []
        except Exception as e:
            print(f"Error scanning market: {e}")
            return []

if __name__ == "__main__":
    scanner = MarketScanner()
    scanner.get_top_volatile(10)