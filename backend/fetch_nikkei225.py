import json
import os

import requests
from bs4 import BeautifulSoup


def fetch_nikkei_225():
    url = "https://ja.wikipedia.org/wiki/%E6%97%A5%E7%B5%8C%E5%B9%B3%E5%9D%87%E6%A0%AA%E4%BE%A1"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    )
    headers = {"User-Agent": user_agent}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        stocks = []
        # find the table that contains "構成銘柄一覧" or the table headers 証券コード/銘柄名
        tables = soup.find_all('table', {'class': 'wikitable'})
        for table in tables:
            headers_th = table.find_all('th')
            header_texts = [th.get_text(strip=True) for th in headers_th]
            
            if any('コード' in h for h in header_texts) and any('銘柄' in h for h in header_texts):
                rows = table.find_all('tr')
                # Figure out column indices
                code_idx = -1
                name_idx = -1
                sector_idx = -1
                
                # Parsing the header row which is usually the first row
                for i, th in enumerate(rows[0].find_all(['th', 'td'])):
                    txt = th.get_text(strip=True)
                    if 'コード' in txt:
                        code_idx = i
                    elif '銘柄' in txt:
                        name_idx = i
                    elif '業種' in txt:
                        sector_idx = i
                
                if code_idx == -1 or name_idx == -1:
                    continue
                    
                for row in rows[1:]:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) > max(code_idx, name_idx):
                        code = cols[code_idx].get_text(strip=True)
                        name_ja = cols[name_idx].get_text(strip=True)
                        sector = cols[sector_idx].get_text(strip=True) if sector_idx != -1 else ""
                        
                        if code.isdigit():
                            stocks.append({
                                "code": code,
                                "name_ja": name_ja,
                                "name_en": "",
                                "sector": sector
                            })
                
        if len(stocks) > 0:
            out_path = os.path.join(os.path.dirname(__file__), 'nikkei225.json')
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(stocks, f, ensure_ascii=False, indent=2)
            print(f"Successfully saved {len(stocks)} stocks.")
        else:
            print("Failed to find or parse the Nikkei 225 table.")
    except Exception as e:
        print(f"Error fetching data: {e}")

if __name__ == "__main__":
    fetch_nikkei_225()
