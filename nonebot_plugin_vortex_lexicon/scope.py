from nonebot.adapters import Event


def is_group_message(event: Event) -> bool:
    """判断事件是否来自群聊。
    Args:
        event: 当前事件对象
    用法：
    ```python
    is_group = is_group_message(event)
    ```
    """
    data = getattr(event, "data", None)
    if data is None:
        return False
    return getattr(data, "message_scene", None) == "group" or getattr(data, "group_id", None) is not None


def resolve_scope_group_id(event: Event) -> int:
    """解析事件对应的作用域群号。
    Args:
        event: 当前事件对象
    用法：
    ```python
    group_id = resolve_scope_group_id(event)
    ```
    """
    data = getattr(event, "data", None)
    if data is not None:
        message_scene = getattr(data, "message_scene", None)
        if message_scene == "group":
            peer_id = getattr(data, "peer_id", None)
            if peer_id is not None:
                return int(peer_id)

        data_group_id = getattr(data, "group_id", None)
        if data_group_id is not None:
            return int(data_group_id)

    event_group_id = getattr(event, "group_id", None)
    if event_group_id is not None:
        return int(event_group_id)

    # 私聊或无法识别群号时统一落入默认作用域
    return 0
