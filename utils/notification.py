import os
import json
import logging
import requests
from typing import Optional

def send_notification(title: str, message: str, level: str = "info") -> bool:
    """
    发送系统通知到配置的渠道 (如企业微信/飞书/Server酱等)。
    
    Args:
        title (str): 消息标题
        message (str): 消息主体内容
        level (str): 消息级别 (info, warning, error, alert)
        
    Returns:
        bool: 发送是否成功
    """
    from utils.config import load_config
    config = load_config()
    settings = config.get("settings", {})
    
    webhook_url = settings.get("notification_webhook_url", "")
    platform = settings.get("notification_platform", "wechat") # 'wechat', 'feishu'
    
    # Check env fallback
    if not webhook_url:
        webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "")
        
    if not webhook_url:
        logging.info(f"[Notification Skipped] No webhook URL configured. Title: {title}")
        return False
        
    try:
        if platform == "wechat":
            return _send_wechat_bot(webhook_url, title, message, level)
        elif platform == "feishu":
            return _send_feishu_bot(webhook_url, title, message, level)
        else:
            logging.warning(f"Unsupported notification platform: {platform}")
            return False
            
    except Exception as e:
        logging.error(f"Failed to send notification: {e}")
        return False

def _send_wechat_bot(webhook_url: str, title: str, message: str, level: str) -> bool:
    """企业微信群机器人 Markdown 推送"""
    color = "info"
    if level in ["warning", "alert"]:
        color = "warning"
    elif level == "error":
        color = "warning" # Wechat only supports 'info', 'comment', 'warning'
        
    content = f"### <font color='{color}'>{title}</font>\n\n{message}"
    
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }
    
    response = requests.post(webhook_url, json=payload, timeout=5)
    return response.json().get('errcode') == 0

def _send_feishu_bot(webhook_url: str, title: str, message: str, level: str) -> bool:
    """飞书群机器人富文本推送"""
    color = "blue"
    if level == "warning":
        color = "orange"
    elif level in ["error", "alert"]:
        color = "red"
        
    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": [
                        [
                            {"tag": "text", "text": message}
                        ]
                    ]
                }
            }
        }
    }
    
    response = requests.post(webhook_url, json=payload, timeout=5)
    return response.json().get('StatusCode') == 0 or response.json().get('code') == 0

# Test code block
if __name__ == "__main__":
    send_notification("🚨 测试告警", "这是一条来自 MarketMonitor 的风控测试消息。\n\n**组合:** default\n**状态:** 正常")
