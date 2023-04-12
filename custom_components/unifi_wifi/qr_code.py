import qrcode, qrcode.image.svg

wwwPath = '/config/www/'

def create(ssid, password):
    qrtext = f"WIFI:T:WPA;S:{ssid};P:{password};;"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=16,
        border=2 )
    qr.add_data(qrtext)
    qr.make(fit=True)

    # GENERATE QR CODE IMAGES
    img_png = qr.make_image(fill_color='black', back_color='white')
    type(img_png)
    pngPath = f"{wwwPath}{ssid}_wifi_qr.png"
    img_png.save(pngPath)
    img_svg = qr.make_image(fill_color='black', back_color='white', image_factory=qrcode.image.svg.SvgPathImage)
    type(img_svg)
    svgPath = f"{wwwPath}{ssid}_wifi_qr.svg"
    img_svg.save(svgPath)
