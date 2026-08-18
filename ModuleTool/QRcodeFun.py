import qrcode
from PIL import Image
import zxingcpp

# 生成二维码：字符串 → PIL图像对象
def generate_qr(text: str,
        fill_color: str = "#000000",  # 前景色（二维码图案颜色），默认黑色
        back_color: str = "#ffffff"  # 背景色，默认白色
    ) -> Image.Image:
    qr = qrcode.main.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(text)
    qr.make(fit=True)
    return qr.make_image(fill_color=fill_color, back_color=back_color).convert("RGB")


# 解析二维码：PIL图像对象 → 字符串
def decode_qr(image: Image.Image) -> str:
    """输入PIL Image，识别失败返回空字符串"""
    result = zxingcpp.read_barcode(image)
    if result is not None:
        return result.text
    return ""


if __name__ == '__main__':
    qr_img = generate_qr("你好，这是测试数据！123456")
    qr_img.show()
    content = decode_qr(qr_img)
    print("解析结果：", content)
