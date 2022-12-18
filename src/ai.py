import base64
import hashlib
import io
import json
import os
import uuid

import requests
from PIL import Image

requests_session = requests.Session()


def get_base64_image(path: str | io.BytesIO) -> str:
    if isinstance(path, io.BytesIO):
        return base64.b64encode(path.getvalue()).decode()

    with open(path, "rb") as img_file:
        b64_string = base64.b64encode(img_file.read()).decode()
    return b64_string


def _get_x_sign_value(request_json):
    string_json = json.dumps(request_json)
    return hashlib.md5(f'https://h5.tu.qq.com{len(string_json)}HQ31X02e'.encode()).hexdigest()


def get_ai_image(b64_image_string: str, version=2):
    request_url = "https://ai.tu.qq.com/trpc.shadow_cv.ai_processor_cgi.AIProcessorCgi/Process"
    request_json = {
        "busiId": "different_dimension_me_img_entry",
        "images": [b64_image_string],
        "extra": '{\"face_rects\":[],\"version\":' + f'{version}' + ',\"platform\":\"web\",\"data_report\":{\"parent_trace_id\":\"' + f'{uuid.uuid4()}' + '\", \"root_channel\":\"\",\"level\":0}}'
    }
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
        'x-sign-value': _get_x_sign_value(request_json),
        'x-sign-version': 'v1',
    }
    response = requests_session.post(
        url=request_url,
        headers=request_headers,
        json=request_json,
    )

    text = response.text
    try:
        text = json.loads(text)['extra']
        text = json.loads(text)
        text = list(set(text['img_urls']))
    except Exception:
        print(text)
        raise Exception
    return text[0]


def crop_image(image: Image.Image) -> Image.Image:
    left = 20
    top = 22
    right = image.width - 22
    bottom = image.height - 210
    if image.width == 1_000:  # Vertical Image
        left += 472
        left += 16
    else:  # Horizontal Image
        top += 504
        top += 17
    cropped_image = image.crop((left, top, right, bottom))
    return cropped_image


def download_image(url) -> Image.Image:
    response = requests_session.get(url)
    if response.status_code != 200:
        raise ValueError
    path: str = f'GENERATED_IMGS\\{str(uuid.uuid4())}.jpg'
    path = os.path.join(os.path.abspath(os.getcwd()), path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(response.content)
    image = Image.open(path)
    cropped_image = crop_image(image)
    cropped_image.filename = path
    image.close()
    return cropped_image
