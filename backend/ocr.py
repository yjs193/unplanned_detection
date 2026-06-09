
from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import pytesseract
from PIL import Image, ImageFilter, ImageOps


FIELD_HINTS = ["计划编号", "项目名称", "工程名称", "计划时间", "风险等级", "计划状态", "执行状态", "工作负责人", "作业地点", "作业内容", "施工单位"]


def _normalize_text(text: str) -> str:
    text = text.replace("\x0c", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _score_text(text: str) -> int:
    cn_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    digit_count = len(re.findall(r"\d", text))
    hint_count = sum(12 for hint in FIELD_HINTS if hint in text)
    return cn_count * 2 + digit_count + hint_count + min(len(text), 400)


def _variants(image: Image.Image) -> list[Image.Image]:
    rgb = image.convert("RGB")
    gray = ImageOps.grayscale(rgb)
    scale = 2 if max(gray.size) < 1800 else 1
    enlarged = gray.resize((gray.width * scale, gray.height * scale)) if scale > 1 else gray
    autocontrast = ImageOps.autocontrast(enlarged)
    sharpened = autocontrast.filter(ImageFilter.SHARPEN)
    threshold = sharpened.point(lambda p: 255 if p > 165 else 0)
    return [rgb, gray, autocontrast, sharpened, threshold]


def extract_text_from_image(content: bytes, filename: str = "") -> dict[str, Any]:
    try:
        image = Image.open(BytesIO(content))
        image.load()
    except Exception as exc:
        return {
            "success": False,
            "text": "",
            "engine": "tesseract",
            "language": "chi_sim+eng",
            "filename": filename,
            "error": f"图片读取失败：{exc}",
        }

    candidates: list[dict[str, Any]] = []
    configs = ["--oem 3 --psm 6", "--oem 3 --psm 11"]
    for variant_index, variant in enumerate(_variants(image)):
        for config in configs:
            try:
                text = pytesseract.image_to_string(variant, lang="chi_sim+eng", config=config)
            except Exception as exc:
                candidates.append({"text": "", "score": 0, "config": config, "variant": variant_index, "error": str(exc)})
                continue
            normalized = _normalize_text(text)
            candidates.append({"text": normalized, "score": _score_text(normalized), "config": config, "variant": variant_index})

    best = max(candidates, key=lambda item: item.get("score", 0), default={"text": "", "score": 0})
    text = best.get("text", "")
    return {
        "success": bool(text),
        "text": text,
        "engine": "tesseract",
        "language": "chi_sim+eng",
        "filename": filename,
        "score": best.get("score", 0),
        "config": best.get("config", ""),
        "variant": best.get("variant"),
        "image_size": {"width": image.width, "height": image.height},
        "error": best.get("error", "") if not text else "",
    }
