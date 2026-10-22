from backend.safety.state import (
    is_safe,
    current_status
)


def get_safety_status():

    return {
        "safe": is_safe,
        "status": current_status
    }