import os
import json
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import pymongo
import json
from pymongo import MongoClient, InsertOne
from pymongo.server_api import ServerApi
import pandas as pd
import pdfplumber
from datetime import datetime
load_dotenv()

# Set the number of the last Perpres you want to check
def set_json(number):
    data = {
        "number": number
    }

    with open('number.json', 'w') as file:
        json.dump(data, file)

# recursively fetch data for each Perpres
def get_data(number):
    url = f"https://jdih.setneg.go.id/front/Peraturan/ajaxview?id=P{number}"
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        "Connection": "keep-alive",
        "Cookie": "ci_session=kv2hv8mdm6gs0mdchsmlcnd6ht0imjjt; CSRFCookie=4ffc891559efa0785ba36b8be670eec8; TS01e7ed0b=01f94ebe60b87597a0eea9571c292494bf84f5766b05ca5d46d6c14b4633805abfe98071f51e09f4e6dec3bdd8c8624ddf90cc2a5c55c90d978a85e4476a62d9f2cb8302cbbbc27fcecc5f0f053f6efa6f54b81f79; TSca2e059f027=086c094b6eab20009e0b3a333bfe010375d02efd919dc847ee953cdce7e72d7b6019f792e5a19ff40855ed9a3d11300068da1a6199230e5d01900fa6da46e1479adb9d6c309900bff0bee8cebc93d5b6e3052656e6fd19bdc9a05e6f418c62b0",
        "Host": "jdih.setneg.go.id",
        "Referer": "https://jdih.setneg.go.id/Terbaru",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"'
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch data for number {number}. Status code: {response.status_code}")
        return None

    try:
        data = response.json()
    except ValueError:
        print(f"Failed to parse JSON response for number {number}")
        return None

    if not isinstance(data, dict):
        print(f"Unexpected data format for number {number}: {data}")
        return None

    if data.get('data') is None:
        print(f"No data available for number {number}.")
        set_json(number)
        return None

    if 'tentang' not in data['data']:
        print(f"Missing 'tentang' key in 'data' for number {number}")
        return None

    title_data = data['data']['tentang']

    if title_data is None:
        print(f"Title data is None for number {number}. Stopping recursion.")
        return None

    title_data = title_data.title()
    
    if "Tunjangan Kinerja" in title_data and "Pembayaran" not in title_data:
        date_data = data.get('data', {}).get('tgl_di', '')
        date_obj = datetime.strptime(date_data, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d %B %Y')
        year = date_obj.year
        peraturan_name = data.get('data', {}).get('tentang', '')
        no_data = data.get('data', {}).get('no_peraturan', '')
        url_data = data.get('datafile', [{}])[0].get('url2', '')
        url_name = data.get('datafile', [{}])[0].get('basename', '')
        number_data = 'P' + str(number)
        title_data = title_data.split("Lingkungan ", 1)[1]
        download_pdf(url_data, url_name, number_data)
        tukin_category = categorizeData(f"File/{url_name}")
        df = pd.DataFrame({'peraturan_number': int(no_data), 'peraturan_year': year, 'peraturan_title': peraturan_name, 'peraturan_download_id': 0,'peraturan_url_id': 0, 'pdf_url': "https://nubisub.github.io/remun-notifier/File/" + url_name, 'tukin_category': tukin_category, 'is_aktif':1}, index=[0])
        
        with open('README.md', 'a') as file:
            file.write(f"|[{title_data}](<File/{url_name}>) |`No {no_data}` | `{tukin_category}` |`{formatted_date}` |\n")
        send_email(f"Tukin Naik", title_data)
        insertData(df)
    return get_data(number + 1)

# send email with the title of the Perpres
def send_email(subject, body):
    sender_email = os.getenv('EMAIL_SENDER')
    receiver_email = os.getenv('EMAIL_RECEIVER')

    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    smtp_username = os.getenv('EMAIL_SENDER')
    smtp_password = os.getenv('PASSWORD')
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Enable security
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        print("Email sent successfully")

    except Exception as e:
        print(f"Failed to send email: {e}")

    finally:
        server.quit()

# download the PDF file and save it to the File folder
def download_pdf(url, name, number):
    csrf_token = "12be17607c5ab3c1fcb02fbeb6facd97"
    payload = {
        "CSRFToken": csrf_token,
        "f": number,
        "ts": name,
    }
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9,id;q=0.8",
        "connection": "keep-alive",
        "cookie": "ci_session=akbdg7llkm6ga1qbfisph0nrsgss6bh4; CSRFCookie=12be17607c5ab3c1fcb02fbeb6facd97; TS01e7ed0b=01f94ebe60c93fe24a5f13eacb0e4b9cb9f49c9161501389ec1626c558948dd877457c4246fa436a5e4c7299f259fb6ebbcb95736c232bdab5c4418e7e5fa2fb541e1d675e6a279bff8899bdd2477d912f62cec8f8; TSca2e059f027=086c094b6eab20002d2b34d434cba7aa34388d4b9f7a41dea0dd02b9cf124fda097c82e8524db70608585b7e4e1130003b7c795514e061542018585189a63f23bb10fbea9d44f9ece8acf558e46bb6ca4100412eab53bdf22130d556e5abb019",
        "host": "jdih.setneg.go.id",
        "referer": "https://jdih.setneg.go.id/Terbaru",
        "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest"
    }

    response = requests.post(url, data=payload, headers=headers)
    if response.status_code == 200:
        with open(f"File/{name}", "wb") as f:
            f.write(response.content)
    else:
        print(f"Failed to submit form. Status code: {response.status_code}")


# insert data to MongoDB
def insertData(df):
    uri = os.getenv('DB_URI')
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client.tukin
    collection = db.tukin
    requesting = []
    for i in range(0, len(df)):
        requesting.append(InsertOne(df.iloc[i].to_dict()))
    try:
        result = collection.bulk_write(requesting)
    except pymongo.errors.BulkWriteError as bwe:
        print(bwe.details)
    client.close()
    return result

# Categories the data based on the last page of the PDF
def categorizeData(path):
    with pdfplumber.open(path) as pdf:
        last_page = len(pdf.pages)
        page = pdf.pages[last_page - 1]
        text = page.extract_text()
        
        if '563' in text:
            return 1
        elif '766' in text:
            return 2
        elif '968' in text:
            return 3
        elif '531' in text:
            return 4
        elif '575' in text:
            return 5
        elif '924' in text:
            return 0
        else:
            return 6

def main():
    try:
        with open('number.json', 'r') as file:
            data = json.load(file)
            number = data.get('number', 1)
    except (FileNotFoundError, json.JSONDecodeError):
        number = 1

    get_data(number)

if __name__ == "__main__":
    main()
