from PIL import Image, ImageDraw


# デフォルトの座標比率（基準: 2560 x 1440）
# 左下: (1, 1438), 右上: (236, 1416)
DEFAULT_RATIOS = {
    'bl_x': 1 / 2560,       # 0.000390625
    'bl_y': 1438 / 1440,    # 0.998611...
    'tr_x': 236 / 2560,     # 0.0921875
    'tr_y': 1416 / 1440,    # 0.983333...
}


def calculate_grid_coords(width, height, ratios=None):
    """
    画像サイズから座標を計算する

    Args:
        width: 画像の幅
        height: 画像の高さ
        ratios: 座標比率（省略時はDEFAULT_RATIOS）

    Returns:
        tuple: (bottom_left, top_right) - それぞれ (x, y) のタプル
    """
    if ratios is None:
        ratios = DEFAULT_RATIOS

    bl_x = int(round(width * ratios['bl_x']))
    bl_y = int(round(height * ratios['bl_y']))
    tr_x = int(round(width * ratios['tr_x']))
    tr_y = int(round(height * ratios['tr_y']))

    return (bl_x, bl_y), (tr_x, tr_y)


def decode_vrchat_camera_grid(
    image_path,
    bottom_left,  # (x,y) 左下のドット座標
    top_right,  # (x,y) 右上のドット座標
    precision=8,
    debug_output=False,
    use_full_data=True,  # True: 7行（CameraFullData）、False: 3行（従来版）
):
    """
    VRChatカメラグリッドをデコードする

    Args:
        image_path: 画像ファイルパス
        bottom_left: 左下のドット座標 (x, y)
        top_right: 右上のドット座標 (x, y)
        precision: 小数部の精度（デフォルト8桁）
        debug_output: デバッグ画像を出力するか
        use_full_data: True=7行モード（ワールドコード+位置+回転）、False=3行モード（位置のみ）

    Returns:
        7行モード: {"world_code": int, "x": float, "y": float, "z": float,
                    "rot_x": float, "rot_y": float, "rot_z": float}
        3行モード: {"x": float, "y": float, "z": float}
        失敗時: None
    """
    img = Image.open(image_path)
    pixels = img.load()
    width, height = img.size

    # 試行する変換パターン
    transforms = ["none", "rotate180", "flip_h", "flip_v"]

    for transform in transforms:
        result = try_decode_with_transform(
            img,
            pixels,
            width,
            height,
            bottom_left,
            top_right,
            transform,
            precision,
            debug_output,
            image_path,
            use_full_data,
        )

        if result is not None:
            if debug_output:
                print(f"Successfully decoded with transform: {transform}")
            return result

    # すべて失敗
    if debug_output:
        print("Failed to decode with any transform")
    return None


def transform_coords(x, y, width, height, transform_type):
    """座標を変換する"""
    if transform_type == "none":
        return x, y
    elif transform_type == "rotate180":
        return width - 1 - x, height - 1 - y
    elif transform_type == "flip_h":
        return width - 1 - x, y
    elif transform_type == "flip_v":
        return x, height - 1 - y
    else:
        return x, y


