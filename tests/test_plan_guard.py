import copy
import unittest

from airline_warehouse.plan_guard import inspect_plan


class SavedPlanGuardTests(unittest.TestCase):
    def plan(self, changes):
        return {"resource_changes": changes}

    def change(self, address, actions, imported=None):
        change = {"actions": actions}
        if imported is not None:
            change["importing"] = {"id": imported}
        return {"address": address, "mode": "managed", "change": change}

    def test_only_exact_imports_are_admissible(self):
        imports = {"snowflake_database.airline": '"AIRLINE_DB"'}
        plan = self.plan([self.change("snowflake_database.airline", ["no-op"], '"AIRLINE_DB"')])
        self.assertEqual(inspect_plan(plan, imports=imports)["imports"], 1)
        for actions in (["update"], ["delete", "create"], ["create"], ["read"]):
            bad = copy.deepcopy(plan)
            bad["resource_changes"][0]["change"]["actions"] = actions
            with self.subTest(actions=actions), self.assertRaises(ValueError):
                inspect_plan(bad, imports=imports)
        plan["resource_changes"][0]["change"]["importing"]["id"] = '"OTHER_DB"'
        with self.assertRaises(ValueError):
            inspect_plan(plan, imports=imports)

    def test_missing_duplicate_or_extra_resources_are_not_blessed(self):
        row = self.change("snowflake_database.airline", ["no-op"], '"AIRLINE_DB"')
        expected = {row["address"]: '"AIRLINE_DB"'}
        for rows in ([], [row, row], [row, self.change("snowflake_database.other", ["create"])]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                inspect_plan(self.plan(rows), imports=expected)

    def test_only_named_additions_and_existing_noops_are_admissible(self):
        rows = [
            self.change("aws_vpc.jobs", ["create"]),
            self.change("aws_s3_bucket.bts", ["no-op"]),
        ]
        policy = dict(creates={"aws_vpc.jobs"}, existing={"aws_s3_bucket.bts"})
        self.assertEqual(inspect_plan(self.plan(rows), **policy)["creates"], 1)
        rows[1]["change"]["actions"] = ["update"]
        with self.assertRaises(ValueError):
            inspect_plan(self.plan(rows), **policy)

    def test_safe_review_is_not_apply_authorization(self):
        result = inspect_plan(self.plan([]))
        self.assertFalse(result["apply_authorized"])

    def test_unreviewed_data_reads_are_not_implicitly_authorized(self):
        row = self.change("data.aws_secretsmanager_secret_version.unreviewed", ["read"])
        row["mode"] = "data"
        with self.assertRaises(ValueError):
            inspect_plan(self.plan([row]))
