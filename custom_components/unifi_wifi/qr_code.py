"""QR code images creation function."""

import qrcode

IMG_PATH = '/config/www'


def create(controller_name, site_name, ssid, password):
    qrtext = f"WIFI:T:WPA;S:{ssid};P:{password};;"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=16,
        border=2 )
    qr.add_data(qrtext)
    qr.make(fit=True)

    # GENERATE QR CODE IMAGE(s)
    img_png = qr.make_image(fill_color='black', back_color='white')
    type(img_png)
    pngPath = f"{IMG_PATH}/{controller_name}_{site_name}_{ssid}_wifi_qr.png"
    img_png.save(pngPath)

    # img_svg = qr.make_image(fill_color='black', back_color='white', image_factory=qrcode.image.svg.SvgPathImage)
    # type(img_svg)
    # svgPath = f"{IMG_PATH}/{controller_name}_{site_name}_{ssid}_wifi_qr.svg"
    # img_svg.save(svgPath)