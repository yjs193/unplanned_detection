"""
视频视觉分析模块

功能：
1. 从视频中均匀抽取指定数量的画面帧。
2. 调用 OpenAI 兼容的视觉模型分析各帧内容和连续作业过程。
3. 返回模型生成的 JSON 字符串，其中包含 ``frames`` 和 ``work_process``。

配置：
- ``API_KEY``：视觉模型 API 密钥。
- ``BASE_URL``：OpenAI 兼容接口地址。
- ``VLM_MODEL``：视觉模型名称，默认使用 ``qwen-vl-max``。

基本用法：
    result = vision_agent("path/to/video.mp4", frame_count=10)
    print(result)

注意：分析完成后，程序会自动删除抽取出的临时图片。

示例

输入：
video_path = (
    Path(__file__).resolve().parent
    / "media"
    / "110千伏汇景站"
    / (
        "JJBZ0301260520200027_44010000V44010000001310048170_"
        "1779705511_1779706605_1776084737645.mp4"
    )
)
result = vision_agent(video_path)
print(result)

输出：
{
  "frames": [
    "第1帧中，一名身穿蓝色工作服、佩戴蓝色安全帽的工人站在柱子旁，手持工具，背景为建筑物外侧的空调机组和黄色箱体，地面有白色软管和杂物，场景为室外作业环境，推测正在进行设备周边清理或检查。",
    "第2帧中，该工人向右侧移动，身体前倾，似乎在弯腰操作或搬运物品，周围环境与前一帧相同，未见其他人员，推测其正在执行某种地面作业。",
    "第3帧中，该工人已离开画面，仅可见地面的软管和部分设备，场景无明显变化，可能处于短暂无人作业状态。",
    "第4帧中，两名身穿蓝色工作服的工人进入画面，其中一人从左侧走向画面中央，另一人从右侧经过，两人均未携带明显工具，推测可能在进行现场巡视或转移位置。",
    "第5帧中，左侧工人弯腰靠近地面，右手持工具（疑似撬棍），正在对地面上的物体进行操作，另一名工人站立于右侧，背景仍为空调机组和箱体，推测正在进行地面设施的安装或调整。",
    "第6帧中，左侧工人继续操作，双手扶住一根长杆状物体，将其抬起并插入红色挡板结构中，右侧工人部分身体仍在画面中，推测正在协助搭建临时围挡或支撑结构。",
    "第7帧中，左侧工人将长杆固定在红色挡板上，形成支撑结构，动作持续进行，右侧工人依然在场，背景未变，推测围挡安装接近完成。",
    "第8帧中，红色挡板已基本竖立，长杆作为支撑固定在挡板上方，工人已不在画面中，仅可见部分支撑结构，推测围挡已安装完毕。",
    "第9帧中，画面右侧出现一名工人的腿部，穿着蓝色工作服和鞋子，正从右向左移动，红色挡板和支撑结构保持不变，推测有人在进行后续作业或撤离。",
    "第10帧中，右侧工人已移出画面，左侧远处可见另一名戴安全帽的工人在柱子附近活动，红色挡板和支撑结构依然存在，地面仍有软管，推测作业区域已基本布置完成，人员在进行收尾或转移。"
  ],
  "work_process": "视频显示多名工人在建筑物外部区域进行作业，初始阶段一名工人在柱子旁活动，随后离开画面。接着两名工人进入，其中一人使用工具在地面操作，之后两人共同将一根长杆插入红色挡板以搭建支撑结构。随着作业推进，挡板被逐步竖立并固定，最终形成完整的临时围挡。期间有工人进出画面，最后一名工人在远处活动，整体过程呈现从准备到搭建完成的连续动作变化。"
}


"""


from __future__ import annotations

import base64
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any, Sequence

import cv2
import requests


API_KEY = os.getenv("API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "")
VLM_MODEL = os.getenv("VLM_MODEL", "")


def _chat_url() -> str:
    base_url = BASE_URL.rstrip("/")
    if not base_url:
        raise RuntimeError("未配置环境变量 BASE_URL")
    if base_url.endswith("/chat/completions"):
        return base_url
    if base_url.endswith("/v1"):
        return f"{base_url}/chat/completions"
    return f"{base_url}/v1/chat/completions"


def _image_to_url(image: str | Path | bytes | bytearray) -> str:
    if isinstance(image, (bytes, bytearray)):
        encoded = base64.b64encode(image).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    image_value = str(image)
    if image_value.startswith(("http://", "https://", "data:")):
        return image_value

    image_path = Path(image_value).expanduser()
    if not image_path.is_file():
        raise FileNotFoundError(f"图片不存在: {image_path}")

    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_text(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"视觉模型响应格式异常: {payload}") from exc

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
        )

    raise ValueError(f"视觉模型返回了无法识别的文本格式: {content!r}")


