"""
EG-6 Serialization Proof: Test advisory lock prevents duplicate execution.

This test runs two concurrent lock acquisition attempts and proves that:
1. First operation acquires lock
2. Second operation sees lock held and cannot acquire
"""
import asyncio
import logging
from sqlalchemy import text

from app.db.session import engine
from app.core.pg_locks import try_acquire_refresh_lock, release_refresh_lock
from app.tasks.maintenance import _qualified_matview_identifier

# Configure logging to see lock acquisition messages
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')

async def simulate_refresh_with_delay(view_name: str, task_id: str, delay_sec: float):
    """
    Simulate a refresh operation that holds the lock for `delay_sec` seconds.

    Returns "success" if lock acquired, "skipped_already_running" if not.
    """
    async with engine.begin() as conn:
        # Try to acquire lock
        acquired = await try_acquire_refresh_lock(conn, view_name)

        if not acquired:
            print(f"[{task_id}] Lock already held - SKIPPING")
            return "skipped_already_running"

        try:
            print(f"[{task_id}] Lock acquired - RUNNING")
            # Simulate refresh operation
            await asyncio.sleep(delay_sec)
            qualified = _qualified_matview_identifier(view_name, task_id=task_id)
            await conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY " + qualified))
            print(f"[{task_id}] Refresh completed")
            return "success"
        finally:
            # Release lock
            await release_refresh_lock(conn, view_name)
            print(f"[{task_id}] Lock released")


async def test_concurrent_refresh():
    """
    Run two refresh operations concurrently for the same view.

    Expected: One succeeds, one returns "skipped_already_running"
    """
    view_name = "mv_allocation_summary"
    task_id_1 = "task-1"
    task_id_2 = "task-2"

    print("\n=== EG-6 SERIALIZATION PROOF ===\n")
    print(f"Testing concurrent refresh of {view_name}")
    print(f"Task 1 will hold lock for 2 seconds")
    print(f"Task 2 will attempt to acquire same lock concurrently")
    print("\n--- Starting concurrent refresh operations ---\n")

    # Run both refreshes concurrently
    # Task 1 will hold the lock for 2 seconds
    # Task 2 should fail to acquire and skip
    results = await asyncio.gather(
        simulate_refresh_with_delay(view_name, task_id_1, 2.0),
        simulate_refresh_with_delay(view_name, task_id_2, 0.5),
    )

    print("\n--- Results ---\n")
    print(f"Task 1 result: {results[0]}")
    print(f"Task 2 result: {results[1]}")

    # Verify one succeeded and one skipped
    assert "success" in results and "skipped_already_running" in results, \
        f"Expected one success and one skip, got: {results}"

    print("\n=== PASS: Advisory locks prevent duplicate execution ===\n")
    print("Evidence:")
    print(f"  - One task completed: {results.count('success')} success")
    print(f"  - One task skipped: {results.count('skipped_already_running')} skipped_already_running")
    print(f"  - Lock serialization working as expected")

if __name__ == "__main__":
    asyncio.run(test_concurrent_refresh())
