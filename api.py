from flask import Flask, request
from flask_cors import CORS, cross_origin
import os
from os.path import join, dirname
from dotenv import load_dotenv
from supabase import create_client
import json
from time import sleep

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import requests
import chromedriver_autoinstaller

# Set up env
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Init app
app = Flask(__name__)
cors = CORS(app)
cors = CORS(app, resources={"*": {"origins": ["https://provo.dscdut.com"]}})
app.config['CORS_HEADERS'] = 'Content-Type'

def delete():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    supabase = create_client(url, key)
    supabase.table("voucher").delete().neq("id", -1).execute()


@app.route("/api/v1/update_voucher", methods=['GET'])
def update_voucher():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    supabase = create_client(url, key)
    supabase.table("voucher").delete().neq("id", -1).execute()
    success, fail = 0, 0
    types = ['Tiki', 'Lazada', 'Sendo', 'Grab', 'Nguyen-Kim', 'Fahasha', 'Now', "Shopee"]
    for type_ in types:
        if type_ == "Shopee":
            chromedriver_autoinstaller.install()
            option = Options()
            option.add_argument("--start-maximized")
            option.add_argument("--headless")
            option.add_experimental_option('excludeSwitches', ['enable-logging'])
            option.add_argument('--ignore-certificate-errors')
            option.add_argument('--ignore-ssl-errors')
            option.add_argument("--disable-infobars")
            option.add_argument("--disable-dev-shm-usage")
            option.add_argument('--disable-extensions')
            driver = webdriver.Chrome(options=option)
            driver.get("https://www.shopeeanalytics.com/vn/ma-giam-gia.html")
            sleep(3)
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            driver.quit()
            items = soup.find_all("li", class_="bc_voucher_item")
            for item in items:
                try:
                    record = {}
                    record["type"] = "Shopee"
                    record["category"] = item['data-cat']
                    date = item.find("div", class_="bc_voucher_desc").find("span").text
                    if "Bắt đầu" in date:
                        record["start_at"] = date
                    else:
                        record["end_at"] = date
                    try:
                        record["discount_code"] = item.find("a", class_="bc_voucher_button bc_voucher_copy")['data-code']
                    except:
                        pass
                    titles = ["Hoàn tối đa", "Giảm tối đa", "Đơn tối thiểu"]
                    text = item.find("div", class_="bc_voucher_title").find_all("span")[-1].text
                    idxs = [0] + sorted([text.find(tl) for tl in titles if text.find(tl) != -1], reverse=False) + [None]
                    temp = [text[idxs[i]:idxs[i+1]] for i in range(len(idxs)-1)]
                    for k, t in enumerate(temp):
                        if k == 0:
                            record["discount"] = t.strip()
                        elif (titles[0] in t) or (titles[1] in t):
                            record["max_discount"] = t.replace(titles[0], "").replace(titles[1], "").strip()
                        elif titles[2] in t:
                            record["min_purchase"] = t.replace(titles[2], "").strip()
                    supabase.table("voucher").insert(record).execute()
                    success += 1
                except:
                    fail += 1
        else:
            page = requests.get(f"https://magiamgia.com/{type_.lower()}/")
            soup = BeautifulSoup(page.content, "html.parser")

            tops = soup.find_all("div", class_="mgg-top")
            bots = soup.find_all("div", class_="mgg-bottom")
            for i in range(len(tops)):
                try:
                    record = {}
                    record["type"] = type_
                    record["discount"] = tops[i].find("div", class_="mgg-discount").text.strip()

                    titles = [t.text.strip() for t in tops[i].find_all("span", class_="polyxgo_bold")]
                    text = tops[i].find("div", class_="polyxgo_title").text.strip()
                    idxs = [text.index(tl) for tl in titles] + [None]

                    temp = [text[idxs[j]:idxs[j+1]].split(':')[1].strip() for j in range(len(idxs)-1)]
                    for k,t in enumerate(titles):
                        if "tối đa" in t:
                            record["max_discount"] = temp[k]
                        elif "tối thiểu" in t:
                            record["min_purchase"] = temp[k]
                        elif "lực lúc" in t:
                            record["start_at"] = temp[k]
                        elif "hết hạn" in t:
                            record["end_at"] = temp[k]
                        elif "Ngành hàng" in t:
                            record["category"] = temp[k].replace(" (…chi tiết)", ".")
                    discount_code = bots[i].find("span", class_="vc-mgg")
                    if discount_code:
                        record["discount_code"] = discount_code.text
                    supabase.table("voucher").insert(record).execute()
                    success += 1
                except:
                    fail += 1
    print(success, fail)
    return {
        "code": 200,
        "success": success,
        "fail": fail
    }

@app.route("/api/v1/get_voucher", methods=['GET'])
def get_voucher():
    data = "null"
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    supabase = create_client(url, key)
    if 'type_' in request.args:
        type_ = str(request.args['type_'])
        data = supabase.table("voucher").select("*").eq("type", type_).execute()
    else:
        data = supabase.table("voucher").select("*").execute()
    data_json = json.loads(data.json())
    data_entries = data_json['data']
    print(data_entries)
    return {
        "data": data_entries,
        "num_records": len(data_entries)
    }

if __name__ == "__main__":
    update_voucher()
    # delete()
