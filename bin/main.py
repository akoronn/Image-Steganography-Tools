from PIL import Image
from pathlib import Path
import random
import os
import sys
import zlib

IDENTIFIER_BITS = 40
DATA_SIZE_BITS = 24

def embed_image(image, text, seed):
    if isinstance(text, str):
        text = text.encode('utf-8')
    bin_data = zlib.compress(text)

    image = image.convert('RGB')
    width, height = image.size

    channels_per_pixel = 3
    capacity = width * height * channels_per_pixel
    HEADER_BITS = IDENTIFIER_BITS + DATA_SIZE_BITS
    required_bits = HEADER_BITS + len(bin_data) * 8

    if capacity < required_bits:
        raise ValueError("Error: The file size is too large for the image.")
    
    # 識別子 (40bits)
    bits = ''.join(format(b, '08b') for b in b"stego")

    # データ量 (24bits)
    bits += format(len(bin_data), "024b")

    # 本文
    for byte in bin_data:
        bits += format(byte, "08b")

    # シードからランダムな座標を生成
    rng = random.Random(seed)
    indices = list(range(width * height))
    rng.shuffle(indices)
    pos = indices[:(len(bits) + 2) // 3]
    pixels = image.load()
    
    # ビット埋め込み
    for idx, bit in enumerate(bits):
        p_idx, c_idx = divmod(idx, channels_per_pixel)

        i = pos[p_idx]
        y, x = divmod(i, width)

        color = list(pixels[x, y])
        channel = color[c_idx]

        # LSB書き換え
        if bit == "1":
            if channel % 2 == 0:
                channel = channel + 1 if channel < 255 else channel - 1
        else:
            if channel % 2 != 0:
                channel -= 1

        color[c_idx] = channel
        pixels[x, y] = tuple(color)

    return image


def text_extract(image, seed):
    image = image.convert("RGB")
    width, height = image.size

    HEADER_BITS = IDENTIFIER_BITS + DATA_SIZE_BITS
    channels_per_pixel = 3
    pixels = image.load()

    # --- ヘッダーの読み込み ---
    rng = random.Random(seed)
    indices = list(range(width * height))
    rng.shuffle(indices)
    total_header_pixels = (HEADER_BITS + 2) // 3
    pos = indices[:total_header_pixels]

    bits = ""
    for idx in range(HEADER_BITS):
        p_idx, c_idx = divmod(idx, channels_per_pixel)
        
        i = pos[p_idx]
        y, x = divmod(i, width)

        color = list(pixels[x, y])
        channel = color[c_idx]

        bits += str(channel % 2)
    
    if bits[:IDENTIFIER_BITS] != ''.join(format(b, '08b') for b in b"stego"):
        return "This is not in stego format."

    data_size = int(bits[IDENTIFIER_BITS:HEADER_BITS], 2) * 8
    total_bits = HEADER_BITS + data_size
    pos = indices[:(total_bits + 2) // 3]

    # --- データ読み込み ---
    for idx in range(HEADER_BITS, HEADER_BITS + data_size):
        p_idx, c_idx = divmod(idx, channels_per_pixel)

        i = pos[p_idx]
        y, x = divmod(i, width)

        color = list(pixels[x, y])
        channel = color[c_idx]

        bits += str(channel % 2)
    
    payload_bits = bits[HEADER_BITS:HEADER_BITS+data_size]
    data = int(payload_bits, 2).to_bytes((len(payload_bits) + 7) // 8, 'big')

    text = zlib.decompress(data)

    return text


def main():
    args = sys.argv

    if len(args) < 2 or args[1] == "help":
        print(
        """
    Image Steganography Tools ver 2.0.0
        
    Usage:
        stego embed <PATH or STRING> <IMAGE PATH> <INT or STRING>
        stego extract <IMAGE PATH> <INT or STRING>

    Commands:
        embed      Embed text or a file into an image
        extract    Extract data from an image
        help       Help about any command
    """)
        
    elif args[1] == "embed":
        if len(args) < 5:
            print("Error: Missing arguments.")
            sys.exit(1)
        
        STRING_PATH = args[2].strip('"\' ')
        IMAGE_PATH = args[3].strip('"\' ')
        SEED = (
            int(args[4].strip('"\' '))
            if args[4].strip('"\' ').isdigit()
            else int.from_bytes(
            args[4].strip('"\' ').encode('utf-8'),
            'big'
            )
        )

        # 平文取得
        if os.path.exists(STRING_PATH):
            with open(STRING_PATH, "rb") as f:
                text = f.read()
        else:
            text = STRING_PATH

        # 画像取得
        if os.path.exists(IMAGE_PATH):
            IMAGE_PATH = Path(IMAGE_PATH)
            image = Image.open(IMAGE_PATH)
        else:
            base_dir = Path(__file__).resolve().parent
            IMAGE_PATH = base_dir / "image.png"
            image = Image.open(IMAGE_PATH)

        stg_image = embed_image(image, text, seed=SEED)

        # 保存
        save_path = IMAGE_PATH.parent / f"stg_{IMAGE_PATH.stem}.png"
        stg_image.save(save_path)
        print(f"Saved to {save_path}.")

    elif args[1] == "extract":
        if len(args) < 4:
            print("Error: Missing image path.")
            sys.exit(1)
        
        IMAGE_PATH = args[2].strip('"\' ')
        SEED = (
            int(args[3].strip('"\' '))
            if args[3].strip('"\' ').isdigit()
            else int.from_bytes(
            args[3].strip('"\' ').encode('utf-8'),
            'big'
            )
        )
        
        if os.path.exists(IMAGE_PATH):
            IMAGE_PATH = Path(IMAGE_PATH)
            stg_image = Image.open(IMAGE_PATH)
        else:
            print("Error: Couldn't open Image Path.")
            sys.exit(1)
        
        extracted = text_extract(stg_image, seed=SEED)

        try:
            text = extracted.decode("utf-8")
            print()
            print("Extracted Text:")
            print(text)
            print()

        except UnicodeDecodeError:
            save_path = Path("extracted.bin")
            with open(save_path, "wb") as f:
                f.write(extracted)
            print(f"Binary saved to {save_path}.")

if __name__ == "__main__":
    main()