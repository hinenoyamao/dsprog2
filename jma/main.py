import requests
import json
import os
import flet as ft

class WeatherForecastApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "天気予報アプリ"
        self.page.window_width = 900
        self.page.window_height = 700

        # API エンドポイント
        self.AREA_LIST_URL = "http://www.jma.go.jp/bosai/common/const/area.json"
        self.FORECAST_URL_TEMPLATE = "https://www.jma.go.jp/bosai/forecast/data/forecast/{}.json"

        # ローカル地域データファイルパス
        self.LOCAL_AREA_FILE = '/Users/hinenoyamao/Lecture/DSp2/jma/areas.json'

        # UIコンポーネント
        self.forecast_container = ft.Container(expand=True)
        self.region_dropdown = ft.Dropdown(expand=True, on_change=self._update_regions)
        self.sub_region_dropdown = ft.Dropdown(expand=True, on_change=self._update_weather)

        # 地域リスト
        self.area_list = {}
        self.centers = {}
        self.offices = {}

        # 地域データを取得
        self._fetch_area_list()

        # メインレイアウトを構築
        self._build_layout()

    def _fetch_area_list(self):
        """地域リストを取得 (ローカル or API)"""
        try:
            # ローカルファイルがあれば優先
            if os.path.exists(self.LOCAL_AREA_FILE):
                with open(self.LOCAL_AREA_FILE, 'r', encoding='utf-8') as f:
                    self.area_list = json.load(f)
            else:
                response = requests.get(self.AREA_LIST_URL)
                response.raise_for_status()
                self.area_list = response.json()

            self.centers = self.area_list.get("centers", {})
            self.offices = self.area_list.get("offices", {})
        except (FileNotFoundError, requests.RequestException, json.JSONDecodeError) as e:
            print(f"地域リストの取得に失敗: {e}")

    def _update_regions(self, e):
        """メイン地域選択に応じてサブ地域リストを更新"""
        region_code = self.region_dropdown.value
        if region_code:
            children = self.centers.get(region_code, {}).get("children", [])
            self.sub_region_dropdown.options = [
                ft.dropdown.Option(key=child, text=self.offices.get(child, {}).get("name", "Unknown")) for child in children
            ]
            self.sub_region_dropdown.update()

    def _update_weather(self, e):
        """サブ地域選択に応じて天気予報を取得して表示"""
        area_code = self.sub_region_dropdown.value
        forecast_info = ft.Column(expand=True)
        self.forecast_container.content = ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("地域を選択してください", size=20, weight="bold"),
                        self.region_dropdown,
                        self.sub_region_dropdown,
                    ],
                    width=300,
                    spacing=10,
                ),
                forecast_info
            ],
            expand=True
        )
        self.forecast_container.update()

        if area_code:
            try:
                response = requests.get(self.FORECAST_URL_TEMPLATE.format(area_code))
                response.raise_for_status()
                forecast_data = response.json()

                area_name = self.offices.get(area_code, {}).get("name", "Unknown")
                forecast_info.controls.append(ft.Text(f"{area_name}の天気予報", size=20, weight="bold"))

                for forecast in forecast_data:
                    for time_series in forecast['timeSeries']:
                        for area in time_series['areas']:
                            if area['area']['code'] == area_code:
                                for time, weather in zip(time_series['timeDefines'], area.get('weathers', [])):
                                    forecast_info.controls.append(ft.Text(f"{time}: {weather}"))

                forecast_info.update()
            except requests.RequestException as e:
                forecast_info.controls.append(ft.Text(f"天気予報の取得に失敗: {e}", color=ft.colors.RED))
                forecast_info.update()

    def _build_layout(self):
        """アプリ全体のレイアウトを構築"""
        self.forecast_container.content = ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("地域を選択してください", size=20, weight="bold"),
                        self.region_dropdown,
                        self.sub_region_dropdown,
                    ],
                    width=300,
                    spacing=10,
                ),
                ft.Container(expand=True, bgcolor=ft.colors.SURFACE, padding=10)
            ],
            expand=True
        )
        self.page.add(self.forecast_container)

        # 地域ドロップダウンの初期化
        self.region_dropdown.options = [
            ft.dropdown.Option(key=code, text=info['name']) for code, info in self.centers.items()
        ]
        self.region_dropdown.update()

def main(page: ft.Page):
    WeatherForecastApp(page)

if __name__ == "__main__":
    ft.app(target=main)