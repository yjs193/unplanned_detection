from __future__ import annotations

import json
import os
import random
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pymysql


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "health_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "health_2024!")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "unplanned_work_inspection")
MYSQL_CHARSET = "utf8mb4"
MYSQL_SOCKET = os.getenv("MYSQL_SOCKET", "/var/run/mysqld/mysqld.sock")

PROJECTS = [
    ("广州南沙220千伏明珠输变电工程", "南沙区明珠湾", ["N1塔", "N3塔", "站区北侧挡土墙", "电缆沟A段"]),
    ("广州黄埔110千伏科学城扩建工程", "黄埔区科学城", ["H5塔", "H8塔", "站内GIS区", "北侧施工便道"]),
    ("广州番禺220千伏大学城配套线路工程", "番禺区大学城", ["P2塔", "P9塔", "电缆隧道3号井", "材料堆场"]),
    ("广州增城110千伏荔湖变电站工程", "增城区荔湖", ["Z1塔", "Z6塔", "主变基础", "围墙东段"]),
    ("广州白云220千伏机场北线路迁改工程", "白云区机场北", ["B4塔", "B12塔", "跨越架区", "临时道路"]),
    ("广州从化110千伏温泉站配套工程", "从化区温泉镇", ["C3塔", "C7塔", "站区南侧挡土墙", "排水沟"]),
]
WORKS = [
    ("展放导地线、紧线、压接、附件安装", ["wire_and_cable_stringing", "wire_tensioning", "crimping", "accessory_installation"]),
    ("挡土墙钢筋绑扎、模板安装、混凝土浇筑准备", ["retaining_wall_construction", "rebar_binding", "formwork_installation"]),
    ("电缆沟开挖、支护、材料转运", ["trench_excavation", "material_transport"]),
    ("跨越架搭设、封网施工、现场警戒", ["crossing_frame_erection", "protective_net_installation"]),
    ("设备基础浇筑、接地网敷设、场地清理", ["concrete_pouring", "grounding_grid_installation"]),
    ("塔材转运、构件吊装、螺栓复紧", ["material_transport", "lifting_operation", "tower_assembly"]),
]
RISKS = ["低", "中", "高"]
PLAN_STATUS = ["待开工", "开工中", "已完工"]
EXEC_STATUS = ["待开工", "现场施工中", "已收工"]
LEADERS = ["陈志强", "李明", "黄晓东", "谭文恩", "周建华", "何伟", "梁启明", "罗海峰"]
CONTRACTORS = ["广东电网能源发展有限公司", "广州电力建设有限公司", "广东火电工程有限公司", "广东省输变电工程有限公司"]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def risk_flag(idx: int) -> bool:
    return idx % 7 == 0 or idx % 13 == 0


