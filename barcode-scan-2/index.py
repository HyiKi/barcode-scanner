import json
import cv2
import numpy as np
import requests
from pyzbar import pyzbar
from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader
import io

def convert_pdf_to_img(filebytes):
    pages = convert_from_bytes(filebytes)
    image_array = []
    for page in pages:
        # Convert PIL image to OpenCV format
        image = np.array(page)
        image_array.append(image)
    return image_array

def is_valid_pdf_file(filebytes):
    try:
        b = io.BytesIO(filebytes)
        reader = PdfReader(b)
        return len(reader.pages) > 0 # 进一步通过页数判断。
    except:
        return False

def decode(url):
    # File
    file_path = url

    # 图片处理
    response = requests.get(file_path)
    filebytes = response.content

    # 获取Content-Type字段
    content_type = response.headers.get('Content-Type')

    # 存储结果
    result = []

    # 如果是pdf需要转换成图片
    if content_type and 'pdf' in content_type:
        # 如果是pdf需要判断是否合法
        if is_valid_pdf_file(filebytes) == False:
            print(f"invalid pdf file: {file_path}")
            return result
        image_array = convert_pdf_to_img(filebytes)
    else:
        image_array = np.asarray(bytearray(filebytes), dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        image_array = [image]

    print(f"image count: {len(image_array)}")

    try:
        for image in image_array:
            # Convert the image to grayscale
            gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Decode barcodes and QR codes
            barcodes = pyzbar.decode(gray_image)
            
            # Loop over the detected barcodes
            for barcode in barcodes:
                # Extract the barcode data
                barcode_data = barcode.data.decode("utf-8")
                barcode_type = barcode.type
                # 创建一个包含barcode_data和barcode_type的字典
                barcode_dict = {
                    "barcode_data": barcode_data,
                    "barcode_type": barcode_type
                }
                # 将字典添加到结果列表中
                result.append(barcode_dict)
                # Print the barcode data and type
                print(f"Barcode Data: {barcode_data}, Barcode Type: {barcode_type}")
    except:
        print(f"image parse exception filepath: {file_path}")
        raise

    return result

def render(url) :
    result_dict = {}
    result_dict['code'] = 'SUCCESS'
    result_dict['msg'] = 'success'
    result_dict['data'] = decode(url)
    return json.dumps(result_dict)

def handler(environ, start_response):
    # get request_body
    try:
        request_body_size = int(environ.get('CONTENT_LENGTH', 0))
    except (ValueError):
        request_body_size = 0
    request_body = environ['wsgi.input'].read(request_body_size)
    body = json.loads(request_body)
    url = body['url']
    # do something here

    status = '200 OK'
    response_headers = [('Content-type', 'application/json;charset=utf-8')]
    start_response(status, response_headers)
    # return value must be iterable
    return render(url)

# img
# file_path = 'https://qrstyle-api.cli.im/create/down?code_tplid=770542199&code_type=3&time=1699858621&publickey=b1ed8dc36e70ad49935e08c20634ee2c&cvid=996075441&fkey=1_996075441_171_85_3_770542199_98eba02eb7bc93eaef8fd278b0751152.png&file_name=cccccccccccccaow';
# pdf
# file_path = 'https://cider-erp-private.oss-cn-guangzhou.aliyuncs.com/waybill/UBILogistics/33G7K634463201000935108.pdf?Expires=1703755788&OSSAccessKeyId=LTAI4GBd1RZLC5HXUrADqNGs&Signature=JW0Z3nUaUzz7bLSQ3t7zqLPGaFs%3D';
# print(render(file_path))
# no pdf
# file_path = 'https://cider-erp-private.oss-cn-guangzhou.aliyuncs.com/waybill/Anjun/2767287029.pdf?Expires=1703705040&OSSAccessKeyId=LTAI4GBd1RZLC5HXUrADqNGs&Signature=NBeK1XCN%2F0PQp5DDK%2Bp8vCxOXgs%3D'
# print(render(file_path))
