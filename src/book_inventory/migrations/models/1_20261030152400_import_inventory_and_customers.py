"""Import the seed data from ../data/inventory.csv and ../data/members.csv (-> customers).

The CSV files are a frozen snapshot: edit them and nothing re-imports, because this migration
runs once. Add a new migration for later data changes.
"""

import csv
from datetime import UTC, date, datetime
from pathlib import Path

from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True

# The work is done through `db` above; Aerich still wants SQL back, and asyncpg rejects "".
_NOOP = "SELECT 1"

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _read(filename: str) -> list[dict[str, str]]:
    with (DATA_DIR / filename).open(newline="", encoding="utf-8-sig") as f:
        return [{k: v.strip() for k, v in row.items()} for row in csv.DictReader(f)]


def _items() -> list[tuple[str, str, int, date]]:
    """(name, description, remaining_quantity, expiration_date) per row.

    Item names are unique, so a repeated title gets a " (2)", " (3)" ... suffix.
    """
    seen: dict[str, int] = {}
    items = []
    for row in _read("inventory.csv"):
        title = row["title"]
        seen[title] = seen.get(title, 0) + 1
        name = title if seen[title] == 1 else f"{title} ({seen[title]})"
        expires = datetime.strptime(row["expiration_date"], "%d/%m/%Y").date()
        items.append((name, row["description"], int(row["remaining_count"]), expires))
    return items


def _customers() -> list[tuple[str, str, int, datetime]]:
    """(name, surname, booking_count, date_joined) per row; naive timestamps are read as UTC."""
    return [
        (
            row["name"],
            row["surname"],
            int(row["booking_count"]),
            datetime.fromisoformat(row["date_joined"]).replace(tzinfo=UTC),
        )
        for row in _read("members.csv")
    ]


async def upgrade(db: BaseDBAsyncClient) -> str:
    # Existing rows win: never overwrite an item that is already there.
    await db.execute_many(
        'INSERT INTO "inventory_items"'
        ' ("name", "description", "remaining_quantity", "is_active", "expiration_date",'
        ' "created_at", "updated_at")'
        " VALUES ($1, $2, $3, TRUE, $4, NOW(), NOW())"
        ' ON CONFLICT ("name") DO NOTHING',
        [list(item) for item in _items()],
    )
    await db.execute_many(
        'INSERT INTO "customers" ("name", "surname", "booking_count", "date_joined")'
        " VALUES ($1, $2, $3, $4)",
        [list(customer) for customer in _customers()],
    )
    return _NOOP


async def downgrade(db: BaseDBAsyncClient) -> str:
    # Remove only what was imported; items and customers that have bookings are kept.
    await db.execute_many(
        'DELETE FROM "inventory_items" WHERE "name" = $1'
        ' AND NOT EXISTS (SELECT 1 FROM "bookings" WHERE "item_id" = "inventory_items"."id")',
        [[name] for name, *_ in _items()],
    )
    await db.execute_many(
        'DELETE FROM "customers" WHERE "name" = $1 AND "surname" = $2 AND "date_joined" = $3'
        ' AND NOT EXISTS (SELECT 1 FROM "bookings" WHERE "customer_id" = "customers"."id")',
        [[name, surname, joined] for name, surname, _, joined in _customers()],
    )
    return _NOOP