def chat_with_vlm(
    prompt: str,
    images: Sequence[str | Path | bytes | bytearray],
) -> str:
    """调用云端 OpenAI 兼容视觉模型，并返回模型生成的文本。"""
    if not API_KEY:
        raise RuntimeError("未配置环境变量 API_KEY")

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    content.extend(
        {
            "type": "image_url",
            "image_url": {"url": _image_to_url(image)},
        }
        for image in images
    )

    response = requests.post(
        _chat_url(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": VLM_MODEL,
            "messages": [{"role": "user", "content": content}],
            "stream": False,
        },
        timeout=120,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"视觉模型调用失败，HTTP {response.status_code}: {response.text[:500]}"
        ) from exc

    try:
        payload = response.json()
    except requests.JSONDecodeError as exc:
        raise ValueError(f"视觉模型返回了非 JSON 响应: {response.text[:500]}") from exc

    return _extract_text(payload)


VISION_ANALYSIS_PROMPT = """
你是一名作业现场视频分析助手。输入图像是按照时间顺序从同一段视频中均匀抽取的帧。
请分析全部帧，并且只输出一个合法的 JSON 对象，不要输出 Markdown、代码块或其他说明文字。

JSON 必须严格包含以下两个字段：
{
  "frames": [
    "第1帧的内容描述",
    "第2帧的内容描述"
  ],
  "work_process": "视频中的作业过程"
}

要求：
1. frames 必须是字符串列表，元素数量必须与输入帧数一致，并按输入图像的时间顺序一一对应；
2. 每个 frames 元素应描述该帧中的主要物体、工具、设备、车辆、安全防护用品、人物数量、人物动作、场景环境以及推测的作业行为；
3. work_process 必须是字符串，结合各帧的时间顺序描述视频中的作业过程和动作变化，不要判断或描述作业类型；
4. 观察事实与推测应明确区分，无法确认的信息写明“无法确定”，不要虚构细节；
5. 所有字段值使用中文，确保输出可以被标准 JSON 解析器直接解析。
""".strip()


def extract_evenly_spaced_frames(
    video: str | Path,
    frame_count: int,
) -> list[Path]:
    """Extract evenly spaced frames from a video into a temporary directory."""
    if frame_count <= 0:
        raise ValueError("frame_count must be greater than 0")

    video_path = Path(video).expanduser()
    if not video_path.is_file():
        raise FileNotFoundError(f"Video does not exist: {video_path}")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"Unable to open video: {video_path}")

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        capture.release()
        raise ValueError(f"Unable to determine video frame count: {video_path}")

    if frame_count == 1:
        frame_indices = [total_frames // 2]
    else:
        last_frame = total_frames - 1
        frame_indices = [
            round(index * last_frame / (frame_count - 1))
            for index in range(frame_count)
        ]

    output_dir = Path(tempfile.mkdtemp(prefix="video_frames_"))
    frame_paths: list[Path] = []

    try:
        for output_index, frame_index in enumerate(frame_indices, start=1):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            success, frame = capture.read()
            if not success:
                raise ValueError(
                    f"Unable to read frame {frame_index} from video: {video_path}"
                )

            frame_path = output_dir / f"frame_{output_index:04d}.jpg"
            if not cv2.imwrite(str(frame_path), frame):
                raise OSError(f"Unable to save extracted frame: {frame_path}")
            frame_paths.append(frame_path)
    except Exception:
        for frame_path in frame_paths:
            frame_path.unlink(missing_ok=True)
        output_dir.rmdir()
        raise
    finally:
        capture.release()

    return frame_paths


def vision_agent(
    video: str | Path,
    frame_count: int = 10,
) -> str:
    """Extract video frames, analyze them with the VLM, and return its response."""
    frame_paths = extract_evenly_spaced_frames(video, frame_count)
    output_dir = frame_paths[0].parent

    try:
        return chat_with_vlm(
            prompt=VISION_ANALYSIS_PROMPT,
            images=frame_paths,
        )
    finally:
        for frame_path in frame_paths:
            frame_path.unlink(missing_ok=True)
        output_dir.rmdir()


def test_vision_agent() -> None:
    video_path = (
        Path(__file__).resolve().parent
        / "media"
        / "110千伏汇景站"
        / (
            "JJBZ0301260520200027_44010000V44010000001310048170_"
            "1779705511_1779706605_1776084737645.mp4"
        )
    )
    result = vision_agent(video_path)
    print(result)


if __name__ == "__main__":
    test_vision_agent()
