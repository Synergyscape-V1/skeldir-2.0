"""
Channel Service - Canonical APIs for Channel Governance

This module provides the canonical APIs for channel state transitions and
assignment corrections, enforcing the state machine rules and relying on
DB triggers to log audit records.

Related Documents:
- docs/database/CHANNEL_GOVERNANCE_AUDITABILITY_IMPLEMENTATION.md (Implementation guide)
- db/docs/channel_contract.md (Channel governance contract)
"""

import json
from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# Custom exceptions
class ChannelNotFoundError(Exception):
    """Raised when a channel code doesn't exist in channel_taxonomy."""
    pass


class StateMachineError(Exception):
    """Raised when a state transition violates the state machine rules."""
    pass


class EntityNotFoundError(Exception):
    """Raised when an entity (event/allocation) doesn't exist."""
    pass


class PermissionError(Exception):
    """Raised when tenant_id doesn't match entity's tenant."""
    pass


# Valid state transitions (from Phase 1)
ALLOWED_TRANSITIONS = {
    ('draft', 'active'),
    ('active', 'deprecated'),
    ('deprecated', 'archived'),
    ('active', 'archived'),  # Fast-track retirement (rare)
}

# Terminal states (no transitions out)
TERMINAL_STATES = {'archived'}

# Disallowed transitions
DISALLOWED_TRANSITIONS = {
    ('deprecated', 'active'),  # No rollback from deprecated
    ('archived', 'active'),    # No transitions from archived
    ('archived', 'deprecated'),
    ('archived', 'draft'),
}


def transition_taxonomy_state(
    session: Session,
    channel_code: str,
    to_state: str,
    changed_by: str,
    reason: Optional[str] = None,
    metadata: Optional[dict] = None
) -> None:
    """
    Transition a channel taxonomy entry to a new state.
    
    This is the canonical API for all channel state changes. It enforces
    the state machine rules and relies on DB trigger to log the transition.
    
    Args:
        session: SQLAlchemy database session
        channel_code: Canonical channel code (must exist in channel_taxonomy)
        to_state: Target state ('draft', 'active', 'deprecated', 'archived')
        changed_by: User/service identifier (e.g., 'admin@skeldir.com', 'migration:20251117')
        reason: Optional human-readable explanation
        metadata: Optional JSONB context (e.g., {'ticket': 'SK-123', 'migration_id': '20251117'})
    
    Raises:
        ChannelNotFoundError: If channel_code doesn't exist
        StateMachineError: If transition violates state machine rules
        ValueError: If changed_by is empty or to_state is invalid
    
    Behavior:
        1. Validates transition against state machine (Phase 1)
        2. Sets session variables for trigger to read
        3. Updates channel_taxonomy.state
        4. DB trigger automatically logs transition to channel_state_transitions
        5. Clears session variables
    """
    # Validate inputs
    if not changed_by:
        raise ValueError("changed_by is required and cannot be empty")
    
    if to_state not in {'draft', 'active', 'deprecated', 'archived'}:
        raise ValueError(f"Invalid to_state: {to_state}. Must be one of: draft, active, deprecated, archived")
    
    # Get current state
    result = session.execute(
        text("SELECT state FROM channel_taxonomy WHERE code = :code"),
        {"code": channel_code}
    ).fetchone()
    
    if not result:
        raise ChannelNotFoundError(f"Channel code '{channel_code}' not found in channel_taxonomy")
    
    from_state = result[0]
    
    # Validate transition
    if from_state == to_state:
        # No-op transition (allowed but will not produce audit record)
        return
    
    transition = (from_state, to_state)
    
    if transition in DISALLOWED_TRANSITIONS:
        raise StateMachineError(
            f"Invalid transition: {from_state} → {to_state}. "
            f"This transition is disallowed by the state machine."
        )
    
    if transition not in ALLOWED_TRANSITIONS:
        raise StateMachineError(
            f"Invalid transition: {from_state} → {to_state}. "
            f"Allowed transitions: {ALLOWED_TRANSITIONS}"
        )
    
    # Set session variables for trigger to read
    session.execute(
        text("SET LOCAL app.channel_state_change_by = :changed_by"),
        {"changed_by": changed_by}
    )
    
    if reason:
        session.execute(
            text("SET LOCAL app.channel_state_change_reason = :reason"),
            {"reason": reason}
        )
    else:
        session.execute(text("SET LOCAL app.channel_state_change_reason = ''"))
    
    # Update state (trigger will log transition)
    try:
        session.execute(
            text("UPDATE channel_taxonomy SET state = :to_state WHERE code = :code"),
            {"to_state": to_state, "code": channel_code}
        )
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise ValueError(f"Failed to update channel state: {e}")
    finally:
        # Clear session variables
        session.execute(text("RESET app.channel_state_change_by"))
        session.execute(text("RESET app.channel_state_change_reason"))


