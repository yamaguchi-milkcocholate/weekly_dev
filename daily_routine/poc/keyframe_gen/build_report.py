"""キーフレーム画像生成PoC: HTMLレポート生成.

experiment_log.json を読み込み、比較テーブルのHTMLを生成する。
縦軸: シーン、横軸: プロンプトパターン

Usage:
    uv run python poc/keyframe_gen/build_report.py
"""

import json
import logging
import sys
from base64 import b64encode
from pathlib import Path

from config import GENERATED_DIR, PROMPT_PATTERNS, REPORTS_DIR, SCENES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _image_to_data_uri(image_path: Path) -> str | None:
    """画像ファイルをBase64 data URIに変換する."""
    if not image_path.exists():
        return None
    data = b64encode(image_path.read_bytes()).decode()
    suffix = image_path.suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(suffix, "image/png")
    return f"data:{mime};base64,{data}"


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_report() -> None:
    log_path = GENERATED_DIR / "experiment_log.json"
    if not log_path.exists():
        logger.error("実験ログが見つかりません: %s", log_path)
        logger.error("先に run_experiment.py を実行してください。")
        sys.exit(1)

    log_data = json.loads(log_path.read_text())
    results = log_data["results"]

    # 結果をルックアップテーブルに変換 {(pattern_id, scene_id): entry}
    lookup: dict[tuple[str, str], dict] = {}
    for entry in results:
        lookup[(entry["pattern_id"], entry["scene_id"])] = entry

    # リファレンス画像
    ref_path = Path(log_data["reference_image"])
    ref_data_uri = _image_to_data_uri(ref_path)

    # ログに含まれるパターンIDを取得し、定義順に並べる
    logged_pattern_ids = {entry["pattern_id"] for entry in results}
    all_pattern_map = {p.id: p for p in PROMPT_PATTERNS}
    pattern_ids = [p.id for p in PROMPT_PATTERNS if p.id in logged_pattern_ids]
    scene_ids = [s.id for s in SCENES]
    scene_map = {s.id: s for s in SCENES}

    # Location 参照画像を収集
    location_refs: dict[str, str | None] = {}
    for entry in results:
        loc_ref = entry.get("location_ref_image")
        if loc_ref:
            location_refs[entry["scene_id"]] = loc_ref

    # HTML構築
    html_parts: list[str] = []
    html_parts.append(f"""\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>キーフレーム画像生成PoC レポート</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }}
h1 {{ color: #333; }}
h2 {{ color: #444; margin-top: 30px; }}
.meta {{ color: #666; margin-bottom: 20px; }}
.ref-section {{ margin-bottom: 30px; }}
.ref-section img {{ max-height: 200px; border: 1px solid #ccc; border-radius: 4px; margin-right: 10px; }}
.ref-grid {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; }}
.ref-item {{ text-align: center; }}
.ref-item .label {{ font-size: 12px; color: #666; margin-top: 4px; }}
table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; vertical-align: top; }}
th {{ background: #4a90d9; color: white; }}
th.scene-header {{ background: #5a5a5a; text-align: left; width: 120px; }}
th.location-col {{ background: #2e8b57; }}
.cell img {{ max-width: 220px; max-height: 390px; border: 1px solid #ccc; border-radius: 4px; cursor: pointer; }}
.cell img:hover {{ transform: scale(1.02); box-shadow: 0 2px 8px rgba(0,0,0,0.2); }}
.prompt {{ font-size: 11px; color: #555; margin-top: 6px; word-break: break-all; text-align: left; max-width: 220px; }}
.risk {{ font-size: 12px; font-weight: bold; }}
.risk-high {{ color: #e74c3c; }}
.risk-mid {{ color: #f39c12; }}
.risk-low {{ color: #27ae60; }}
.failed {{ color: #e74c3c; font-style: italic; }}
.tag-mode {{ font-size: 11px; color: #888; }}
.pattern-header {{ font-size: 13px; }}
.pattern-header .pattern-id {{ font-size: 16px; font-weight: bold; }}
</style>
</head>
<body>
<h1>キーフレーム画像生成PoC レポート</h1>
<div class="meta">
  <p>実行日時: {_escape_html(log_data["timestamp"])}</p>
  <p>組み合わせ数: {log_data["total_combinations"]}</p>
</div>
""")

    # リファレンス画像セクション
    html_parts.append('<div class="ref-section">\n<h2>リファレンス画像</h2>\n<div class="ref-grid">\n')

    # キャラクター参照
    html_parts.append('<div class="ref-item">\n')
    if ref_data_uri:
        html_parts.append(f'<img src="{ref_data_uri}" alt="character reference">\n')
    else:
        html_parts.append(f"<p>見つかりません: {_escape_html(str(ref_path))}</p>\n")
    html_parts.append('<div class="label">Character (@char)</div>\n</div>\n')

    # Location 参照（あれば）
    for scene_id, loc_path_str in sorted(location_refs.items()):
        if loc_path_str:
            loc_path = Path(loc_path_str)
            loc_uri = _image_to_data_uri(loc_path)
            html_parts.append('<div class="ref-item">\n')
            if loc_uri:
                html_parts.append(f'<img src="{loc_uri}" alt="location {scene_id}">\n')
            html_parts.append(f'<div class="label">Location: {_escape_html(scene_id)}</div>\n</div>\n')

    html_parts.append("</div>\n</div>\n")

    # 比較テーブル
    html_parts.append("<h2>比較テーブル</h2>\n<table>\n<tr>\n<th></th>\n")
    for pid in pattern_ids:
        p = all_pattern_map.get(pid)
        if p:
            th_class = "location-col" if p.use_location_tag else ""
            class_attr = f' class="{th_class}"' if th_class else ""
            html_parts.append(
                f'<th{class_attr}><div class="pattern-header">'
                f'<span class="pattern-id">{_escape_html(p.id)}</span><br>'
                f"{_escape_html(p.name)}</div></th>\n"
            )
    html_parts.append("</tr>\n")

    for sid in scene_ids:
        scene = scene_map.get(sid)
        if not scene:
            continue
        risk_class = {"高": "risk-high", "中": "risk-mid", "低": "risk-low"}.get(scene.split_risk, "")
        html_parts.append(
            f'<tr>\n<th class="scene-header">{_escape_html(scene.name)}<br>'
            f'<span class="risk {risk_class}">分裂リスク: {_escape_html(scene.split_risk)}</span></th>\n'
        )
        for pid in pattern_ids:
            entry = lookup.get((pid, sid))
            html_parts.append('<td class="cell">\n')
            if entry and entry["status"] == "success":
                img_path = Path(entry["output_path"])
                data_uri = _image_to_data_uri(img_path)
                if data_uri:
                    html_parts.append(f'<img src="{data_uri}" alt="{pid}-{sid}">\n')
                else:
                    html_parts.append('<p class="failed">画像ファイルなし</p>\n')
                html_parts.append(f'<div class="prompt">{_escape_html(entry["prompt"])}</div>\n')
                tags = []
                if entry.get("use_char_tag", entry.get("use_tag", False)):
                    tags.append("@char")
                if entry.get("use_location_tag", False):
                    tags.append("@location")
                if not tags:
                    tags.append("代名詞")
                html_parts.append(f'<div class="tag-mode">{_escape_html(" + ".join(tags))}</div>\n')
            elif entry and entry["status"] == "failed":
                html_parts.append('<p class="failed">生成失敗</p>\n')
                html_parts.append(f'<div class="prompt">{_escape_html(entry["prompt"])}</div>\n')
            else:
                html_parts.append("<p>未実行</p>\n")
            html_parts.append("</td>\n")
        html_parts.append("</tr>\n")

    html_parts.append("</table>\n")

    # パターン説明
    html_parts.append("<h2>プロンプトパターン詳細</h2>\n<table>\n")
    html_parts.append("<tr><th>ID</th><th>名前</th><th>テンプレート</th><th>参照タグ</th></tr>\n")
    for pid in pattern_ids:
        p = all_pattern_map.get(pid)
        if not p:
            continue
        tags = []
        if p.use_char_tag:
            tags.append("@char")
        if p.use_location_tag:
            tags.append("@location")
        if not tags:
            tags.append("referenceImages のみ")
        tag_label = " + ".join(tags)
        html_parts.append(
            f"<tr><td>{_escape_html(p.id)}</td><td>{_escape_html(p.name)}</td>"
            f"<td style='text-align:left; font-size:12px;'>{_escape_html(p.template)}</td>"
            f"<td>{_escape_html(tag_label)}</td></tr>\n"
        )
    html_parts.append("</table>\n")

    html_parts.append("</body>\n</html>")

    # 出力
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "experiment_report.html"
    report_path.write_text("".join(html_parts))
    logger.info("レポートを生成しました: %s", report_path)


if __name__ == "__main__":
    build_report()
