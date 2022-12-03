import base64
import io
import json
import os
import uuid

import requests
from PIL import Image

requests_session = requests.session()


def get_base64_image(path: str | io.BytesIO) -> str:
    if isinstance(path, io.BytesIO):
        b64_string = base64.b64encode(path.getvalue())
    else:
        with open(path, "rb") as img_file:
            b64_string = base64.b64encode(img_file.read())
    return b64_string.decode()


def get_ai_image(b64_image_string: str):
    request_url = "https://ai.tu.qq.com/trpc.shadow_cv.ai_processor_cgi.AIProcessorCgi/Process"
    request_headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "ru,uk-UA;q=0.8,uk;q=0.6,en-US;q=0.4,en;q=0.2",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Length": "448320",
        "Content-Type": "application/json",
        "Cookie": "pac_uid=0_ce27c744a8be3; iip=0; pgv_info=ssid=s2755604992; pgv_pvid=9635260140; ariaDefaultTheme=undefined",
        "Host": "ai.tu.qq.com",
        "Origin": "https://h5.tu.qq.com",
        "Pragma": "no-cache",
        "Referer": "https://h5.tu.qq.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",
    }
    request_cookies = {
        "pac_uid": "0_ce27c744a8be3",
        "iip": "0",
        "pgv_info": "ssid=s2755604992",
        "pgv_pvid": "9635260140",
        "ariaDefaultTheme": "undefined"
    }
    requests_json = {
        "busiId": "ai_painting_anime_entry",
        "images": [b64_image_string],
        "extra": "{\"face_rects\":[],\"version\":2,\"platform\":\"web\",\"data_report\":{\"parent_trace_id\":\"323b8a31-2487-494c-6d0e-3baabf3c608a\",\"root_channel\":\"\",\"level\":0}}"
    }
    response = requests.post(
        url=request_url,
        headers=request_headers,
        cookies=request_cookies,
        json=requests_json,
    )
    text = response.text
    try:
        text = json.loads(text)['extra']
        text = json.loads(text)
        text = list(set(text['img_urls']))
    except Exception:
        print(text)
        raise Exception

    for url in text:
        if url.startswith('https://act-artifacts'):
            return url
    return text[0]


def download_image(url) -> Image.Image:
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError
    path: str = f'GENERATED_IMGS\\{str(uuid.uuid4())}.jpg'
    path = os.path.join(os.path.abspath(os.getcwd()), path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(response.content)
    image = Image.open(path)
    image.filename = path
    return image
