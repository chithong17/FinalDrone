"""Generate labelled SYNTHETIC fixture; never a field accuracy dataset."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def create(path):
    image = Image.new('RGB', (640,480), '#303030')
    draw = ImageDraw.Draw(image)
    draw.rectangle((160,260,480,460), fill=(240,120,10))
    draw.rectangle((224,300,416,380), fill='white')
    font_path = Path('C:/Windows/Fonts/arialbd.ttf')
    font = ImageFont.truetype(str(font_path), 64) if font_path.exists() else ImageFont.load_default(size=64)
    draw.text((320,340), '17', fill='black', font=font, anchor='mm')
    image.save(path, 'JPEG', quality=95)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='fixtures')
    args = parser.parse_args()
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=True)
    create(folder/'synthetic-chair-17.jpg')
    print('SYNTHETIC fixture generated; bbox=[160,260,480,460], number=17, example floor=1 EAST')