MODELS_STATE = (
    "eJztWltz4jYU/isaPyUzaSahyd7egCVdulx2iNvu7LbjCFuAG1sisgxhtvnv1ZFtfHdgJz"
    "CQ8RNwdI4kf0c6/j6JH5rLLOJ45y3G7m061T6gHxrFLpFfsk1nSMPzedwABoHHjvIdB07K"
    "iMee4NgU0j7BjkekySKeye25sBkF7ybixCN8gcGA2ATdPfiYClus7pBPbeGBDVNkC+Iiti"
    "AciRlBNhUQ46DvnsBcGFicIUIt+Xl6DuNazJQDB0+xoyFk5INPDMGmRLpzOdD3f6TZphZ5"
    "JF70c35vTGziWCk0bQs6UHZDrObK1qXiRjnC7MeGyRzfpbHzfCVmjK695eTAOiWUcCwIdC"
    "+4D/BS33HCTESIBzONXYIpJmIsMsG+A0mC6GACsU0zjMFQN247umFouQRGEQnAQ5PJKCRf"
    "TtVTTz+FKfzSuLx6e/Xu1zdX76SLmuba8vYpGDoGJghU8Ax07Um1Y4EDD4VxDGqU0y2gTY"
    "Y8D3AEZxXCkSGGOF72EZ6XBw1wDGi07POAfpSICNslxagm4zKoWmHgefTlZTDe5zKugFDv"
    "9ju3erP/Bbp3Pe/BUWA19Q60NJR1lbGevDkFO5NFMqie607QX139E4Kf6Ntw0FFoMk9MuR"
    "ox9tO/aTAn7AtmULY0sJUEMjJHplSGg3K2bX7jqDq7h5xduQ+F7+Wz255h3qG+q7LblY+P"
    "qUmKdnEYncmyhGtXlRGyMbG5S6JFt2l+tfZwcNMd9TsfP6B1H3/TdnPQ7vR6ygoP6TjKOu"
    "x/6XX0wNedO0SE4z1fYV38aDiETsVM/nxfsVj+bI7an5qjk/eZ/A/Chga0pMutyQnA+RMb"
    "Mh25n02ZT94uqYN8QGtInVVYDY5kl4aFq3KTmr4nmEu4sRUnzETtj7scPD9MkGzJ5rdDNR"
    "FRIxoiChpmcl9IuAGuPLo3jBN7Sj+TVe79kgE11JRduiBUML7qhv0dGcpP0TKKrPHO53i5"
    "Vn/J1SVBkI8u3ztgH8kSMuq2da2wLrwAwO1EV68U20w9LMEX1vIYm/dLzC0jtaihhTVYxr"
    "L2zTe5DTdrwRRPFULwKDDxLPwF5ynJ1JQfqERPt/GJylz6MoqWMwa8B7n4nqDoVOYcDeQc"
    "PIQ5QZQJFKRawrqUztFAMmSFvBn4jJmYFR2p7GSM+kzlsM5U1GehgCjGNfLfn2TYJbgptn"
    "95cbEB35depYxftWWOWHy+LcSJkBrlzVAOy5IE0acF4qq0SuTi9scKLw66YMTQgqg0/mU2"
    "JQXlt1q1ZkJfoWw9EplaepiU4/7lBCq32QrOnVph5M3nEXHUXUw5Z01cNB1n0nOU9WmXHD"
    "OtoQqIZk5klbNNO3I1QLFszDkh79AF3LUxn5vkHN1x4koEoITGF262h2ZsKckfXYWXb0Af"
    "xwF5JBbCAjEpZ4oo5y6GqBlnzTgPBdoUE2psxIQaFUyokWdCyZnlQNbJY8nizYTt8UJgy3"
    "uAF3k1d77qqbdyhOhJv/n1NPVm7g0Hv0XuiQy0e8NWBvh8mdqidhQH10eURYe+niHfU/ai"
    "oIZISuEQTEvKczIug6x8azi7gjaqL/td4q3hsJda4q1udg3/0W91pNBS61062cFZWh5w8j"
    "i3uSJzBjD1YhFQco+cD60SARukIETzUBZ3RQaA09f3f/X9n+bPrZ/MejqyzvqhZL1ATq/1"
    "X62mj0FNNwm3zZlWIKPDlrMq/Yxjn+dkczkMtSw9LFm6INwrFE3lyjQR8goP6hvX15vI0+"
    "vrcnkKbWkKBJtqC4RD91eI7k6uQeSIghRdgPx+OxyUMMs4JEswbFOg/5Bje8coOyvABTCq"
    "5X9W6WfoAXTQKvrnzD7/fvD0P0qUA58="
)
