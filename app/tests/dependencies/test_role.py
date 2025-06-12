from app.dependencies.role import Role


def test_role_properties():
    assert Role.TENANT.role_name == "tenant"
    assert Role.TENANT.is_admin is False
    assert Role.TENANT.is_multitenant is True

    assert Role.TENANT_ADMIN.role_name == "tenant-admin"
    assert Role.TENANT_ADMIN.is_admin is True
    assert Role.TENANT_ADMIN.is_multitenant is True

    assert Role.GOVERNANCE.role_name == "governance"
    assert Role.GOVERNANCE.is_admin is True
    assert Role.GOVERNANCE.is_multitenant is False

    assert Role.from_str("tenant") == Role.TENANT
    assert Role.from_str("tenant-admin") == Role.TENANT_ADMIN
    assert Role.from_str("governance") == Role.GOVERNANCE
    assert Role.from_str("") is None
