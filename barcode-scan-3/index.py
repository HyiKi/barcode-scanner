import base64
import io
import json
import logging

from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader
from pyzbar import pyzbar
from urllib.request import Request, urlopen


def convert_pdf_to_img(filebytes):
    pages = convert_from_bytes(filebytes)
    image_array = []
    for page in pages:
        # Convert PIL image to OpenCV format
        image = __np().array(page)
        image_array.append(image)
    return image_array


def __np():
    import numpy as np

    return np


def __cv2():
    import cv2

    return cv2


def __requests():
    try:
        import requests

        return requests
    except Exception as e:
        # FC 环境里 requests/urllib3 layer 可能不完整；失败则降级到 urllib.request
        print(f"requests import failed: {e}")
        return None


def __zxingcpp():
    try:
        import zxingcpp

        return zxingcpp
    except Exception as e:
        print(f"zxingcpp import failed: {e}")
        return None


def __fetch_bytes(url: str):
    req = Request(url, headers={"User-Agent": "barcode-scanner/1.0"})
    with urlopen(req, timeout=30) as resp:
        content_type = resp.headers.get("Content-Type")
        return resp.read(), content_type


def is_valid_pdf_file(filebytes):
    try:
        b = io.BytesIO(filebytes)
        reader = PdfReader(b)
        return len(reader.pages) > 0  # 进一步通过页数判断。
    except Exception:
        return False


def decode(url):
    # File
    file_path = url

    try:
        cv2 = __cv2()
        np = __np()
    except Exception as e:
        # 避免 FC 在 import handler 阶段直接崩溃：cv2 只在需要时加载
        print(f"opencv import failed: {e}")
        return []

    # 图片处理
    requests = __requests()
    if requests is not None:
        response = requests.get(file_path, timeout=30)
        filebytes = response.content
        # 获取Content-Type字段
        content_type = response.headers.get("Content-Type")
    else:
        filebytes, content_type = __fetch_bytes(file_path)

    # 存储结果
    result = []

    # 如果是pdf需要转换成图片
    if content_type and "pdf" in content_type:
        # 如果是pdf需要判断是否合法
        if is_valid_pdf_file(filebytes) is False:
            print(f"invalid pdf file: {file_path}")
            return result
        image_array = convert_pdf_to_img(filebytes)
    else:
        image_array = np.asarray(bytearray(filebytes), dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        image_array = [image]

    print(f"image count: {len(image_array)}")

    try:
        zxingcpp = __zxingcpp()
        for image in image_array:
            found_any = False

            # 1) Prefer ZXing (更抗干扰)
            if zxingcpp is not None:
                try:
                    zx_barcodes = zxingcpp.read_barcodes(image)
                except Exception as e:
                    print(f"zxingcpp read_barcodes failed: {e}")
                    zx_barcodes = []

                for barcode in zx_barcodes:
                    barcode_data = getattr(barcode, "text", "") or ""
                    barcode_type = str(getattr(barcode, "format", "")) or "UNKNOWN"
                    if barcode_data:
                        result.append(
                            {"barcode_data": barcode_data, "barcode_type": barcode_type}
                        )
                        found_any = True

            # 2) Fallback to pyzbar (兼容旧行为)
            if not found_any:
                gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                barcodes = pyzbar.decode(gray_image)
                for barcode in barcodes:
                    barcode_data = barcode.data.decode("utf-8")
                    barcode_type = barcode.type
                    result.append(
                        {"barcode_data": barcode_data, "barcode_type": barcode_type}
                    )
                    print(f"Barcode Data: {barcode_data}, Barcode Type: {barcode_type}")
    except Exception:
        print(f"image parse exception filepath: {file_path}")
        raise

    return result


def render(url):
    result_dict = {}
    result_dict["code"] = "SUCCESS"
    result_dict["msg"] = "success"
    result_dict["data"] = decode(url)
    return json.dumps(result_dict)


def handler(event, context):
    logger = logging.getLogger()
    logger.info("receive event: %s", event)

    try:
        event_json = json.loads(event)
    except Exception:
        return "The request did not come from an HTTP Trigger because the event is not a json string, event: {}".format(
            event
        )

    if "body" not in event_json:
        return "The request did not come from an HTTP Trigger because the event does not include the 'body' field, event: {}".format(
            event
        )

    req_body = event_json["body"]
    if "isBase64Encoded" in event_json and event_json["isBase64Encoded"]:
        req_body = base64.b64decode(event_json["body"]).decode("utf-8")

    body = json.loads(req_body)
    url = body["url"]

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json;charset=utf-8"},
        "isBase64Encoded": False,
        "body": render(url),
    }

