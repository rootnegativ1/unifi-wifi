"""QR code images creation function."""

import qrcode
import qrcode.image.svg # required for svg support

IMG_PATH = '/config/www'
#FILETYPES = ['png', 'svg']
FILETYPES = ['png']


def create(coordinator_name, ssid, password):
    qrtext = f"WIFI:T:WPA;S:{ssid};P:{password};;"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=16,
        border=2
    )
    qr.add_data(qrtext)
    qr.make(fit=True)

    for x in FILETYPES:
        ext = x.lower()
        if ext == 'svg':
            #img = qr.make_image(fill_color='black', back_color='white', image_factory=qrcode.image.svg.SvgPathImage)
            img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
        else:
            # fill_color defaults to black and back_color defaults to white
            #    so there's no need to pass them as arguments in make_image() method
            #    https://github.com/lincolnloop/python-qrcode/blob/main/qrcode/image/pil.py#L12
            #img = qr.make_image(fill_color='black', back_color='white')
            img = qr.make_image()
        type(img)
        path = f"{IMG_PATH}/{coordinator_name}_{ssid}_wifi_qr.{ext}"
        img.save(path)