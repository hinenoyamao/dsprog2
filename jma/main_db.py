import sqlite3
import requests
import datetime

# データベースに接続します。
conn = sqlite3.connect('jma/weather.db')
cursor = conn.cursor()


# ------------------------------
# 1. テーブルの作成
# ------------------------------

# regions（地方）テーブルを作成します。
cursor.execute('''
CREATE TABLE IF NOT EXISTS regions (
    region_id TEXT PRIMARY KEY,
    region_name TEXT NOT NULL
)
''')

# prefectures（都道府県）テーブルを作成します。
cursor.execute('''
CREATE TABLE IF NOT EXISTS prefectures (
    prefecture_id TEXT PRIMARY KEY,
    prefecture_name TEXT NOT NULL,
    region_id TEXT NOT NULL,
    FOREIGN KEY (region_id) REFERENCES regions(region_id)
)
''')

# areas（一次細分区域）テーブルを作成します。
cursor.execute('''
CREATE TABLE IF NOT EXISTS areas (
    area_id TEXT PRIMARY KEY,
    area_name TEXT NOT NULL,
    prefecture_id TEXT NOT NULL,
    FOREIGN KEY (prefecture_id) REFERENCES prefectures(prefecture_id)
)
''')

# weather_forecasts（天気予報）テーブルを作成します。
cursor.execute('''
CREATE TABLE IF NOT EXISTS weather_forecasts (
    forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id TEXT NOT NULL,
    date DATE NOT NULL,
    weather TEXT,
    wind TEXT,
    wave TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (area_id) REFERENCES areas(area_id)
)
''')

conn.commit()

# ------------------------------
# 2. 地域データの取得と挿入
# ------------------------------

# 地域データのURL
AREA_DATA_URL = "https://www.jma.go.jp/bosai/common/const/area.json"

# 地域データを取得します。
response = requests.get(AREA_DATA_URL)
area_data = response.json()

# regions（地方）テーブルにデータを挿入します。
regions = area_data["centers"]
for region_id, info in regions.items():
    region_name = info["name"]
    cursor.execute('''
        INSERT OR IGNORE INTO regions (region_id, region_name)
        VALUES (?, ?)
    ''', (region_id, region_name))

# prefectures（都道府県）テーブルにデータを挿入します。
prefectures = area_data["offices"]
for prefecture_id, info in prefectures.items():
    prefecture_name = info["name"]
    region_id = info["parent"]
    cursor.execute('''
        INSERT OR IGNORE INTO prefectures (prefecture_id, prefecture_name, region_id)
        VALUES (?, ?, ?)
    ''', (prefecture_id, prefecture_name, region_id))

conn.commit()

# areas（一次細分区域）テーブルにデータを挿入します。
class10s = area_data["class10s"]
for area_id, info in class10s.items():
    area_name = info["name"]
    prefecture_id = info["parent"]
    cursor.execute('''
        INSERT OR IGNORE INTO areas (area_id, area_name, prefecture_id)
        VALUES (?, ?, ?)
    ''', (area_id, area_name, prefecture_id))

conn.commit()

# ------------------------------
# 3. 天気予報データの取得と挿入
# ------------------------------

# 天気予報データを取得する関数を定義します。
def fetch_forecast(prefecture_id):
    forecast_url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{prefecture_id}.json"
    response = requests.get(forecast_url)
    return response.json()

# 天気予報データを挿入する関数を定義します。
def insert_weather_forecasts(prefecture_id):
    forecast_data = fetch_forecast(prefecture_id)
    
    for report in forecast_data:
        time_series_list = report["timeSeries"]
        for time_series in time_series_list:
            time_defines = time_series["timeDefines"]
            areas_in_forecast = time_series["areas"]
            for area in areas_in_forecast:
                area_code = area["area"]["code"]
                # エリアがデータベースに存在するか確認します。
                cursor.execute('SELECT area_id FROM areas WHERE area_id = ?', (area_code,))
                if cursor.fetchone() is None:
                    continue  # 存在しない場合はスキップ
                
                # 各種データが存在する場合に取得します（3日分のみ）
                num_times = min(3, len(time_defines))
                time_defines = time_defines[:num_times]
                weathers = area.get("weathers", [])[:num_times]
                winds = area.get("winds", [])[:num_times]
                waves = area.get("waves", [])[:num_times]
                
                for i in range(num_times):
                    date = datetime.datetime.fromisoformat(time_defines[i]).date()
                    weather = weathers[i] if i < len(weathers) else None
                    # 天気情報がない場合はスキップ
                    if not weather:
                        continue
                    wind = winds[i] if i < len(winds) else None
                    wave = waves[i] if i < len(waves) else None
                    # 天気予報データを挿入します。
                    cursor.execute('''
                        INSERT INTO weather_forecasts (area_id, date, weather, wind, wave)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (area_code, date, weather, wind, wave))
    conn.commit()

# 都道府県のリストを取得します。
cursor.execute('SELECT prefecture_id, prefecture_name FROM prefectures')
prefectures_list = cursor.fetchall()

# 各都道府県の天気予報データを取得してデータベースに挿入します。
for prefecture in prefectures_list:
    prefecture_id, prefecture_name = prefecture
    try:
        insert_weather_forecasts(prefecture_id)
        print(f"{prefecture_name} の天気予報データを挿入しました。")
    except Exception as e:
        print(f"{prefecture_name} のデータ挿入中にエラーが発生しました: {e}")

# ------------------------------
# 4. データの階層的な取得と表示
# ------------------------------

# 地方名を指定して、その地方のデータを取得します。
selected_region_name = "東北地方"

# 指定した地方に属する都道府県を取得します。
cursor.execute('''
SELECT p.prefecture_id, p.prefecture_name
FROM regions r
JOIN prefectures p ON r.region_id = p.region_id
WHERE r.region_name = ?
''', (selected_region_name,))
prefectures_list = cursor.fetchall()

# 各都道府県について処理します。
for prefecture_id, prefecture_name in prefectures_list:
    print(f"都道府県: {prefecture_name}")
    # 都道府県に属するエリアを取得します。
    cursor.execute('''
    SELECT area_id, area_name FROM areas WHERE prefecture_id = ?
    ''', (prefecture_id,))
    areas_list = cursor.fetchall()
    for area_id, area_name in areas_list:
        print(f"  エリア: {area_name}")
        # エリアの天気予報を取得します。
        cursor.execute('''
        SELECT date, weather, wind, wave
        FROM weather_forecasts
        WHERE area_id = ? AND date >= DATE('now')
        ORDER BY date
        ''', (area_id,))
        forecasts = cursor.fetchall()
        for forecast in forecasts:
            date, weather, wind, wave = forecast
            print(f"    日付: {date}, 天気: {weather}, 風: {wind}, 波: {wave}")

# データベース接続を閉じます。
conn.close()