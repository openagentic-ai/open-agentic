from openagentic.control_plane.employee_registry import ROLE_REGISTRY, get_employee_role


def test_all_registered_roles_have_stable_metadata():
    assert len(ROLE_REGISTRY) == 9
    for key, role in ROLE_REGISTRY.items():
        assert role.key == key
        assert role.department
        assert role.title
        assert role.description


def test_unknown_role_does_not_route_to_an_agent():
    assert get_employee_role("printer_repair") is None
