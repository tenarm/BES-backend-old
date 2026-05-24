import logging
from datetime import datetime
from core.events import event_bus, BaseEventPayload

logger = logging.getLogger(__name__)

async def emit_entity_created(entity_id: str, entity_name: str):
    payload = BaseEventPayload(
        emitter_module="settings",
        event_type="SETTINGS_ENTITY_CREATED",
        data={"entity_id": entity_id, "name": entity_name}
    )
    await event_bus.emit(payload)

async def emit_company_profile_updated(updater_name: str, tenant_name: str):
    payload = BaseEventPayload(
        emitter_module="settings",
        event_type="COMPANY_PROFILE_UPDATED",
        data={
            "updater_name": updater_name,
            "tenant_name": tenant_name,
            "timestamp": datetime.now().isoformat()
        }
    )
    await event_bus.emit(payload)
    logger.info(f"[Settings] COMPANY_PROFILE_UPDATED event emitted by user '{updater_name}'")

async def emit_subsidiary_created(subsidiary_id: str, name: str):
    payload = BaseEventPayload(
        emitter_module="settings",
        event_type="SUBSIDIARY_CREATED",
        data={
            "subsidiary_id": subsidiary_id,
            "name": name,
            "timestamp": datetime.now().isoformat()
        }
    )
    await event_bus.emit(payload)
    logger.info(f"[Settings] SUBSIDIARY_CREATED event emitted for '{name}'")

async def emit_posting_period_locked(period_id: str, period_name: str, updater_name: str):
    payload = BaseEventPayload(
        emitter_module="settings",
        event_type="POSTING_PERIOD_LOCKED",
        data={
            "period_id": period_id,
            "period_name": period_name,
            "updater_name": updater_name,
            "timestamp": datetime.now().isoformat()
        }
    )
    await event_bus.emit(payload)
    logger.info(f"[Settings] POSTING_PERIOD_LOCKED event emitted for '{period_name}' by user '{updater_name}'")

async def emit_user_invited(email: str, token: str):
    payload = BaseEventPayload(
        emitter_module="settings",
        event_type="USER_INVITED",
        data={
            "target_email": email,
            "invitation_link": f"/register?token={token}",
            "timestamp": datetime.now().isoformat()
        }
    )
    await event_bus.emit(payload)
    logger.info(f"[Settings] USER_INVITED event emitted for '{email}'")

async def emit_user_role_changed(role_id: str, role_name: str):
    payload = BaseEventPayload(
        emitter_module="settings",
        event_type="USER_ROLE_CHANGED",
        data={
            "role_id": role_id,
            "role_name": role_name,
            "timestamp": datetime.now().isoformat()
        }
    )
    await event_bus.emit(payload)
    logger.info(f"[Settings] USER_ROLE_CHANGED event emitted for role ID '{role_id}' ({role_name})")

async def emit_user_session_revoked(token_id: str, user_id: str):
    payload = BaseEventPayload(
        emitter_module="settings",
        event_type="USER_SESSION_REVOKED",
        data={
            "token_id": token_id,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
    )
    await event_bus.emit(payload)
    logger.info(f"[Settings] USER_SESSION_REVOKED event emitted for token ID '{token_id}' (User: {user_id})")

async def emit_user_offboarded(user_id: str, username: str, updater_name: str):
    payload = BaseEventPayload(
        emitter_module="settings",
        event_type="USER_OFFBOARDED",
        data={
            "user_id": user_id,
            "username": username,
            "updater_name": updater_name,
            "timestamp": datetime.now().isoformat()
        }
    )
    await event_bus.emit(payload)
    logger.info(f"[Settings] USER_OFFBOARDED event emitted for user '{username}' by admin '{updater_name}'")

def register_event_handlers():
    logger.info("[Settings] Event handlers registered")