def correct_assignment(
    session: Session,
    entity_type: str,
    entity_id: UUID,
    to_channel: str,
    reason: str,
    corrected_by: str,
    tenant_id: UUID,
    metadata: Optional[dict] = None
) -> None:
    """
    Correct a channel assignment for an event or allocation.
    
    This is the canonical API for all post-ingestion channel corrections.
    It validates the target channel is active and relies on DB trigger
    to log the correction.
    
    Args:
        session: SQLAlchemy database session
        entity_type: 'event' or 'allocation'
        entity_id: UUID of the entity to correct
        to_channel: Target channel code (must be in 'active' state)
        reason: Mandatory explanation for correction
        corrected_by: User/service identifier
        tenant_id: Tenant owning the entity
        metadata: Optional JSONB context
    
    Raises:
        ValueError: If reason is empty, to_channel is not active, or entity_type is invalid
        EntityNotFoundError: If entity doesn't exist
        PermissionError: If tenant_id doesn't match entity's tenant
    
    Behavior:
        1. Validates to_channel is in 'active' state
        2. Validates entity exists and belongs to tenant_id
        3. Sets session variables for trigger to read
        4. Updates attribution_events.channel or attribution_allocations.channel_code
        5. DB trigger automatically logs correction to channel_assignment_corrections
        6. Clears session variables
    """
    # Validate inputs
    if not reason:
        raise ValueError("reason is required and cannot be empty for corrections")
    
    if not corrected_by:
        raise ValueError("corrected_by is required and cannot be empty")
    
    if entity_type not in {'event', 'allocation'}:
        raise ValueError(f"Invalid entity_type: {entity_type}. Must be 'event' or 'allocation'")
    
    # Validate target channel is active
    channel_result = session.execute(
        text("SELECT state FROM channel_taxonomy WHERE code = :code"),
        {"code": to_channel}
    ).fetchone()
    
    if not channel_result:
        raise ChannelNotFoundError(f"Channel code '{to_channel}' not found in channel_taxonomy")
    
    channel_state = channel_result[0]
    if channel_state != 'active':
        raise ValueError(
            f"Channel '{to_channel}' is not active (state: {channel_state}). "
            f"Cannot assign to deprecated/archived channels."
        )
    
    # Validate entity exists and belongs to tenant
    if entity_type == "allocation":
        entity_result = session.execute(
            text("SELECT tenant_id, channel_code FROM attribution_allocations WHERE id = :id"),
            {"id": str(entity_id)},
        ).fetchone()
    else:  # entity_type == "event"
        entity_result = session.execute(
            text("SELECT tenant_id, channel FROM attribution_events WHERE id = :id"),
            {"id": str(entity_id)},
        ).fetchone()
    
    if not entity_result:
        raise EntityNotFoundError(f"{entity_type.capitalize()} with id '{entity_id}' not found")
    
    entity_tenant_id, current_channel = entity_result
    
    if UUID(str(entity_tenant_id)) != tenant_id:
        raise PermissionError(
            f"Entity belongs to tenant '{entity_tenant_id}', not '{tenant_id}'"
        )
    
    # No-op check
    if current_channel == to_channel:
        # No correction needed (will not produce audit record)
        return
    
    # Set session variables for trigger to read
    session.execute(
        text("SET LOCAL app.current_tenant_id = :tenant_id"),
        {"tenant_id": str(tenant_id)}
    )
    
    session.execute(
        text("SET LOCAL app.correction_by = :corrected_by"),
        {"corrected_by": corrected_by}
    )
    
    session.execute(
        text("SET LOCAL app.correction_reason = :reason"),
        {"reason": reason}
    )
    
    try:
        if entity_type == "allocation":
            # attribution_allocations is mutable; its trigger logs to channel_assignment_corrections.
            session.execute(
                text("UPDATE attribution_allocations SET channel_code = :to_channel WHERE id = :id"),
                {"to_channel": to_channel, "id": str(entity_id)},
            )
        else:
            # attribution_events is immutable by schema; record an append-only correction.
            session.execute(
                text(
                    """
                    INSERT INTO channel_assignment_corrections (
                        tenant_id, entity_type, entity_id,
                        from_channel, to_channel, corrected_by, reason, metadata
                    ) VALUES (
                        :tenant_id, 'event', :entity_id,
                        :from_channel, :to_channel, :corrected_by, :reason, CAST(:metadata AS jsonb)
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "entity_id": str(entity_id),
                    "from_channel": str(current_channel),
                    "to_channel": to_channel,
                    "corrected_by": corrected_by,
                    "reason": reason,
                    "metadata": json.dumps(metadata or {}),
                },
            )
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise ValueError(f"Failed to correct assignment: {e}")
    finally:
        # Clear session variables
        session.execute(text("RESET app.current_tenant_id"))
        session.execute(text("RESET app.correction_by"))
        session.execute(text("RESET app.correction_reason"))

