"""模块说明（中文）：`src/openagentic/devices/router.py`。

Devices REST API —— 设备节点与能力目录（前端 DevicesPage）。
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("")
async def list_devices():
    """返回可用设备节点及其能力（当前为静态目录）。

    前端 DevicesPage 可从此接口获取设备列表，替换硬编码数据。
    """
    return {
        "nodes": [
            {
                "id": "camera",
                "name": "相机",
                "type": "camera",
                "enabled": True,
                "available": True,
                "capabilities": [
                    {"id": "camera.snap", "name": "相机拍照", "description": "使用设备相机拍摄照片", "enabled": True},
                    {"id": "camera.clip", "name": "相机录像", "description": "使用设备相机录制视频", "enabled": True},
                ],
            },
            {
                "id": "screen",
                "name": "屏幕录制",
                "type": "screen",
                "enabled": True,
                "available": True,
                "capabilities": [
                    {"id": "screen.record", "name": "屏幕录制", "description": "录制屏幕内容", "enabled": True},
                    {"id": "screen.screenshot", "name": "屏幕截图", "description": "截取屏幕内容", "enabled": True},
                ],
            },
            {
                "id": "location",
                "name": "定位",
                "type": "location",
                "enabled": True,
                "available": True,
                "capabilities": [
                    {"id": "location.get", "name": "获取定位", "description": "获取设备当前地理位置", "enabled": True},
                ],
            },
            {
                "id": "notification",
                "name": "通知推送",
                "type": "notification",
                "enabled": True,
                "available": True,
                "capabilities": [
                    {"id": "notification.send", "name": "发送通知", "description": "向设备发送通知", "enabled": True},
                ],
            },
            {
                "id": "system",
                "name": "系统命令",
                "type": "system",
                "enabled": True,
                "available": True,
                "capabilities": [
                    {"id": "system.run", "name": "执行命令", "description": "在设备上执行系统命令", "enabled": True},
                    {"id": "system.notify", "name": "系统通知", "description": "发送系统级通知", "enabled": True},
                ],
            },
        ]
    }
