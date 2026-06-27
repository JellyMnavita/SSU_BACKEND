DEFAULT_NOTIFICATION_PREFERENCES = {
    "email_alerts": True,
    "push_notifications": False,
    "sms_alerts": False,
    "weekly_report": True,
    "nearby_incidents": True,
}

NOTIFICATION_PREFERENCE_KEYS = frozenset(DEFAULT_NOTIFICATION_PREFERENCES.keys())
