"""俯瞰画像を背景に埋め込んだ.drawioファイルを生成する.

overhead.pngをJPEG変換・Base64エンコードしてbackgroundImageとして埋め込み、
ユーザーがdraw.io上で矢印を描画してカメラパスを指示できるようにする。

Usage:
    uv run python .claude/skills/v2v-camera-cuts/scripts/generate_drawio.py \
      --image <overhead.png> --output <output.drawio>
"""

import argparse
import base64
import io
import json
from pathlib import Path

from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True, help="俯瞰画像のパス")
    parser.add_argument("--output", type=Path, required=True, help="出力.drawioファイルのパス")
    args = parser.parse_args()

    if not args.image.exists():
        msg = f"画像が見つかりません: {args.image}"
        raise FileNotFoundError(msg)

    # 画像をJPEGに変換してBase64エンコード（サイズ削減）
    # draw.ioで扱いやすいよう長辺を800pxにリサイズ
    img = Image.open(args.image)
    orig_w, orig_h = img.size
    max_side = 800
    scale = max_side / max(orig_w, orig_h)
    width = round(orig_w * scale)
    height = round(orig_h * scale)
    img = img.resize((width, height), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=75)
    jpeg_bytes = buf.getvalue()
    b64 = base64.b64encode(jpeg_bytes).decode("ascii")
    data_uri = f"data:image/jpeg;base64,{b64}"
    print(f"画像変換: PNG({orig_w}x{orig_h}) → JPEG({width}x{height}, {len(jpeg_bytes)}B)")

    # backgroundImage JSON
    bg_json = json.dumps({"src": data_uri, "width": width, "height": height})
    bg_attr = bg_json.replace('"', "&quot;")

    # draw.io XML生成（文字列テンプレートで構築、ElementTreeのエスケープ問題を回避）
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net">
  <diagram name="カメラパス" id="camera-paths">
    <mxGraphModel dx="1422" dy="794" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{width}" pageHeight="{height}" backgroundImage="{bg_attr}">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>'''

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(xml, encoding="utf-8")

    print(f"drawio生成: {args.output} ({width}x{height})")


if __name__ == "__main__":
    main()
