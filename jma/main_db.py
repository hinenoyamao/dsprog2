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
    FOREIGN KEY (area_id) REFERENCES areas(area_id),
    UNIQUE (area_id, date) ON CONFLICT REPLACE
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
                    # 天気予報データを挿入または更新します。
                    cursor.execute('''
                        INSERT INTO weather_forecasts (area_id, date, weather, wind, wave)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(area_id, date) DO UPDATE SET
                            weather = excluded.weather,
                            wind = excluded.wind,
                            wave = excluded.wave,
                            created_at = CURRENT_TIMESTAMP
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

# データベース接続を閉じます。
conn.close()

import flet
from flet import Page, Column, Text, colors
import sqlite3

def main(page: Page):
    page.title = "天気予報データの階層的表示"
    page.window_width = 800
    page.window_height = 600
    page.scroll = "adaptive"
    page.update()

    # データベースに接続します
    conn = sqlite3.connect('weather.db')
    cursor = conn.cursor()

    # 地方を取得します
    cursor.execute('SELECT region_id, region_name FROM regions')
    regions = cursor.fetchall()

    # メインのColumnを作成します
    main_column = Column()
    
    for region_id, region_name in regions:
        # 地方名を表示
        region_text = Text(region_name, size=24, weight="bold", color=colors.BLUE)
        main_column.controls.append(region_text)
        
        # 地方に属する都道府県を取得します
        cursor.execute('''
        SELECT prefecture_id, prefecture_name FROM prefectures
        WHERE region_id = ?
        ''', (region_id,))
        prefectures = cursor.fetchall()
        
        for prefecture_id, prefecture_name in prefectures:
            # 都道府県名を表示（インデント）
            prefecture_text = Text(f"└ {prefecture_name}", size=20, weight="bold", color=colors.BLUE_ACCENT)
            main_column.controls.append(prefecture_text)
            
            # 都道府県に属するエリアを取得します
            cursor.execute('''
            SELECT area_id, area_name FROM areas WHERE prefecture_id = ?
            ''', (prefecture_id,))
            areas = cursor.fetchall()
            
            for area_id, area_name in areas:
                # エリア名を表示（さらにインデント）
                area_text = Text(f"    └ {area_name}", size=16, weight="bold", color=colors.GREEN)
                main_column.controls.append(area_text)
                
                # エリアの天気予報を取得します
                cursor.execute('''
                SELECT date, weather, wind, wave FROM weather_forecasts
                WHERE area_id = ? AND date >= DATE('now')
                ORDER BY date
                ''', (area_id,))
                forecasts = cursor.fetchall()
                
                for forecast in forecasts:
                    date, weather, wind, wave = forecast
                    # 天気予報を表示（さらにインデント）
                    forecast_text = Text(
                        f"        - 日付: {date}, 天気: {weather}, 風: {wind}, 波: {wave}",
                        size=14
                    )
                    main_column.controls.append(forecast_text)

    # ページにメインのColumnを追加します
    page.add(main_column)

    # データベース接続を閉じます
    conn.close()

import flet as ft
import sqlite3

def main(page: ft.Page):
    # データベースに接続します
    conn = sqlite3.connect('jma/weather.db')
    cursor = conn.cursor()
    
    # 初期状態の選択肢を設定
    selected_region_id = None
    selected_prefecture_id = None
    selected_area_id = None
    
    # 地方のデータを取得
    cursor.execute('SELECT region_id, region_name FROM regions ORDER BY region_name')
    regions = cursor.fetchall()
    
    # イベントハンドラを定義
    def on_region_change(e):
        nonlocal selected_region_id
        selected_region_id = region_dropdown.value
        # 都道府県ドロップダウンを更新
        cursor.execute('SELECT prefecture_id, prefecture_name FROM prefectures WHERE region_id = ? ORDER BY prefecture_name', (selected_region_id,))
        prefectures = cursor.fetchall()
        prefecture_dropdown.options = [ft.dropdown.Option(pref_id, pref_name) for pref_id, pref_name in prefectures]
        prefecture_dropdown.disabled = False
        prefecture_dropdown.value = None
        prefecture_dropdown.update()
        # エリアと日付ドロップダウンをリセット
        area_dropdown.options = []
        area_dropdown.disabled = True
        area_dropdown.value = None
        area_dropdown.update()
        date_dropdown.options = []
        date_dropdown.disabled = True
        date_dropdown.value = None
        date_dropdown.update()
        weather_text.value = ''
        weather_text.update()
    
    def on_prefecture_change(e):
        nonlocal selected_prefecture_id
        selected_prefecture_id = prefecture_dropdown.value
        # エリアドロップダウンを更新
        cursor.execute('SELECT area_id, area_name FROM areas WHERE prefecture_id = ? ORDER BY area_name', (selected_prefecture_id,))
        areas = cursor.fetchall()
        area_dropdown.options = [ft.dropdown.Option(area_id, area_name) for area_id, area_name in areas]
        area_dropdown.disabled = False
        area_dropdown.value = None
        area_dropdown.update()
        # 日付ドロップダウンをリセット
        date_dropdown.options = []
        date_dropdown.disabled = True
        date_dropdown.value = None
        date_dropdown.update()
        weather_text.value = ''
        weather_text.update()
    
    def on_area_change(e):
        nonlocal selected_area_id
        selected_area_id = area_dropdown.value
        # 日付ドロップダウンを更新
        cursor.execute('SELECT DISTINCT date FROM weather_forecasts WHERE area_id = ? AND date >= DATE("now") ORDER BY date', (selected_area_id,))
        dates = cursor.fetchall()
        date_dropdown.options = [ft.dropdown.Option(str(date[0]), str(date[0])) for date in dates]
        date_dropdown.disabled = False
        date_dropdown.value = None
        date_dropdown.update()
        weather_text.value = ''
        weather_text.update()
    
    def on_date_change(e):
        selected_date = date_dropdown.value
        # 天気予報を取得して表示
        cursor.execute('SELECT weather, wind, wave FROM weather_forecasts WHERE area_id = ? AND date = ?', (selected_area_id, selected_date))
        forecast = cursor.fetchone()
        if forecast:
            weather, wind, wave = forecast
            weather_text.value = f"天気: {weather}\n風: {wind}\n波: {wave}"
        else:
            weather_text.value = "天気予報が見つかりませんでした。"
        weather_text.update()
    
    # ウィジェットを定義
    region_dropdown = ft.Dropdown(
        label="地方を選択してください",
        options=[ft.dropdown.Option(region_id, region_name) for region_id, region_name in regions],
        on_change=on_region_change
    )
    
    prefecture_dropdown = ft.Dropdown(
        label="都道府県を選択してください",
        options=[],
        on_change=on_prefecture_change,
        disabled=True
    )
    
    area_dropdown = ft.Dropdown(
        label="一次細分区域を選択してください",
        options=[],
        on_change=on_area_change,
        disabled=True
    )
    
    date_dropdown = ft.Dropdown(
        label="日付を選択してください",
        options=[],
        on_change=on_date_change,
        disabled=True
    )
    
    weather_text = ft.Text()
    
    # ページにウィジェットを追加
    page.add(
        region_dropdown,
        prefecture_dropdown,
        area_dropdown,
        date_dropdown,
        weather_text
    )
    
    # ページ終了時にデータベース接続を閉じる
    def on_disconnect(e):
        conn.close()
    page.on_disconnect = on_disconnect

ft.app(target=main)