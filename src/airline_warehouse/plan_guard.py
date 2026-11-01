"""Exact saved-plan actions -> review evidence, never authority to apply a plan."""


def inspect_plan(plan, *, imports=None, creates=(), existing=()):
    imports, creates, existing = dict(imports or {}), set(creates), set(existing)
    if set(imports) & (creates | existing) or creates & existing:
        raise ValueError("Plan policy groups must be disjoint")
    expected = set(imports) | creates | existing
    seen = set()
    for resource in plan.get("resource_changes", []):
        address = resource.get("address")
        if resource.get("mode") != "managed" or address not in expected or address in seen:
            raise ValueError("Unexpected or duplicate managed resource in saved plan")
        seen.add(address)
        change = resource["change"]
        actions = change.get("actions")
        imported = change.get("importing")
        if address in imports:
            if actions != ["no-op"] or imported != {"id": imports[address]}:
                raise ValueError(f"Import is not an exact unchanged object: {address}")
        elif imported is not None or actions != (["create"] if address in creates else ["no-op"]):
            raise ValueError(f"Saved plan exceeds the reviewed action scope: {address}")
    if seen != expected:
        raise ValueError("Saved plan omits expected resources")
    return {
        "imports": len(imports),
        "creates": len(creates),
        "unchanged_existing": len(existing),
        "updates": 0,
        "deletions": 0,
        "apply_authorized": False,
    }