def generate_tickets(total: int) -> list[dict[str, Any]]:
    random.seed(20260521)
    base = datetime(2026, 5, 21, 8, 0, 0)
    tickets = []
    for idx in range(1, total + 1):
        project, district, locations = PROJECTS[(idx - 1) % len(PROJECTS)]
        location = locations[(idx + 1) % len(locations)]
        work_content, work_types = WORKS[(idx * 3) % len(WORKS)]
        plan_status = PLAN_STATUS[idx % len(PLAN_STATUS)]
        high_attention = idx % 11 == 0 or risk_flag(idx)
        plan_id = f"20260521{idx:08d}"
        risk = "高" if high_attention else RISKS[idx % 2]
        start = base + timedelta(days=idx % 16, hours=idx % 5)
        end = start + timedelta(hours=4 + idx % 6)
        leader = LEADERS[idx % len(LEADERS)]
        video = 0 if idx % 9 == 0 else 1
        contractor = CONTRACTORS[idx % len(CONTRACTORS)]
        if plan_status == "待开工":
            execution_status = "待开工"
        elif plan_status == "已完工":
            execution_status = "已收工"
        else:
            execution_status = "现场施工中"
        raw_text = (
            f"计划编号：{plan_id}\n"
            f"项目名称：{project}\n"
            f"施工单位：{contractor}\n"
            f"城市：广州\n"
            f"行政区：{district}\n"
            f"计划时间：{start:%Y-%m-%d %H:%M} 至 {end:%Y-%m-%d %H:%M}\n"
            f"风险等级：{risk}\n"
            f"计划状态：{plan_status}\n"
            f"执行状态：{execution_status}\n"
            f"工作负责人：{leader}\n"
            f"是否纳入视频管控：{'是' if video else '否'}\n"
            f"作业地点：{location}\n"
            f"作业内容：{work_content}。"
        )
        fact = {
            "plan_id": plan_id,
            "project_name": project,
            "city": "广州",
            "district": district,
            "contractor": contractor,
            "plan_time_range": {"start": f"{start:%Y-%m-%d %H:%M:%S}", "end": f"{end:%Y-%m-%d %H:%M:%S}"},
            "risk_level": risk,
            "plan_status": plan_status,
            "execution_status": execution_status,
            "work_leader": leader,
            "video_control_enabled": bool(video),
            "work_location": location,
            "work_content_raw": work_content,
            "work_scope": [location],
            "person_count": 3 + idx % 8,
            "source_type": "database",
            "normalized_work_types": work_types,
            "scene_tags": ["户外作业", "广州基建", "高处作业" if "塔" in location else "土建施工"],
        }
        camera_id = f"CAM_GZ_{idx:03d}"
        media_task = {
            "task_type": "MEDIA_RETRIEVAL",
            "tool_name": "get_site_media",
            "trigger_mode": "manual_or_scheduled",
            "trigger_interval_minutes": 30,
            "arguments": {
                "plan_id": plan_id,
                "project_name": project,
                "work_location": location,
                "work_scope_keywords": [location, district],
                "query_window": {"mode": "latest", "duration_minutes": 30},
                "media_type": ["image", "video"],
                "image_sample_interval_seconds": 10,
                "camera_selection_strategy": "project_tower_section_nearest",
                "candidate_cameras": [
                    {"camera_id": camera_id, "camera_name": f"{location}固定监控", "distance_m": 20 + idx % 120},
                    {"camera_id": f"{camera_id}_PTZ", "camera_name": f"{district}移动云台", "distance_m": 65 + idx % 160},
                ],
                "uav_route": {"route_id": f"UAV_GZ_{idx:03d}", "route_name": f"{location}巡检航线"},
            },
            "mapping_confidence": round(0.68 + (idx % 20) / 100, 2),
        }
        validation = {
            "missing_fields": [],
            "warnings": (["高风险作业票进入自动一致性检查时，应重点比对作业地点、时间窗口和现场人员数量。"] if high_attention else []),
            "requires_human_review": False,
            "confidence": 0.86 if high_attention else 0.93,
        }
        agent_analysis = {
            "agent_name": "作业票入库分析智能体",
            "risk_judgement": "重点跟踪" if high_attention or risk == "高" else "常规检查",
            "key_findings": ([f"作业票处于{plan_status}状态，计划作业地点为{district}{location}。", f"计划作业内容为{work_content}，自动检查时应比对现场作业类型、人员数量和时间窗口。"] if high_attention else [f"作业票覆盖{district}{location}，作业内容为{work_content}。", "字段完整，可作为后续现场媒体调取和计划-现场一致性比对的计划侧事实。"]),
            "dispatch_suggestion": f"优先调取{location}固定监控，若画面遮挡再派发无人机补拍。",
            "review_required": False,
            "model_provider": "rules",
        }
        tickets.append(
            {
                "id": f"ticket_{idx:04d}",
                "plan_id": plan_id,
                "project_name": project,
                "district": district,
                "work_location": location,
                "work_content_raw": work_content,
                "plan_status": fact["plan_status"],
                "execution_status": fact["execution_status"],
                "risk_level": risk,
                "work_leader": leader,
                "contractor": contractor,
                "video_control_enabled": video,
                "plan_start": fact["plan_time_range"]["start"],
                "plan_end": fact["plan_time_range"]["end"],
                "raw_text": raw_text,
                "ticket_fact": fact,
                "media_query_task": media_task,
                "validation_result": validation,
                "agent_analysis": agent_analysis,
                "created_at": f"{datetime(2026, 5, 21, 9, 0, 0) + timedelta(minutes=idx):%Y-%m-%d %H:%M:%S}",
                "updated_at": f"{datetime(2026, 5, 21, 10, 0, 0) + timedelta(minutes=idx):%Y-%m-%d %H:%M:%S}",
            }
        )
    return tickets



