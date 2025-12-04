import requests
import json
import os
import time
import config

class MarketScanner:
    def __init__(self, json_path="universe.json"):
        self.json_path = json_path
        self.base_url = "https://testnet.binancefuture.com/fapi/v1/ticker/24hr" 

    def load_universe(self):
        if not os.path.exists(self.json_path):
            alt_path = os.path.join("main", "strategies", "universe.json")
            if os.path.exists(alt_path):
                self.json_path = alt_path
            else:
                return []
        with open(self.json_path, 'r') as f:
            return json.load(f)

    # Note: Tambahkan parameter 'override_mode' agar bisa diatur dari command line
    def get_top_volatile(self, limit=10, override_mode=None):
        universe = self.load_universe()
        if not universe: return []

        # Prioritas: Command Line > Config > Default
        sort_mode = override_mode if override_mode else getattr(config, 'SCANNER_SORT_MODE', 'hybrid')
        min_vol = getattr(config, 'SCANNER_MIN_VOLUME', 1000000)
        blacklist = getattr(config, 'SCANNER_BLACKLIST', [])
        min_change = getattr(config, 'SCANNER_MIN_CHANGE', 0.0)

        print(f"🔍 Scanning Market...")
        print(f"   Mode: {sort_mode.upper()} | Min Vol: ${min_vol:,.0f}")

        try:
            response = requests.get(self.base_url, timeout=20)
            if response.status_code != 200: return []
            data = response.json()
            
            candidates = []
            for item in data:
                symbol = item['symbol']
                if symbol not in universe: continue
                if symbol in blacklist: continue

                vol_usdt = float(item['quoteVolume'])
                if vol_usdt < min_vol: continue

                price_change = abs(float(item['priceChangePercent']))
                if price_change < min_change: continue

                candidates.append(item)
            
            if not candidates: 
                print("⚠️ Filter terlalu ketat. Mengambil data mentah.")
                candidates = [i for i in data if i['symbol'] in universe]

            # --- SORTING LOGIC ---
            
            if sort_mode == 'activity':
                # Sort by Trades Count
                sorted_data = sorted(candidates, key=lambda x: int(x['count']), reverse=True)
                
            elif sort_mode == 'volatility':
                # Sort by Price Change %
                sorted_data = sorted(candidates, key=lambda x: abs(float(x['priceChangePercent'])), reverse=True)
                
            elif sort_mode == 'hybrid':
                # --- HYBRID ALGORITHM ---
                # 1. Ranking by Count
                rank_count = sorted(candidates, key=lambda x: int(x['count']), reverse=True)
                map_rank_count = {item['symbol']: i for i, item in enumerate(rank_count)}
                
                # 2. Ranking by Volatility
                rank_vol = sorted(candidates, key=lambda x: abs(float(x['priceChangePercent'])), reverse=True)
                map_rank_vol = {item['symbol']: i for i, item in enumerate(rank_vol)}
                
                # 3. Combine Score (Lower Score = Better)
                # Score = (Rank Activity * 0.5) + (Rank Volatility * 0.5)
                hybrid_scores = []
                for item in candidates:
                    sym = item['symbol']
                    r_c = map_rank_count.get(sym, 999)
                    r_v = map_rank_vol.get(sym, 999)
                    final_score = r_c + r_v # Simple addition logic
                    
                    hybrid_scores.append({
                        'data': item,
                        'score': final_score
                    })
                
                # Sort by lowest score
                hybrid_sorted = sorted(hybrid_scores, key=lambda x: x['score'])
                sorted_data = [x['data'] for x in hybrid_sorted]

            # Ambil Top N
            top_n = sorted_data[:limit]
            
            final_symbols = []
            print(f"\n⚡ TOP {limit} RESULTS ({sort_mode.upper()}):")
            print(f"{'SYMBOL':<10} | {'TRADES':<8} | {'CHANGE':<8} | {'VOL (M)':<8}")
            print("-" * 50)
            
            for item in top_n:
                sym_formatted = item['symbol'].replace("USDT", "/USDT")
                final_symbols.append(sym_formatted)
                
                count = int(item['count'])
                change = float(item['priceChangePercent'])
                vol_m = float(item['quoteVolume']) / 1000000
                
                print(f"{sym_formatted:<10} | {count:<8} | {change:>6.2f}% | ${vol_m:.1f}M")
                
            return final_symbols

        except Exception as e:
            print(f"Scanner Error: {e}")
            return []

if __name__ == "__main__":
    scanner = MarketScanner()
    scanner.get_top_volatile(10, override_mode='hybrid')