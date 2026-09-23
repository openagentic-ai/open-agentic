from openagentic.application.capabilities import CORE_CAPABILITIES, ENDPOINTS, Capability


def test_every_endpoint_exposes_the_same_core_capabilities():
    assert len(ENDPOINTS) == 7
    assert CORE_CAPABILITIES == frozenset(Capability)
    assert all(endpoint.capabilities == CORE_CAPABILITIES for endpoint in ENDPOINTS)


def test_device_events_are_adapter_specific():
    android = next(x for x in ENDPOINTS if x.endpoint_id == "android")
    web = next(x for x in ENDPOINTS if x.endpoint_id == "web")
    assert "location" in android.device_events
    assert "location" not in web.device_events
