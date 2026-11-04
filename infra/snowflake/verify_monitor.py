"""Read-only verification of the attachment the pinned provider cannot read."""

import json
from decimal import Decimal

from airline_warehouse.connection import connect_as
from airline_warehouse.deadlines import DeadlineConnection
from airline_warehouse.load import check_account_monitor


def verify(connection):
    with DeadlineConnection(connection, 60).cursor() as cursor:
        cursor.execute("SHOW RESOURCE MONITORS LIKE 'AIRLINE_BUDGET'")
        names = [item[0].lower() for item in cursor.description]
        rows = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    if len(rows) != 1:
        raise ValueError("Expected exactly one visible AIRLINE_BUDGET monitor")
    check_account_monitor(rows[0])
    row = rows[0]
    if (
        Decimal(str(row["credit_quota"])) != Decimal("10")
        or row["frequency"] != "MONTHLY"
        or Decimal(str(row["suspend_immediately_at"]).removesuffix("%")) != 100
    ):
        raise ValueError("Existing quota, frequency or immediate suspension differs")
    return {
        key: str(rows[0][key])
        for key in ("name", "level", "credit_quota", "frequency", "suspend_immediately_at")
    }


if __name__ == "__main__":
    with connect_as("publisher") as connection:
        print(json.dumps(verify(connection), indent=2))