def try_decode_with_transform(
    img,
    pixels,
    width,
    height,
    bottom_left,
    top_right,
    transform,
    precision,
    debug_output,
    image_path,
    use_full_data,
):
    # 座標を変換
    bl_x, bl_y = transform_coords(
        bottom_left[0], bottom_left[1], width, height, transform
    )
    tr_x, tr_y = transform_coords(top_right[0], top_right[1], width, height, transform)

    COLS = 66
    ROWS = 7 if use_full_data else 3

    # 間隔計算（変換後の座標を直接使用）
    spacing_x = (tr_x - bl_x) / (COLS - 1)
    spacing_y = (tr_y - bl_y) / (ROWS - 1)

    # ドット座標生成（変換後の座標を基準に）
    dot_positions = []
    for row in range(ROWS):
        for col in range(COLS):
            x = bl_x + col * spacing_x
            y = bl_y + row * spacing_y
            dot_positions.append((int(round(x)), int(round(y))))

    # ビット判定
    def is_bit_set(dot_index):
        x, y = dot_positions[dot_index]
        if x < 0 or y < 0 or x >= width or y >= height:
            return False
        pixel = pixels[x, y]
        if isinstance(pixel, tuple):
            brightness = sum(pixel[:3]) / 3
        else:
            brightness = pixel
        return brightness > 127

    # 行デコード
    def decode_row(row_index):
        base = row_index * COLS

        # 灰色マーカー確認（0列目）
        dot_pos = dot_positions[base]
        x, y = dot_pos

        if x < 0 or y < 0 or x >= width or y >= height:
            return None

        pixel = pixels[x, y]

        if isinstance(pixel, tuple) and len(pixel) >= 3:
            r, g, b = pixel[:3]
            if not (118 <= r <= 138 and 118 <= g <= 138 and 118 <= b <= 138):
                return None

        # 符号ビット（1列目）
        sign = 1 if is_bit_set(base + 1) else -1

        # 整数部（2〜33列目：32ビット）
        integer_bits = "".join(
            "1" if is_bit_set(base + col) else "0" for col in range(2, 34)
        )

        # 小数部（34〜65列目：32ビット）
        fractional_bits = "".join(
            "1" if is_bit_set(base + col) else "0" for col in range(34, 66)
        )

        integer_part = int(integer_bits, 2)
        fractional_part = int(fractional_bits, 2) / (10**precision)

        return sign * (integer_part + fractional_part)

    # デコード結果を格納
    if use_full_data:
        # 7行モード: 行0=ワールドコード, 行1-3=位置, 行4-6=回転
        # 変換タイプに応じて行インデックスを調整
        if transform in ["rotate180", "flip_v"]:
            row_mapping = {
                "world_code": 0,
                "x": 1, "y": 2, "z": 3,
                "rot_x": 4, "rot_y": 5, "rot_z": 6
            }
        else:
            row_mapping = {
                "world_code": 0,
                "x": 1, "y": 2, "z": 3,
                "rot_x": 4, "rot_y": 5, "rot_z": 6
            }

        decoded_values = {}
        for key, row_idx in row_mapping.items():
            value = decode_row(row_idx)
            if value is None:
                decoded_values[key] = None
            elif key == "world_code":
                # ワールドコードは整数部のみ使用（絶対値）
                decoded_values[key] = abs(int(value))
            else:
                decoded_values[key] = value
    else:
        # 3行モード: 従来の位置のみ
        if transform in ["rotate180", "flip_v"]:
            row_mapping = {"z": 0, "y": 1, "x": 2}
        else:
            row_mapping = {"z": 0, "y": 1, "x": 2}

        decoded_values = {
            "x": decode_row(row_mapping["x"]),
            "y": decode_row(row_mapping["y"]),
            "z": decode_row(row_mapping["z"])
        }

    # デバッグ出力
    if debug_output:
        debug_img = img.copy()
        draw = ImageDraw.Draw(debug_img)

        # すべてのドット位置にマーカー
        for idx, (dx, dy) in enumerate(dot_positions):
            row_idx = idx // COLS
            col_idx = idx % COLS

            # 範囲外チェック
            if dx < 0 or dy < 0 or dx >= width or dy >= height:
                continue

            # マーカー色を役割別に分ける
            if col_idx == 0:  # 灰色マーカー列
                color = (255, 0, 255)  # マゼンタ
            elif col_idx == 1:  # 符号ビット列
                color = (255, 255, 0)  # 黄色
            elif 2 <= col_idx <= 33:  # 整数部
                color = (0, 255, 0)  # 緑
            else:  # 小数部
                color = (0, 0, 255)  # 青

            # 実際に取得している1ピクセルだけにマーク
            draw.point((dx, dy), fill=color)

        # ファイル名に変換タイプを追加
        debug_path = image_path.replace(".png", f"_debug_{transform}.png")
        debug_img.save(debug_path)
        print(f"Debug image saved: {debug_path}")
        print(f"  Decoded values: {decoded_values}")

    # 全行マーカーありの確認
    if all(v is not None for v in decoded_values.values()):
        return decoded_values

    return None


def decode_world_code_only(
    image_path,
    bottom_left,
    top_right,
    debug_output=False,
):
    """
    ワールドコードのみをデコードする（軽量版）

    Returns:
        int: ワールドコード（成功時）
        None: 失敗時
    """
    result = decode_vrchat_camera_grid(
        image_path,
        bottom_left,
        top_right,
        precision=8,
        debug_output=debug_output,
        use_full_data=True,
    )

    if result and "world_code" in result:
        return result["world_code"]
    return None


# 使用例
if __name__ == "__main__":
    # 7行モード（CameraFullData）
    result = decode_vrchat_camera_grid(
        "test_image.png",
        bottom_left=(100, 500),
        top_right=(600, 200),
        precision=8,
        debug_output=True,
        use_full_data=True,
    )

    if result:
        print(f"Decoded data (7-row mode):")
        print(f"  World Code: {result.get('world_code')}")
        print(f"  Position: ({result.get('x')}, {result.get('y')}, {result.get('z')})")
        print(f"  Rotation: ({result.get('rot_x')}, {result.get('rot_y')}, {result.get('rot_z')})")
    else:
        print("Failed to decode (7-row mode)")

    # 3行モード（従来版）
    result_legacy = decode_vrchat_camera_grid(
        "test_image.png",
        bottom_left=(100, 500),
        top_right=(600, 200),
        precision=8,
        debug_output=True,
        use_full_data=False,
    )

    if result_legacy:
        print(f"Decoded coordinates (3-row mode): {result_legacy}")
    else:
        print("Failed to decode (3-row mode)")
