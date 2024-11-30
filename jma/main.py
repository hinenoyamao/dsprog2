import flet as ft
import requests

# エンドポイントのURL
AREA_URL = "https://www.jma.go.jp/bosai/common/const/area.json"
FORECAST_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/{}.json"

# 地域データを取得して階層構造を作成
def get_area_hierarchy():
    try:
        response = requests.get(AREA_URL)
        response.raise_for_status()
        areas_data = response.json()

        # 階層的にデータを統合
        hierarchy = {
            "centers": areas_data["centers"],
            "offices": areas_data["offices"]
        }
        return hierarchy
    except requests.RequestException as e:
        print(f"Error fetching area hierarchy: {e}")
        return None

# 天気予報情報を取得する関数
def get_forecast(office_code):
    try:
        response = requests.get(FORECAST_URL.format(office_code))
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching forecast for office_code {office_code}: {e}")
        return None

# 詳細地域の3日分の天気予報を取得
def get_3day_forecast(forecast_data, detail_code):
    if not forecast_data:
        return "天気予報データがありません"

    weather_info = ""
    try:
        # areas内を探索し、detail_codeに一致する地域を見つける
        for time_series in forecast_data[0]["timeSeries"]:
            if "timeDefines" in time_series and "areas" in time_series:
                time_defines = time_series["timeDefines"]
                for area in time_series["areas"]:
                    if area["area"]["code"] == detail_code:
                        # 3日分のデータを取得
                        for i in range(min(3, len(time_defines))):
                            date = time_defines[i]
                            weather = area.get("weathers", ["不明"])[i] if "weathers" in area else "不明"
                            wind = area.get("winds", ["不明"])[i] if "winds" in area else "不明"
                            wave = area.get("waves", ["不明"])[i] if "waves" in area else "不明"

                            weather_info += (
                                f"日付: {date}\n"
                                f"天気: {weather}\n"
                                f"風: {wind}\n"
                                f"波: {wave}\n\n"
                            )
                        return weather_info
    except (KeyError, IndexError):
        return "指定されたデータ形式に一致する予報データがありません"
    
    return "該当する天気予報データが見つかりません"

# Fletアプリケーションのメイン関数
def main(page: ft.Page):
    page.title = "三層構造 地域選択 天気予報"
    page.padding = 20

    # 地域データを取得
    area_hierarchy = get_area_hierarchy()
    if area_hierarchy is None:
        page.add(ft.Text("地域データの取得に失敗しました"))
        return

    # ドロップダウン
    centers_dropdown = ft.Dropdown(label="地方を選択してください", options=[])
    offices_dropdown = ft.Dropdown(label="地域を選択してください", options=[], disabled=True)
    details_dropdown = ft.Dropdown(label="詳細地域を選択してください", options=[], disabled=True)
    forecast_text = ft.Text()

    # 地方選択後の地域更新
    def update_offices(e):
        selected_center = centers_dropdown.value
        print(f"選択された地方: {selected_center}")
        if not selected_center:
            offices_dropdown.options = []
            offices_dropdown.disabled = True
            details_dropdown.options = []
            details_dropdown.disabled = True
        else:
            offices = [
                ft.dropdown.Option(key=key, text=value["name"])
                for key, value in area_hierarchy["offices"].items()
                if value["parent"] == selected_center
            ]
            print(f"取得された地域: {offices}")
            offices_dropdown.options = offices
            offices_dropdown.disabled = False
        details_dropdown.options = []
        details_dropdown.disabled = True
        page.update()

    # 地域選択後の詳細地域更新
    def update_details(e):
        selected_office = offices_dropdown.value
        print(f"選択された地域コード: {selected_office}")

        if not selected_office:
            details_dropdown.options = []
            details_dropdown.disabled = True
        else:
            # 天気予報データを取得（officeコードを使用）
            forecast_data = get_forecast(selected_office)
            if not forecast_data:
                forecast_text.value = "天気予報データを取得できませんでした"
                details_dropdown.options = []
                details_dropdown.disabled = True
                page.update()
                return

            # areasから詳細地域名を取得
            details = [
                ft.dropdown.Option(key=area["area"]["code"], text=area["area"]["name"])
                for area in forecast_data[0]["timeSeries"][0]["areas"]
            ]
            print(f"取得された詳細地域: {details}")
            details_dropdown.options = details
            details_dropdown.disabled = False
        page.update()

    # 詳細地域の天気予報を表示
    def show_forecast(e):
        selected_detail = details_dropdown.value

        print(f"選択された詳細地域コード: {selected_detail}")

        if not selected_detail:
            forecast_text.value = "詳細地域を選択してください"
            page.update()
            return

        # 天気予報データを取得
        selected_office = offices_dropdown.value
        forecast_data = get_forecast(selected_office)
        if not forecast_data:
            forecast_text.value = "天気予報を取得できませんでした"
            page.update()
            return

        # 詳細地域の3日分天気予報を取得
        detail_forecast = get_3day_forecast(forecast_data, selected_detail)
        forecast_text.value = detail_forecast
        page.update()

    # 地方選択ドロップダウンの初期化
    centers_dropdown.options = [
        ft.dropdown.Option(key=key, text=value["name"])
        for key, value in area_hierarchy["centers"].items()
    ]
    centers_dropdown.on_change = update_offices
    offices_dropdown.on_change = update_details

    # ボタン
    button = ft.ElevatedButton(
        text="天気予報を表示",
        on_click=show_forecast,
    )

    # ページレイアウト
    page.add(centers_dropdown, offices_dropdown, details_dropdown, button, forecast_text)

# アプリケーションを起動
ft.app(target=main)
