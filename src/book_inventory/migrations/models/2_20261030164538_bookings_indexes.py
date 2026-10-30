from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "idx_bookings_end_at_91c483";
        DROP INDEX IF EXISTS "idx_bookings_start_a_38fc08";
        CREATE INDEX IF NOT EXISTS "idx_bookings_item_start" ON "bookings" ("item_id", "start_at");
        CREATE INDEX IF NOT EXISTS "idx_bookings_confirmed_end_at" ON "bookings" ("end_at") WHERE status = 'confirmed';
        CREATE INDEX IF NOT EXISTS "idx_bookings_confirmed_customer" ON "bookings" ("customer_id") WHERE status = 'confirmed';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "idx_bookings_confirmed_customer";
        DROP INDEX IF EXISTS "idx_bookings_confirmed_end_at";
        DROP INDEX IF EXISTS "idx_bookings_item_start";
        CREATE INDEX IF NOT EXISTS "idx_bookings_start_a_38fc08" ON "bookings" ("start_at");
        CREATE INDEX IF NOT EXISTS "idx_bookings_end_at_91c483" ON "bookings" ("end_at");"""


MODELS_STATE = (
    "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"
    "6J8z2/z7wfx/WlyERA=="
)
