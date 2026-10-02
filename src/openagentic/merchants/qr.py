"""Offline QR encoder for short storefront URLs (ISO QR version 6, level L).

Byte mode, two 68-byte data blocks and 18 Reed–Solomon parity bytes per block.
No remote image service, desktop dependency, or JavaScript CDN is used.
"""

SIZE = 41


def _multiply(a: int, b: int) -> int:
    result = 0
    for i in range(7, -1, -1):
        result = (result << 1) ^ ((result >> 7) * 0x11D)
        result ^= ((b >> i) & 1) * a
    return result


def _parity(data: list[int]) -> list[int]:
    divisor = [0] * 17 + [1]
    root = 1
    for _ in range(18):
        for j in range(18):
            divisor[j] = _multiply(divisor[j], root)
            if j + 1 < 18:
                divisor[j] ^= divisor[j + 1]
        root = _multiply(root, 2)
    remainder = [0] * 18
    for value in data:
        factor = value ^ remainder.pop(0)
        remainder.append(0)
        for j in range(18):
            remainder[j] ^= _multiply(divisor[j], factor)
    return remainder


def encode(text: str) -> list[list[bool]]:
    payload = text.encode("utf-8")
    if len(payload) > 134:
        raise ValueError("Storefront URL is too long for this QR encoder")
    bits: list[int] = []

    def append(value: int, count: int):
        bits.extend((value >> i) & 1 for i in range(count - 1, -1, -1))

    append(4, 4)
    append(len(payload), 8)
    for byte in payload:
        append(byte, 8)
    bits.extend([0] * min(4, 1088 - len(bits)))
    bits.extend([0] * ((-len(bits)) % 8))
    data = [sum(bits[i + j] << (7 - j) for j in range(8)) for i in range(0, len(bits), 8)]
    while len(data) < 136:
        data.append(0xEC if (len(data) - len(bits) // 8) % 2 == 0 else 0x11)
    blocks = [data[:68], data[68:]]
    parity = [_parity(block) for block in blocks]
    codewords = [block[i] for i in range(68) for block in blocks]
    codewords += [block[i] for i in range(18) for block in parity]
    stream = [(byte >> i) & 1 for byte in codewords for i in range(7, -1, -1)]
    matrix = [[False] * SIZE for _ in range(SIZE)]
    function = [[False] * SIZE for _ in range(SIZE)]

    def draw(x: int, y: int, value: bool):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            matrix[y][x] = value
            function[y][x] = True

    for i in range(SIZE):
        draw(6, i, i % 2 == 0)
        draw(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (SIZE - 4, 3), (3, SIZE - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                draw(cx + dx, cy + dy, max(abs(dx), abs(dy)) not in (2, 4))
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            draw(34 + dx, 34 + dy, max(abs(dx), abs(dy)) != 1)

    def format_bits(mask: int):
        value = (1 << 3) | mask  # L error correction.
        remainder = value
        for _ in range(10):
            remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
        encoded = ((value << 10) | remainder) ^ 0x5412

        def bit(i):
            return bool((encoded >> i) & 1)

        for i in range(6):
            draw(8, i, bit(i))
        draw(8, 7, bit(6))
        draw(8, 8, bit(7))
        draw(7, 8, bit(8))
        for i in range(9, 15):
            draw(14 - i, 8, bit(i))
        for i in range(8):
            draw(SIZE - 1 - i, 8, bit(i))
        for i in range(8, 15):
            draw(8, SIZE - 15 + i, bit(i))
        draw(8, SIZE - 8, True)

    format_bits(0)
    index = 0
    right = SIZE - 1
    while right >= 1:
        if right == 6:
            right = 5
        upwards = ((right + 1) & 2) == 0
        for vertical in range(SIZE):
            y = SIZE - 1 - vertical if upwards else vertical
            for offset in range(2):
                x = right - offset
                if not function[y][x]:
                    matrix[y][x] = bool(stream[index]) if index < len(stream) else False
                    index += 1
        right -= 2

    # Mask 0 is valid and deterministic; no heuristic may modify functional modules.
    for y in range(SIZE):
        for x in range(SIZE):
            if not function[y][x] and (x + y) % 2 == 0:
                matrix[y][x] = not matrix[y][x]
    format_bits(0)
    return matrix


def svg(text: str) -> str:
    matrix = encode(text)
    commands = "".join(
        f"M{x + 4},{y + 4}h1v1h-1z"
        for y, row in enumerate(matrix)
        for x, dark in enumerate(row)
        if dark
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 49 49" '
        f'width="294" height="294" shape-rendering="crispEdges">'
        f'<rect width="49" height="49" fill="white"/>'
        f'<path d="{commands}" fill="black"/></svg>'
    )
