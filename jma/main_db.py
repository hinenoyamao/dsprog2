import flet as ft
import json

# ローカルのエリアデータファイルのパス
AREA_FILE_PATH = "/Users/hinenoyamao/Lecture/DSp2/jma/areas.json"
FORECAST_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/{}.json"

# 地域データをローカルファイルから取得して階層構造を作成
def fetch_area_hierarchy():
    """ローカルファイルから地域データを読み込み、階層構造を生成"""
    try:
        with open(AREA_FILE_PATH, "r", encoding="utf-8") as f:
            areas_data = json.load(f)
        
        # 必要なデータを階層構造で統合
        return {
            "centers": areas_data["centers"],
            "offices": areas_data["offices"]
        }
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading area data from file: {e}")
        return None

# 天気予報データを取得
def fetch_forecast(office_code):
    """指定された地域コードに基づいて天気予報を取得"""
    import requests
    try:
        response = requests.get(FORECAST_URL.format(office_code))
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching forecast for office_code {office_code}: {e}")
        return None

def get_three_day_forecast(forecast_data, detail_code):
    """詳細地域コードに基づいて3日分の天気予報を抽出"""
    if not forecast_data:
        return "天気予報データがありません。"

    try:
        # 時系列データを探索
        for time_series in forecast_data[0]["timeSeries"]:
            if "timeDefines" in time_series and "areas" in time_series:
                time_defines = time_series["timeDefines"]
                for area in time_series["areas"]:
                    if area["area"]["code"] == detail_code:
                        forecast_text = ""
                        for i in range(min(3, len(time_defines))):
                            date = time_defines[i]
                            weather = area.get("weathers", ["不明"])[i]
                            wind = area.get("winds", ["不明"])[i]
                            # 波の情報があるか確認して取得
                            wave = (
                                area.get("waves", ["波の情報はありません"])[i]
                                if "waves" in area
                                else "波の情報はありません"
                            )

                            forecast_text += (
                                f"日付: {date}\n"
                                f"天気: {weather}\n"
                                f"風: {wind}\n"
                                f"波: {wave}\n\n"
                            )
                        return forecast_text
    except (KeyError, IndexError) as e:
        print(f"Error parsing forecast data: {e}")
        return "予報データの形式が不正です。"

    return "該当するデータが見つかりません。"

def main(page: ft.Page):
    page.title = "天気予報アプリ"
    page.padding = 20
    page.bgcolor = ft.colors.BLUE_GREY_100 

    # ヘッダー
    header = ft.Container(
        content=ft.Text("天気予報", size=30, weight="bold", color=ft.colors.WHITE),
        padding=15,
        alignment=ft.alignment.center,
        bgcolor=ft.colors.INDIGO_300,  
    )

    # 地域データの取得
    area_hierarchy = fetch_area_hierarchy()
    if not area_hierarchy:
        page.add(ft.Text("地域データの取得に失敗しました。"))
        return

    # UI要素の初期化
    centers_dropdown = ft.Dropdown(label="地方を選択してください", options=[])
    offices_dropdown = ft.Dropdown(label="地域を選択してください", options=[], disabled=True)
    details_dropdown = ft.Dropdown(label="詳細地域を選択してください", options=[], disabled=True)
    forecast_text = ft.Text()

    # 地方選択時の処理
    def on_center_select(e):
        selected_center = centers_dropdown.value
        if not selected_center:
            offices_dropdown.options = []
            offices_dropdown.disabled = True
            details_dropdown.options = []
            details_dropdown.disabled = True
        else:
            offices_dropdown.options = [
                ft.dropdown.Option(key=key, text=value["name"])
                for key, value in area_hierarchy["offices"].items()
                if value["parent"] == selected_center
            ]
            offices_dropdown.disabled = False

        details_dropdown.options = []
        details_dropdown.disabled = True
        page.update()

    # 地域選択時の処理
    def on_office_select(e):
        selected_office = offices_dropdown.value
        if not selected_office:
            details_dropdown.options = []
            details_dropdown.disabled = True
        else:
            forecast_data = fetch_forecast(selected_office)
            if not forecast_data:
                forecast_text.value = "天気予報データを取得できませんでした。"
                details_dropdown.options = []
                details_dropdown.disabled = True
            else:
                details_dropdown.options = [
                    ft.dropdown.Option(key=area["area"]["code"], text=area["area"]["name"])
                    for area in forecast_data[0]["timeSeries"][0]["areas"]
                ]
                details_dropdown.disabled = False
        page.update()

    # 天気予報表示ボタンの処理
    def on_show_forecast(e):
        selected_detail = details_dropdown.value
        if not selected_detail:
            forecast_text.value = "詳細地域を選択してください。"
        else:
            selected_office = offices_dropdown.value
            forecast_data = fetch_forecast(selected_office)
            forecast_text.value = get_three_day_forecast(forecast_data, selected_detail)
        page.update()

    # ドロップダウンの初期化
    centers_dropdown.options = [
        ft.dropdown.Option(key=key, text=value["name"])
        for key, value in area_hierarchy["centers"].items()
    ]
    centers_dropdown.on_change = on_center_select
    offices_dropdown.on_change = on_office_select

    # ボタン
    forecast_button = ft.ElevatedButton(
    text="天気予報を表示",
    on_click=on_show_forecast,
    bgcolor=ft.colors.INDIGO_300, 
    color=ft.colors.WHITE,  # ボタンの文字色を白に設定（対比を強く）
)


    # ページレイアウト
    page.add(header, centers_dropdown, offices_dropdown, details_dropdown, forecast_button, forecast_text)

# アプリケーションの実行
ft.app(target=main)
