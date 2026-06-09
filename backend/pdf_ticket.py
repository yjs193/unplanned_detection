from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import fitz
import pytesseract
from PIL import Image


def _clean_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    replacements = {
        "执行的施工方案名\n称": "执行的施工方案名称",
        "作业是否需要停电\n配合": "作业是否需要停电配合",
        "是否在运行区域或\n邻电作业": "是否在运行区域或邻电作业",
        "作业部位及内\n容": "作业部位及内容",
        "初勘风险等\n级": "初勘风险等级",
        "复测后风险等\n级": "复测后风险等级",
        "计划开始时\n间": "计划开始时间",
        "计划结束时\n间": "计划结束时间",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _ocr_page(page: fitz.Page) -> str:
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    image = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
    return pytesseract.image_to_string(image, lang="chi_sim+eng", config="--oem 3 --psm 6")


def extract_text_from_pdf(content: bytes, filename: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "text": "",
        "engine": "pymupdf_text",
        "filename": filename,
        "page_count": 0,
        "pages": [],
        "error": "",
    }
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        result["error"] = f"PDF打开失败：{exc}"
        return result

    page_texts: list[str] = []
    try:
        result["page_count"] = len(doc)
        for index, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            page_texts.append(text)
            result["pages"].append({"page": index, "chars": len(text.strip()), "method": "text"})
        merged_text = _clean_text("\n".join(page_texts))

        if len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", merged_text)) < 80:
            result["engine"] = "pymupdf_render+tesseract"
            page_texts = []
            result["pages"] = []
            for index in range(min(len(doc), 6)):
                page = doc[index]
                text = _ocr_page(page)
                page_texts.append(text)
                result["pages"].append({"page": index + 1, "chars": len(text.strip()), "method": "ocr"})
            merged_text = _clean_text("\n".join(page_texts))

        result["text"] = merged_text
        result["success"] = bool(merged_text)
        if not merged_text:
            result["error"] = "未从PDF中识别到有效文字。"
    except Exception as exc:
        result["error"] = f"PDF识别失败：{exc}"
    finally:
        doc.close()
    return result
