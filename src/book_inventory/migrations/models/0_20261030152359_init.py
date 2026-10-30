from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "customers" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "surname" VARCHAR(100) NOT NULL,
    "booking_count" INT NOT NULL,
    "date_joined" TIMESTAMPTZ NOT NULL
);
COMMENT ON TABLE "customers" IS 'A person who can make bookings. Names are not unique: two customers may share both.';
CREATE TABLE IF NOT EXISTS "inventory_items" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(200) NOT NULL UNIQUE,
    "description" TEXT NOT NULL,
    "remaining_quantity" INT NOT NULL,
    "is_active" BOOL NOT NULL,
    "expiration_date" DATE,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL
);
COMMENT ON TABLE "inventory_items" IS 'A bookable resource. `remaining_quantity` is how many units can be booked at the same time.';
CREATE TABLE IF NOT EXISTS "bookings" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "quantity" INT NOT NULL,
    "start_at" TIMESTAMPTZ NOT NULL,
    "end_at" TIMESTAMPTZ NOT NULL,
    "status" VARCHAR(9) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "customer_id" INT NOT NULL REFERENCES "customers" ("id") ON DELETE RESTRICT,
    "item_id" INT NOT NULL REFERENCES "inventory_items" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_bookings_start_a_38fc08" ON "bookings" ("start_at");
CREATE INDEX IF NOT EXISTS "idx_bookings_end_at_91c483" ON "bookings" ("end_at");
COMMENT ON COLUMN "bookings"."status" IS 'CONFIRMED: confirmed\nCANCELLED: cancelled';
COMMENT ON TABLE "bookings" IS 'A reservation of `quantity` units of an item over the interval [start_at, end_at).';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "eJztWl1z4jYU/SsaPyUzaSahyX69AUu6dBPYIbTd2W3HEbYANbZEZBnCbPPfqyvb+NuBnc"
    "BAxk/A1b2SfK50fY7ED8PlNnG80xbn95RNjA/oh8GwS9SXbNMJMvBsFjeAQeKRo31HgZM2"
    "4pEnBbakso+x4xFlsolnCTqTlDPwbiJBPCLmGAyIj9Hdg4+ZpHJ5h3xGpQc2zBCVxEV8Tg"
    "SSU4IokxDjoO+exEKaWJ4gwmz1eXwK49rcUgMHT7GlIVTkg09MySdEuQs10Pd/lJkymzwS"
    "L/o5uzfHlDh2Ck1qQwfabsrlTNu6TF5pR5j9yLS447ssdp4t5ZSzlbeaHFgnhBGBJYHupf"
    "ABXuY7TpiJCPFgprFLMMVEjE3G2HcgSRAdTCC2GabZ6w/N287QNI1cAqOIBOChyeIMkq+m"
    "6umnn8AUfmmcX7y9ePfrm4t3ykVPc2V5+xQMHQMTBGp4ekPjSbdjiQMPjXEMapTTDaBNhj"
    "wPcARnFcKRIYY4XvYRnud7DXAMaLTs84B+VIhI6pJiVJNxGVTtMPA0+vIyGO9yGVdAOOze"
    "dG6HzZsv0L3reQ+OBqs57EBLQ1uXGevRm2Owc1Ukg+q56gT91R1+QvATfev3OhpN7smJ0C"
    "PGfsNvBswJ+5KbjC9MbCeBjMyRKZXhoJxtmt84qs7uPmdX7UPpe/nstqdYdJjv6ux21eNj"
    "ZpGiXRxGZ7Ks4NpWZYRsjKlwSbTo1s2v0e73rrqDm87HD2jVx9+s3ey1O9fX2goP6Thhz8"
    "/XUhc/mg5hEzlVP99XLIs/m4P2p+bg6H0m072woQEt6cJqCQLA/cTWS0fuZvvl07RNkqAe"
    "0O4zZxnu+wPZj2GJqtyOlu9J7hJhbsT+MlG7Yyl7zwQTdFrx9s1QTUTUiIaIgloZ3xdSa4"
    "Arj+4VF4RO2GeyzL1JMqCG6rHL5oRJLpbdsL8DQ/kpWkaRNd75Ai9WOi+5uhQI6tGJ1DAM"
    "VAkZdNtDo7AuvADA7URXrxTbTD0swRfW8ghb9wssbDO1qKGFN3jGsvLNN7kNN2vBDE80Qv"
    "AoMPEs/AUnJ8nUlB+dRE+39tnJTPlyhhZTDgwHufieoOj85RT11Bw8hAVBjEsUpFrBulDO"
    "0UAqZIm8KfiMuJwWHZ5sZYz69GS/Tk/0Z6FUKMY18t+dONgmuCm2f352tgbfV16ljF+3ZQ"
    "5TfLEpxImQGuX1UA7LkgLRZwXiqrRK5OJ2xwrP9rpgxNCCqDT/5ZSRgvJbrVozoa9Qth6I"
    "TC09Nspx/3ICldtsBSdMrTDy6vOAOPrWpZyzJq6UDjPpOcr6tE2OmdZQBUQzJ7LK2SaNXE"
    "1QLGtzTsg7dAG3atwXFjlFd4K4CgEoofHVGvXQlC8U+WPL8JoN6OMoII/ERljqezZPzR/p"
    "AlDAPbc6Vs1Baw66L9CmuFFjLW7UqOBGjTw3Ss4sB/KQPJYs3kzYDi8DNrwDeJGXdefrMP"
    "WejhA9uml+PU69q6/7vd8i90QG2tf9Vgb4fL3aoHYUB9eHlkXHwJ6p3lx0XlBDFMlwCGYl"
    "5TkZl0FWvT6cbUEb1ZfdLvFWv3+dWuKtbnYN/3HT6ijppde7cqLB6VoecPI4o0LTOxO4e7"
    "EsKLlDzodWyYI1UhCiuS+LuyIDwPLrG8H6RtDwZ/ZPZj0dWWd9X7JeILBXirDW14egr5tE"
    "UGtqFAjrsOWkSlHj2Oc5IV0OQy1L90uWzonwCkVTuTJNhLzCo/vG5eU68vTyslyeQluaAs"
    "Gm2gDh0P0VoruVixE1oiRFVyK/3/Z7JcwyDskSDGpJ9B9yqHeIsrMCXACjWv5nlX6GHkAH"
    "raL/0uzyDwlP/wNe4wKD"
)
