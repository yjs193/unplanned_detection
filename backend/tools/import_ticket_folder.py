from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.agent import parse_ticket
from backend.app import build_agent_analysis
from backend.db import get_ticket, import_parse_record_as_ticket, init_db, save_parse_record
from backend.ocr import extract_text_from_image
from backend.pdf_ticket import extract_text_from_pdf


SUPPORTED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def extract_file(path: Path) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    content = path.read_bytes()
    if path.suffix.lower() == ".pdf":
        pdf_result = extract_text_from_pdf(content, filename=path.name)
        return pdf_result.get("text", "").strip(), "pdf", {}, pdf_result
    ocr_result = extract_text_from_image(content, filename=path.name)
    return ocr_result.get("text", "").strip(), "image_ocr", ocr_result, {}


def build_record(path: Path) -> dict[str, Any]:
    text, source_type, ocr_result, pdf_result = extract_file(path)
    if not text:
        text = f"文件：{path.name}\n未识别到有效文字。"
    payload = parse_ticket(text, source_type=source_type)
    fact = payload["ticket_fact"]
    fact["source_file_name"] = path.name
    fact["source_file_path"] = str(path)
    payload["agent_analysis"] = build_agent_analysis(fact, payload["validation_result"], use_llm=True)
    fingerprint = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:10]
    return {
        "id": f"folder_{fingerprint}",
        "ticket_id": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_type": source_type,
        "summary": fact.get("project_name") or fact.get("plan_id") or path.stem,
        "raw_text": text,
        "ocr_result": ocr_result,
        "pdf_result": pdf_result,
        **payload,
    }


def iter_ticket_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES)


def import_folder(root: Path, limit: int | None = None, dry_run: bool = False, skip_init_db: bool = False) -> dict[str, int]:
    if not skip_init_db:
        init_db()
    stats = {"scanned": 0, "created": 0, "skipped": 0, "failed": 0}
    for path in iter_ticket_files(root)[:limit]:
        stats["scanned"] += 1
        try:
            record = build_record(path)
            plan_id = (record.get("ticket_fact") or {}).get("plan_id")
            if plan_id and get_ticket(plan_id):
                stats["skipped"] += 1
                print(f"跳过已入库：{plan_id}｜{path}")
                continue
            if dry_run:
                print(f"预演导入：{plan_id or '无计划编号'}｜{path}")
                continue
            save_parse_record(record)
            result = import_parse_record_as_ticket(record)
            stats["created"] += 1 if result.get("created") else 0
            stats["skipped"] += 0 if result.get("created") else 1
            print(f"完成导入：{plan_id or result.get('ticket', {}).get('plan_id')}｜{path}")
        except Exception as exc:
            stats["failed"] += 1
            print(f"导入失败：{path}｜{exc}")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="批量导入作业票文件夹")
    parser.add_argument("--ticket-dir", default=os.getenv("TICKET_DATA_DIR") or str(ROOT / "backend" / "media" / "ticket"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-init-db", action="store_true", help="跳过 init_db，适用于清库后只导入真实作业票")
    args = parser.parse_args()
    stats = import_folder(Path(args.ticket_dir), limit=args.limit, dry_run=args.dry_run, skip_init_db=args.skip_init_db)
    print(f"扫描{stats['scanned']}个文件，新增{stats['created']}条，跳过{stats['skipped']}条，失败{stats['failed']}条。")


if __name__ == "__main__":
    main()