def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _root_connect() -> pymysql.connections.Connection:
    return pymysql.connect(
        unix_socket=MYSQL_SOCKET,
        user="root",
        charset=MYSQL_CHARSET,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _server_connect() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset=MYSQL_CHARSET,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def connect() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset=MYSQL_CHARSET,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def ensure_database() -> None:
    try:
        conn = _root_connect()
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cur.execute("CREATE USER IF NOT EXISTS %s@'localhost' IDENTIFIED BY %s", (MYSQL_USER, MYSQL_PASSWORD))
            cur.execute("CREATE USER IF NOT EXISTS %s@'%' IDENTIFIED BY %s", (MYSQL_USER, MYSQL_PASSWORD))
            cur.execute(f"GRANT ALL PRIVILEGES ON `{MYSQL_DATABASE}`.* TO %s@'localhost'", (MYSQL_USER,))
            cur.execute(f"GRANT ALL PRIVILEGES ON `{MYSQL_DATABASE}`.* TO %s@'%'", (MYSQL_USER,))
            cur.execute("FLUSH PRIVILEGES")
        conn.close()
        return
    except Exception:
        pass

    conn = _server_connect()
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.close()


def init_db() -> None:
    ensure_database()
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS work_tickets (
                    id VARCHAR(64) PRIMARY KEY,
                    plan_id VARCHAR(80) NOT NULL,
                    project_name VARCHAR(255) NOT NULL,
                    district VARCHAR(80) NOT NULL,
                    work_location VARCHAR(255) NOT NULL,
                    work_content_raw TEXT NOT NULL,
                    plan_status VARCHAR(40) NOT NULL,
                    execution_status VARCHAR(40) NOT NULL,
                    risk_level VARCHAR(20) NOT NULL,
                    work_leader VARCHAR(80) NOT NULL,
                    contractor VARCHAR(255) NOT NULL,
                    video_control_enabled TINYINT(1) NOT NULL,
                    plan_start DATETIME NOT NULL,
                    plan_end DATETIME NOT NULL,
                    raw_text TEXT NOT NULL,
                    ticket_fact_json LONGTEXT NOT NULL,
                    media_query_task_json LONGTEXT NOT NULL,
                    validation_result_json LONGTEXT NOT NULL,
                    agent_analysis_json LONGTEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    INDEX idx_plan_status (plan_status),
                    INDEX idx_risk_level (risk_level),
                    INDEX idx_district (district),
                    INDEX idx_updated_at (updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS parse_records (
                    id VARCHAR(64) PRIMARY KEY,
                    ticket_id VARCHAR(64),
                    source_type VARCHAR(40) NOT NULL,
                    summary VARCHAR(255) NOT NULL,
                    record_json LONGTEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS inspections (
                    id VARCHAR(64) PRIMARY KEY,
                    ticket_id VARCHAR(64),
                    ticket VARCHAR(80),
                    location VARCHAR(255),
                    status VARCHAR(40),
                    risk VARCHAR(20),
                    operator_name VARCHAR(80),
                    mode VARCHAR(40),
                    record_json LONGTEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    INDEX idx_updated_at (updated_at),
                    INDEX idx_status (status),
                    INDEX idx_risk (risk)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id VARCHAR(64) PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    ticket_id VARCHAR(64),
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    INDEX idx_updated_at (updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id VARCHAR(64) PRIMARY KEY,
                    conversation_id VARCHAR(64) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content LONGTEXT NOT NULL,
                    metadata_json LONGTEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    INDEX idx_conversation_time (conversation_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cur.execute("SHOW COLUMNS FROM work_tickets LIKE 'agent_analysis_json'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE work_tickets ADD COLUMN agent_analysis_json LONGTEXT NOT NULL AFTER validation_result_json")
                cur.execute("UPDATE work_tickets SET agent_analysis_json = '{}' WHERE agent_analysis_json = ''")
            cur.execute("SELECT COUNT(*) AS total FROM work_tickets")
            count = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) AS invalid_total FROM work_tickets WHERE id LIKE 'ticket_%' AND id NOT LIKE 'ticket_import_%' AND (plan_id NOT REGEXP '^[0-9]{16}$' OR raw_text LIKE CONCAT('%', '华南', '理工', '%') OR raw_text LIKE CONCAT('%', '合作', '单位', '%') OR plan_status NOT IN ('待开工', '开工中', '已完工'))")
            invalid_count = cur.fetchone()["invalid_total"]
            cur.execute("SELECT COUNT(*) AS bad_status_total FROM work_tickets WHERE (plan_status = '待开工' AND execution_status <> '待开工') OR (plan_status = '开工中' AND execution_status <> '现场施工中') OR (plan_status = '已完工' AND execution_status <> '已收工')")
            bad_status_count = cur.fetchone()["bad_status_total"]
            if count < 100 or invalid_count > 0 or bad_status_count > 0:
                cur.execute("DELETE FROM work_tickets")
                for ticket in generate_tickets(120):
                    insert_ticket(cur, ticket)
            cur.execute("SHOW INDEX FROM work_tickets WHERE Key_name = 'uniq_plan_id'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE work_tickets ADD UNIQUE KEY uniq_plan_id (plan_id)")
            cur.execute("SELECT id, ticket_fact_json, validation_result_json, agent_analysis_json FROM work_tickets")
            for row in cur.fetchall():
                current = _loads(row.get("agent_analysis_json"), {})
                if current:
                    continue
                fact = _loads(row.get("ticket_fact_json"), {})
                validation = _loads(row.get("validation_result_json"), {})
                attention = fact.get("risk_level") == "高" or fact.get("plan_status") == "开工中"
                analysis = {
                    "agent_name": "作业票入库分析智能体",
                    "risk_judgement": "重点跟踪" if attention else "常规检查",
                    "key_findings": [
                        f"作业票覆盖{fact.get('district', '广州')}{fact.get('work_location', '作业地点')}，计划状态为{fact.get('plan_status', '待确认')}。",
                        f"计划作业内容为{fact.get('work_content_raw', '待补充')}，后续需与现场识别到的时间、地点、人员数量和作业类型进行一致性比对。",
                    ],
                    "dispatch_suggestion": f"优先调取{fact.get('work_location', '作业地点')}固定监控，画面遮挡时派发无人机补拍。",
                    "review_required": False,
                    "model_provider": "rules",
                }
                cur.execute("UPDATE work_tickets SET agent_analysis_json = %s WHERE id = %s", (_json(analysis), row["id"]))
    finally:
        conn.close()


def insert_ticket(cur: pymysql.cursors.Cursor, ticket: dict[str, Any]) -> None:
    cur.execute(
        """
        INSERT INTO work_tickets (
            id, plan_id, project_name, district, work_location, work_content_raw,
            plan_status, execution_status, risk_level, work_leader, contractor,
            video_control_enabled, plan_start, plan_end, raw_text,
            ticket_fact_json, media_query_task_json, validation_result_json, agent_analysis_json, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            ticket["id"], ticket["plan_id"], ticket["project_name"], ticket["district"], ticket["work_location"],
            ticket["work_content_raw"], ticket["plan_status"], ticket["execution_status"], ticket["risk_level"],
            ticket["work_leader"], ticket["contractor"], ticket["video_control_enabled"], ticket["plan_start"], ticket["plan_end"],
            ticket["raw_text"], _json(ticket["ticket_fact"]), _json(ticket["media_query_task"]), _json(ticket["validation_result"]),
             _json(ticket.get("agent_analysis", {})), ticket["created_at"], ticket["updated_at"],
        ),
    )


def row_to_ticket(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "plan_id": row["plan_id"],
        "project_name": row["project_name"],
        "district": row["district"],
        "work_location": row["work_location"],
        "work_content_raw": row["work_content_raw"],
        "plan_status": row["plan_status"],
        "execution_status": row["execution_status"],
        "risk_level": row["risk_level"],
        "work_leader": row["work_leader"],
        "contractor": row["contractor"],
        "video_control_enabled": bool(row["video_control_enabled"]),
        "plan_start": str(row["plan_start"]),
        "plan_end": str(row["plan_end"]),
        "raw_text": row["raw_text"],
        "ticket_fact": _loads(row["ticket_fact_json"], {}),
        "media_query_task": _loads(row["media_query_task_json"], {}),
        "validation_result": _loads(row["validation_result_json"], {}),
        "agent_analysis": _loads(row.get("agent_analysis_json"), {}),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def list_tickets(limit: int = 100, offset: int = 0, status: str | None = None, keyword: str | None = None) -> dict[str, Any]:
    clauses = []
    params: list[Any] = []
    if status:
        clauses.append("plan_status = %s")
        params.append(status)
    if keyword:
        clauses.append("(project_name LIKE %s OR work_location LIKE %s OR plan_id LIKE %s)")
        like = f"%{keyword}%"
        params.extend([like, like, like])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM work_tickets{where}", params)
            total = cur.fetchone()["total"]
            cur.execute(
                f"SELECT * FROM work_tickets{where} ORDER BY updated_at DESC LIMIT %s OFFSET %s",
                [*params, limit, offset],
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return {"total": total, "items": [row_to_ticket(row) for row in rows]}


def get_ticket(ticket_id: str) -> dict[str, Any] | None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM work_tickets WHERE id = %s OR plan_id = %s", (ticket_id, ticket_id))
            row = cur.fetchone()
    finally:
        conn.close()
    return row_to_ticket(row) if row else None


def dashboard_data() -> dict[str, Any]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id VARCHAR(64) PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    ticket_id VARCHAR(64),
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    INDEX idx_updated_at (updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id VARCHAR(64) PRIMARY KEY,
                    conversation_id VARCHAR(64) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content LONGTEXT NOT NULL,
                    metadata_json LONGTEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    INDEX idx_conversation_time (conversation_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cur.execute("SHOW COLUMNS FROM work_tickets LIKE 'agent_analysis_json'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE work_tickets ADD COLUMN agent_analysis_json LONGTEXT NOT NULL AFTER validation_result_json")
                cur.execute("UPDATE work_tickets SET agent_analysis_json = '{}' WHERE agent_analysis_json = ''")
            cur.execute("SELECT COUNT(*) AS total FROM work_tickets")
            total = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) AS total FROM work_tickets WHERE plan_status = '开工中'")
            active = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) AS total FROM work_tickets WHERE risk_level = '高'")
            high = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) AS total FROM work_tickets WHERE video_control_enabled = 1")
            video = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) AS total FROM work_tickets WHERE plan_status = '开工中' AND risk_level = '高'")
            key_active = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) AS total FROM inspections")
            media = cur.fetchone()["total"]
            cur.execute("SELECT plan_status AS name, COUNT(*) AS value FROM work_tickets GROUP BY plan_status ORDER BY value DESC")
            by_status = cur.fetchall()
            cur.execute("SELECT risk_level AS name, COUNT(*) AS value FROM work_tickets GROUP BY risk_level ORDER BY value DESC")
            by_risk = cur.fetchall()
            cur.execute("SELECT district AS name, COUNT(*) AS value FROM work_tickets GROUP BY district ORDER BY value DESC")
            by_district = cur.fetchall()
            cur.execute("SELECT * FROM work_tickets ORDER BY updated_at DESC LIMIT 12")
            recent = [row_to_ticket(row) for row in cur.fetchall()]
    finally:
        conn.close()
    return {
        "stats": {
            "total_tickets": total,
            "active_tickets": active,
            "pending_match_tickets": active,
            "high_risk_tickets": high,
            "video_control_tickets": video,
            "key_active_tickets": key_active,
            "human_review": key_active,
            "media_tasks": media,
            "video_control_rate": round(video / total, 4) if total else 0,
        },
        "by_status": by_status,
        "by_risk": by_risk,
        "by_district": by_district,
        "recent_tickets": recent,
    }


def save_parse_record(record: dict[str, Any], ticket_id: str | None = None) -> None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO parse_records VALUES (%s, %s, %s, %s, %s, %s)",
                (record["id"], ticket_id, record["source_type"], record["summary"], _json(record), record["created_at"]),
            )
    finally:
        conn.close()


def list_parse_records(limit: int = 20) -> list[dict[str, Any]]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT record_json FROM parse_records ORDER BY created_at DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return [_loads(row["record_json"], {}) for row in rows]


def save_inspection(record: dict[str, Any]) -> None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO inspections VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    record["id"], record.get("ticket_id"), record.get("ticket"), record.get("location"), record.get("status"),
                    record.get("risk"), record.get("operator"), record.get("mode"), _json(record), record["created_at"], record["updated_at"],
                ),
            )
    finally:
        conn.close()


def list_inspections(limit: int = 20) -> list[dict[str, Any]]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT record_json FROM inspections ORDER BY updated_at DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return [_loads(row["record_json"], {}) for row in rows]



def ensure_conversation(conversation_id: str | None, title: str, ticket_id: str | None = None) -> str:
    import uuid
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cid = conversation_id or f"conv_{uuid.uuid4().hex[:10]}"
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM conversations WHERE id = %s", (cid,))
            if cur.fetchone():
                cur.execute("UPDATE conversations SET updated_at = %s WHERE id = %s", (now, cid))
            else:
                cur.execute("INSERT INTO conversations VALUES (%s, %s, %s, %s, %s)", (cid, title[:255], ticket_id, now, now))
    finally:
        conn.close()
    return cid


def save_chat_message(conversation_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
    import uuid
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversation_messages VALUES (%s, %s, %s, %s, %s, %s)",
                (f"msg_{uuid.uuid4().hex[:12]}", conversation_id, role, content, _json(metadata or {}), now),
            )
            cur.execute("UPDATE conversations SET updated_at = %s WHERE id = %s", (now, conversation_id))
    finally:
        conn.close()


def list_conversations(limit: int = 20) -> list[dict[str, Any]]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM conversations ORDER BY updated_at DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return [{**row, "created_at": str(row["created_at"]), "updated_at": str(row["updated_at"])} for row in rows]


def list_conversation_messages(conversation_id: str) -> list[dict[str, Any]]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM conversation_messages WHERE conversation_id = %s ORDER BY created_at ASC", (conversation_id,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"id": row["id"], "conversation_id": row["conversation_id"], "role": row["role"], "content": row["content"], "metadata": _loads(row.get("metadata_json"), {}), "created_at": str(row["created_at"])}
        for row in rows
    ]


def clear_inspection_and_conversations() -> None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM conversation_messages")
            cur.execute("DELETE FROM conversations")
            cur.execute("DELETE FROM inspections")
    finally:
        conn.close()


def _clip(value: Any, max_len: int, fallback: str = "") -> str:
    text = str(value or fallback).strip()
    return text[:max_len]


def _parse_datetime(value: Any, fallback: datetime, default_time: str | None = None) -> str:
    if not value:
        return fallback.strftime("%Y-%m-%d %H:%M:%S")
    raw = str(value).strip().replace("/", "-")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) and default_time:
        raw = f"{raw} {default_time}"
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}", raw):
        raw = f"{raw}:00"
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    return fallback.strftime("%Y-%m-%d %H:%M:%S")


def import_parse_record_as_ticket(record: dict[str, Any]) -> dict[str, Any]:
    fact = record.get("ticket_fact") or {}
    plan_id = str(fact.get("plan_id") or "").strip()
    if not plan_id:
        plan_id = f"{datetime.now():%Y%m%d%H%M%S}{random.randint(0, 99):02d}"
        fact["plan_id"] = plan_id
    existing = get_ticket(plan_id)
    if existing:
        return {"created": False, "ticket": existing, "message": "该计划编号已在库中，无需重复入库。"}

    now_dt = datetime.now()
    start = _parse_datetime((fact.get("plan_time_range") or {}).get("start"), now_dt, "00:00:00")
    end = _parse_datetime((fact.get("plan_time_range") or {}).get("end"), now_dt + timedelta(hours=4), "23:59:59")
    plan_status = fact.get("plan_status") if fact.get("plan_status") in PLAN_STATUS else "待开工"
    execution_status = fact.get("execution_status") or ("现场施工中" if plan_status == "开工中" else "待开工")
    if plan_status == "待开工":
        execution_status = "待开工"
    elif plan_status == "已完工":
        execution_status = "已收工"
    elif plan_status == "开工中" and execution_status not in {"现场施工中", "开工中"}:
        execution_status = "现场施工中"
    fact["plan_status"] = plan_status
    fact["execution_status"] = execution_status
    fact.setdefault("city", "广州")
    fact.setdefault("district", "广州")
    fact.setdefault("work_scope", [fact.get("work_location", "作业地点")])
    if record.get("pdf_result"):
        fact.setdefault("source_file_type", "PDF")
        fact.setdefault("source_file_name", (record.get("pdf_result") or {}).get("filename", ""))
        fact.setdefault("source_page_count", (record.get("pdf_result") or {}).get("page_count", 0))
    elif record.get("ocr_result"):
        fact.setdefault("source_file_type", "图片")
        fact.setdefault("source_file_name", (record.get("ocr_result") or {}).get("filename", ""))
    fact.setdefault("source_type", record.get("source_type", "text"))
    fact.setdefault("normalized_work_types", record.get("normalized_work_types", []))
    fact.setdefault("scene_tags", ["户外作业"])

    ticket = {
        "id": f"ticket_import_{uuid.uuid4().hex[:10]}",
        "plan_id": plan_id,
        "project_name": _clip(fact.get("project_name"), 255, "待补充项目"),
        "district": _clip(fact.get("district"), 80, "广州"),
        "work_location": _clip(fact.get("work_location"), 255, "待补充作业地点"),
        "work_content_raw": fact.get("work_content_raw") or "待补充作业内容",
        "plan_status": plan_status,
        "execution_status": execution_status,
        "risk_level": fact.get("risk_level") or "待确认",
        "work_leader": _clip(fact.get("work_leader"), 80, "待补充"),
        "contractor": _clip(fact.get("contractor"), 255, "待补充"),
        "video_control_enabled": 1 if fact.get("video_control_enabled") else 0,
        "plan_start": start,
        "plan_end": end,
        "raw_text": record.get("raw_text") or "",
        "ticket_fact": fact,
        "media_query_task": record.get("media_query_task") or {},
        "validation_result": record.get("validation_result") or {},
        "agent_analysis": record.get("agent_analysis") or {},
        "created_at": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
    }
    conn = connect()
    try:
        with conn.cursor() as cur:
            insert_ticket(cur, ticket)
    finally:
        conn.close()
    return {"created": True, "ticket": get_ticket(ticket["id"]), "message": "作业票已入库。"}
