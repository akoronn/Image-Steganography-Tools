from cryptography.fernet import Fernet, InvalidToken
from PIL import Image
from pathlib import Path
import random
import os
import sys
import zlib

HEADER_SIZE_BITS = 24
FLAG_SIZE_BITS = 1

def embed_image(image, bin_data, is_encryption):
    image = image.convert('RGBA')
    width, height = image.size

    channels_per_pixel = 3
    capacity = width * height * channels_per_pixel
    required_bits = HEADER_SIZE_BITS +  FLAG_SIZE_BITS + len(bin_data) * 8

    if capacity < required_bits:
        raise ValueError("Error: The file size is too large for the image.")
    
    bits = ""

    # データ量 (24bits)
    bits += format(len(bin_data), "024b")

    # 暗号フラグ (1bit)s
    bits += str(int(is_encryption))

    # 本文
    for byte in bin_data:
        bits += format(byte, "08b")

    pixels = image.load()

    for i in range(len(bin_data)):
        pass

    for idx, bit in enumerate(bits):
        pixel_idx = idx // channels_per_pixel
        c_idx = idx % channels_per_pixel

        y = pixel_idx // width
        x = pixel_idx % width

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


def text_extract(image):
    image = image.convert("RGBA")
    width, height = image.size

    channels_per_pixel = 3
    pixels = image.load()

    is_encryption = False

    idx = 0
    current_val = 0
    bit_count = 0

    max_bytes = 0
    bin_data = bytearray()

    for y in range(height):
        for x in range(width):
            pixel = pixels[x, y]

            for c_idx in range(channels_per_pixel):
                channel = pixel[c_idx]

                current_val = (current_val << 1) | (channel % 2)
                bit_count += 1

                # 先頭32bit = サイズ
                if idx == HEADER_SIZE_BITS - 1:
                    max_bytes = current_val

                    current_val = 0
                    bit_count = 0

                # 次の1bit = 暗号化フラグ
                elif idx == HEADER_SIZE_BITS:
                    is_encryption = bool(current_val)

                    current_val = 0
                    bit_count = 0

                # 本文
                elif idx >= HEADER_SIZE_BITS + FLAG_SIZE_BITS:
                    if bit_count == 8:
                        bin_data.append(current_val)

                        current_val = 0
                        bit_count = 0

                        if len(bin_data) == max_bytes:
                            return bytes(bin_data), is_encryption

                idx += 1

    return bytes(bin_data), is_encryption

def main():
    args = sys.argv

    if len(args) < 2 or args[1] == "help":
        print(
        """
    Image Steganography Tools ver 1.0
        
    Usage:
        stego embed <STRING or PATH> <IMAGE PATH> [--encrypt]
        stego extract <IMAGE PATH>

    Commands:
        embed      Embed text or a file into an image
        extract    Extract data from an image
        help       Help about any command

    Options:
        --encrypt  Encrypt embedded data
    
    """)
        
    elif args[1] == "embed":
        if len(args) < 4:
            print("Error: Missing arguments.")
            sys.exit(1)
        
        STRING_PATH = args[2].strip('"\' ')
        IMAGE_PATH = args[3].strip('"\' ')
        OPTION = args[4] if len(args) >= 5 else ""

        if os.path.exists(STRING_PATH):
            with open(STRING_PATH, "rb") as f:
                original_data = f.read()
        else:
            original_data = STRING_PATH

        compressed_data = zlib.compress(original_data)

        if os.path.exists(IMAGE_PATH):
            IMAGE_PATH = Path(IMAGE_PATH)
            image = Image.open(IMAGE_PATH)
        else:
            print("Error: Couldn't find Image Path.")
            sys.exit(1)
        
        if OPTION == "--encrypt":
            key = Fernet.generate_key()
            f = Fernet(key)
            encrypted_data = f.encrypt(compressed_data)
            is_encryption = True
        else:
            encrypted_data = compressed_data
            is_encryption = False

        stg_image = embed_image(
        image,
        encrypted_data,
        is_encryption
        )

        save_path = IMAGE_PATH.parent / f"stg_{IMAGE_PATH.stem}.png"
        stg_image.save(save_path)
        print(f"Saved to {save_path}.")
        
        if is_encryption:
            print(f"Encryption Key: {key.decode('utf-8')}.")

    elif args[1] == "extract":
        if len(args) < 3:
            print("Error: Missing image path.")
            sys.exit(1)
        
        IMAGE_PATH = args[2].strip('"\' ')
        
        if os.path.exists(IMAGE_PATH):
            IMAGE_PATH = Path(IMAGE_PATH)
            stg_image = Image.open(IMAGE_PATH)
        else:
            print("Error: Couldn't open Image Path.")
            sys.exit(1)
        
        extracted_bytes, is_encryption = text_extract(stg_image)

        try:
            if is_encryption:
                key = input("Input Encryption Key:\n> ").strip()
                f = Fernet(key.encode("utf-8"))
                extracted_bytes = f.decrypt(extracted_bytes)

            extracted_bytes = zlib.decompress(extracted_bytes)

        except InvalidToken:
            print("Error: Invalid encryption key.")
            sys.exit(1)

        except zlib.error:
            print("Error: Failed to decompress.")
            sys.exit(1)
        
        try:
            text = extracted_bytes.decode("utf-8")

            print("Message decode successful.")
            print(
            f"""
            Message:
                  
              {text}

            """)

        except UnicodeDecodeError:
            save_path = Path("extracted.bin")

            with open(save_path, "wb") as f:
                binary = f.write(extracted_bytes)

            print("Binary decode successful.")
            print(f"Binary: {binary}")

if __name__ == "__main__":
    main()