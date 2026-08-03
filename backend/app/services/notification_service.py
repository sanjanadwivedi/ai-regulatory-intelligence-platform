import datetime
from typing import List, Dict, Any

class NotificationService:
    """
    Notification Dispatcher Service
    Handles outbound notifications for compliance alerts, task assignments, and review SLA breaches.
    """
    _notifications = [
        {
            "id": "notif-1",
            "type": "COMPLIANCE_ALERT",
            "title": "New High-Severity Directive Issued",
            "message": "RBI Master Direction on IT Infrastructure & Cyber Resilience Controls requires action.",
            "timestamp": datetime.datetime.now().isoformat(),
            "read": False,
            "channel": "SYSTEM"
        },
        {
            "id": "notif-2",
            "type": "TASK_ASSIGNMENT",
            "title": "Task Assigned to You",
            "message": "Update Retail KYC SOP for 2-Year High-Risk Cadence assigned by Chief Compliance Officer.",
            "timestamp": datetime.datetime.now().isoformat(),
            "read": False,
            "channel": "EMAIL"
        }
    ]

    @classmethod
    def get_user_notifications(cls) -> List[Dict[str, Any]]:
        return cls._notifications

    @classmethod
    def mark_as_read(cls, notification_id: str) -> bool:
        for n in cls._notifications:
            if n["id"] == notification_id:
                n["read"] = True
                return True
        return False

    @classmethod
    def dispatch_alert(cls, title: str, message: str, channel: str = "SYSTEM") -> Dict[str, Any]:
        new_notif = {
            "id": f"notif-{len(cls._notifications) + 1}",
            "type": "ALERT",
            "title": title,
            "message": message,
            "timestamp": datetime.datetime.now().isoformat(),
            "read": False,
            "channel": channel
        }
        cls._notifications.insert(0, new_notif)
        return new_notif
