from __future__ import annotations

from datetime import datetime, timedelta


def _iso_minutes(offset: int) -> str:
    return (datetime.now() + timedelta(minutes=offset)).strftime("%Y-%m-%d %H:%M:%S")


CAMERA_MAPPINGS = [
    {
        "id": "map_l13",
        "project_keywords": ["挂绿", "输变电", "L13", "L1-L13", "L13-L19"],
        "location_keywords": ["L13塔", "L13", "L1-L13", "L13-L19"],
        "cameras": [
            {"camera_id": "CAM_L13_01", "camera_name": "L13塔固定枪机-北侧", "distance_m": 38},
            {"camera_id": "CAM_L13_02", "camera_name": "L13塔云台球机-施工便道", "distance_m": 64},
        ],
        "uav_route": {"route_id": "UAV_ROUTE_L13", "route_name": "L13塔及挡土墙巡检航线"},
    },
    {
        "id": "map_s11_s19",
        "project_keywords": ["挂绿", "S11-S19", "架线"],
        "location_keywords": ["S11-S19", "S19", "S11"],
        "cameras": [
            {"camera_id": "CAM_S19_01", "camera_name": "S19塔固定枪机", "distance_m": 55},
            {"camera_id": "CAM_S15_01", "camera_name": "S15-S19通道球机", "distance_m": 120},
        ],
        "uav_route": {"route_id": "UAV_ROUTE_S11_S19", "route_name": "S11-S19线路巡检航线"},
    },
    {
        "id": "map_station_wall",
        "project_keywords": ["明珠", "变电站", "挡土墙", "基础"],
        "location_keywords": ["北侧挡土墙", "站区北侧", "挡土墙"],
        "cameras": [
            {"camera_id": "CAM_WALL_N_01", "camera_name": "站区北侧挡土墙全景", "distance_m": 22},
            {"camera_id": "CAM_GATE_02", "camera_name": "北门施工道路球机", "distance_m": 85},
        ],
        "uav_route": {"route_id": "UAV_ROUTE_WALL_N", "route_name": "站区北侧挡土墙巡检航线"},
    },
]


SAMPLE_TICKETS = [
    {
        "id": "sample_planned_line",
        "name": "计划内架线作业样例",
        "source_type": "text",
        "raw_text": (
            "计划编号：JJSX0301251030200025\n"
            "项目名称：220千伏挂绿输变电工程（第二分册）\n"
            "计划时间：2026-05-21 08:00 至 2026-05-21 18:00\n"
            "风险等级：低\n"
            "计划状态：开工中\n"
            "执行状态：现场施工中\n"
            "工作负责人：谭文恩\n"
            "是否纳入视频管控：是\n"
            "作业地点：构架-L1、构架-S1、S1-S11、L1-L13、S11-S19、L13-L19塔段\n"
            "作业内容：220kV挂绿一标：构架-L1、构架-S1、S1-S11、L1-L13、S11-S19、"
            "L13-L19塔段展放导、地线、光缆、紧线、压接、附件安装、沿线跨越架搭设、北绕线封网施工。"
        ),
    },
    {
        "id": "sample_unplanned_l13",
        "name": "L13塔现场巡查线索样例",
        "source_type": "image_ocr_simulation",
        "raw_text": (
            "巡查问题：L13塔5名施工人员进行挡土墙施工作业，查询智慧工程系统无相关作业计划内容，"
            "现场无工作负责人开展现场管控。\n"
            "项目名称：220千伏挂绿输变电工程\n"
            "作业地点：L13塔附近挡土墙\n"
            "作业内容：挡土墙施工作业，现场有5名施工人员。\n"
            "计划查询结果：智慧工程系统无相关作业计划\n"
            "工作负责人：无\n"
            "是否纳入视频管控：否"
        ),
    },
    {
        "id": "sample_station_wall",
        "name": "变电站挡土墙计划作业样例",
        "source_type": "text",
        "raw_text": (
            "计划编号：GJSG202605210018\n"
            "项目名称：明珠110千伏变电站扩建工程\n"
            "计划时间：2026-05-21 09:30 至 2026-05-21 17:30\n"
            "风险等级：中\n"
            "计划状态：待开工\n"
            "执行状态：待开工\n"
            "工作负责人：陈志强\n"
            "是否纳入视频管控：是\n"
            "作业地点：站区北侧挡土墙、北门施工道路\n"
            "作业内容：挡土墙钢筋绑扎、模板安装、混凝土浇筑准备、材料转运。"
        ),
    },
]


RECENT_INSPECTIONS = [
    {
        "id": "insp_20260521_001",
        "ticket": "JJSX0301251030200025",
        "location": "L13-L19塔段",
        "status": "媒体调取完成",
        "risk": "低",
        "updated_at": _iso_minutes(-16),
    },
    {
        "id": "insp_20260521_002",
        "ticket": "现场巡查-L13",
        "location": "L13塔附近挡土墙",
        "status": "等待视觉比对",
        "risk": "高",
        "updated_at": _iso_minutes(-8),
    },
    {
        "id": "insp_20260521_003",
        "ticket": "GJSG202605210018",
        "location": "站区北侧挡土墙",
        "status": "未触发检查",
        "risk": "中",
        "updated_at": _iso_minutes(-3),
    },
]
