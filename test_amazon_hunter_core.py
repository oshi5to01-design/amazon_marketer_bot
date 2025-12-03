import pytest
from bs4 import BeautifulSoup
import amazon_hunter_core


# ====================================================================
# 1. 数字変換ロジックのテスト (_clean_number)
# ====================================================================
def test_clean_number():
    """ゴミ付きの文字列から、正しく数字だけを取り出せるか？"""
    # 普通のパターン
    assert amazon_hunter_core._clean_number("￥1,980") == 1980
    assert amazon_hunter_core._clean_number("2,500") == 2500

    # 割引率のパターン
    assert amazon_hunter_core._clean_number("-15%") == 15

    # 変なゴミがついているパターン
    assert amazon_hunter_core._clean_number("参考価格: ￥5,000") == 5000

    # 数字がないパターン
    assert amazon_hunter_core._clean_number("在庫なし") == 0
    assert amazon_hunter_core._clean_number(None) == 0


# ====================================================================
# 2. HTML解析ロジックのテスト (_extract_price_info)
# ====================================================================
def test_extract_price_info_success():
    """
    Amazonっぽい偽物のHTMLを渡して、
    価格・割引率・元値を正しく抜き出せるか？
    """
    # 偽物のHTML（Amazonの構造を真似したもの）
    fake_html = """
    <html>
        <body>
            <!-- 現在価格エリア -->
            <div id="corePriceDisplay_desktop_feature_div">
                <span class="a-price-whole">2,980</span>
            </div>
            
            <!-- 割引率エリア -->
            <span class="savingsPercentage">-10%</span>
            
            <!-- 参考価格エリア -->
            <span class="a-price a-text-price">
                <span class="a-offscreen">￥3,300</span>
            </span>
        </body>
    </html>
    """

    # BeautifulSoupで解析させる
    soup = BeautifulSoup(fake_html, "html.parser")

    # テスト対象の関数を実行
    info = amazon_hunter_core._extract_price_info(soup)

    # 結果の検証
    assert info["price"] == 2980
    assert info["discount"] == 10
    assert info["original_price"] == 3300


def test_extract_price_info_no_discount():
    """
    割引がない商品（定価のみ）の場合、エラーにならず動くか？
    """
    # 割引タグがないHTML
    fake_html = """
    <html>
        <body>
            <div id="corePrice_feature_div">
                <span class="a-price-whole">10,000</span>
            </div>
        </body>
    </html>
    """

    soup = BeautifulSoup(fake_html, "html.parser")
    info = amazon_hunter_core._extract_price_info(soup)

    assert info["price"] == 10000
    assert info["discount"] == 0  # 割引なしなら0
    assert info["original_price"] == 0  # 元値なしなら0
