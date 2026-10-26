"""C4 tests use caller-supplied demo facts and forbid outbound networking."""
from copy import deepcopy
from decimal import Context, localcontext
import json
import socket

import pytest
import requests

from tools.disruption_simulator import DisruptionSimulationError, DisruptionSimulator
from tools.hotel_search import HotelSearchTool


CONTEXTS = {
    'flight_cancelled': {'trip_id': 'demo-trip', 'flight': {
        'flight_id': 'demo-flight', 'origin': 'HKG', 'destination': 'SIN',
        'departure_date': '2026-11-15'}},
    'hotel_unavailable': {'trip_id': 'demo-trip', 'hotel': {
        'hotel_id': 'demo-hotel', 'location': 'Singapore, SG',
        'check_in': '2026-11-15', 'check_out': '2026-11-18', 'guests': 1, 'rooms': 1}},
    'meeting_time_changed': {'trip_id': 'demo-trip', 'meeting': {
        'meeting_id': 'demo-meeting', 'original_start': '2026-11-16T09:00:00+08:00',
        'new_start': '2026-11-16T14:00:00+08:00'}},
    'budget_reduced': {'trip_id': 'demo-trip', 'budget': {
        'currency': 'SGD', 'original_amount': '2500.00', 'new_amount': '1800.00'}},
}
EVENT_KEYS = {'type', 'severity', 'message', 'source', 'data_mode',
              'confirmed_disruption', 'requires_replanning_assessment', 'affected_trip', 'supporting_data'}


@pytest.fixture(autouse=True)
def no_outbound_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('C4 must not make outbound calls')
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)


@pytest.mark.parametrize('scenario', CONTEXTS)
def test_scenarios_share_schema_and_mock_provenance(scenario):
    event = DisruptionSimulator().simulate(scenario, CONTEXTS[scenario])
    assert set(event) == EVENT_KEYS
    assert set(event['affected_trip']) == {'trip_id', 'flight', 'hotel', 'meeting', 'budget'}
    assert event['type'] == scenario.upper()
    assert event['severity'] == ('HIGH' if scenario in ['flight_cancelled', 'hotel_unavailable'] else 'MEDIUM')
    assert event['source'] == 'disruption_simulator'
    assert event['data_mode'] == 'mock'
    assert event['confirmed_disruption'] is False
    assert event['requires_replanning_assessment'] is True
    assert json.loads(json.dumps(event, allow_nan=False)) == event
    assert 'approval_status' not in event and 'booked' not in event


@pytest.mark.parametrize('scenario', CONTEXTS)
def test_deterministic_and_no_context_mutation(scenario):
    context = deepcopy(CONTEXTS[scenario])
    before = deepcopy(context)
    simulator = DisruptionSimulator()
    first = simulator.simulate(scenario, context)
    assert first == simulator.simulate(scenario, context) == DisruptionSimulator().simulate(scenario, context)
    first['affected_trip']['trip_id'] = 'caller-mutated'
    assert simulator.simulate(scenario, context)['affected_trip']['trip_id'] == 'demo-trip'
    assert context == before


def test_hotel_reuses_c2_fully_booked_and_discards_clock(monkeypatch):
    original = HotelSearchTool.search_hotels
    calls = []
    def observed(self, *args, **kwargs):
        calls.append((self.provider, self.mock_scenario, args, kwargs))
        result = original(self, *args, **kwargs)
        result['retrieved_at'] = str(len(calls))
        return result
    monkeypatch.setattr(HotelSearchTool, 'search_hotels', observed)
    simulator = DisruptionSimulator()
    first = simulator.simulate('hotel_unavailable', CONTEXTS['hotel_unavailable'])
    assert first == simulator.simulate('hotel_unavailable', CONTEXTS['hotel_unavailable'])
    assert calls[0][:2] == ('mock', 'fully_booked')
    assert first['affected_trip']['hotel']['nights'] == 3
    assert first['supporting_data'] == dict(provider='mock', data_mode='mock', mock_scenario='fully_booked',
                                           status='no_results', result_count=0)
    assert 'retrieved_at' not in json.dumps(first)


def test_unrelated_booking_and_approval_facts_are_not_changed_or_echoed():
    context = deepcopy(CONTEXTS['budget_reduced'])
    context['approval_status'] = 'pending'
    context['booking_callback'] = lambda: pytest.fail('No booking callback may run')
    event = DisruptionSimulator().simulate('budget_reduced', context)
    assert context['approval_status'] == 'pending'
    assert 'approval' not in json.dumps(event)
    assert 'booking_callback' not in event


@pytest.mark.parametrize('scenario', [None, True, 1, [], {}, '', 'FLIGHT_CANCELLED', 'weather_disruption'])
def test_invalid_scenario(scenario):
    with pytest.raises(DisruptionSimulationError) as error:
        DisruptionSimulator().simulate(scenario, {})
    assert error.value.code == 'unsupported_scenario'


@pytest.mark.parametrize('context', [None, [], 'trip', 1, {}])
def test_invalid_context(context):
    with pytest.raises(DisruptionSimulationError):
        DisruptionSimulator().simulate('flight_cancelled', context)


@pytest.mark.parametrize('scenario', CONTEXTS)
def test_missing_scenario_object(scenario):
    with pytest.raises(DisruptionSimulationError) as error:
        DisruptionSimulator().simulate(scenario, {'trip_id': 'demo'})
    assert error.value.code == 'invalid_context'


@pytest.mark.parametrize('value', [None, '', ' ', True, 12, 'x' * 201])
def test_invalid_trip_id(value):
    context = deepcopy(CONTEXTS['flight_cancelled'])
    context['trip_id'] = value
    with pytest.raises(DisruptionSimulationError):
        DisruptionSimulator().simulate('flight_cancelled', context)


@pytest.mark.parametrize('scenario,component,field', [
    ('flight_cancelled', 'flight', 'flight_id'), ('flight_cancelled', 'flight', 'departure_date'),
    ('hotel_unavailable', 'hotel', 'hotel_id'), ('hotel_unavailable', 'hotel', 'guests'),
    ('hotel_unavailable', 'hotel', 'rooms'), ('meeting_time_changed', 'meeting', 'meeting_id'),
    ('meeting_time_changed', 'meeting', 'original_start'), ('meeting_time_changed', 'meeting', 'new_start'),
    ('budget_reduced', 'budget', 'currency'), ('budget_reduced', 'budget', 'original_amount'),
    ('budget_reduced', 'budget', 'new_amount'),
])
def test_missing_facts_never_invented(scenario, component, field):
    context = deepcopy(CONTEXTS[scenario])
    del context[component][field]
    with pytest.raises(DisruptionSimulationError):
        DisruptionSimulator().simulate(scenario, context)


@pytest.mark.parametrize('field,value', [('origin', 'Hong Kong'), ('origin', 'hkg'), ('destination', 'HKG'),
    ('departure_date', '2026-02-30'), ('departure_date', '20261115'), ('departure_date', '2026-11-15T00:00:00')])
def test_invalid_flight(field, value):
    context = deepcopy(CONTEXTS['flight_cancelled'])
    context['flight'][field] = value
    with pytest.raises(DisruptionSimulationError):
        DisruptionSimulator().simulate('flight_cancelled', context)


@pytest.mark.parametrize('field,value', [('location', 'Unknown City'), ('location', 'Singapore, GB'),
    ('check_in', '2026-02-30'), ('check_out', '2026-11-15'), ('check_out', '2027-01-01'),
    ('guests', True), ('rooms', 0), ('guests', 5)])
def test_hotel_validation_delegated_to_existing_c2(field, value):
    context = deepcopy(CONTEXTS['hotel_unavailable'])
    context['hotel'][field] = value
    with pytest.raises(DisruptionSimulationError) as error:
        DisruptionSimulator().simulate('hotel_unavailable', context)
    assert error.value.code == 'invalid_hotel'


@pytest.mark.parametrize('value', ['2026-11-16T09:00:00', '2026-02-30T09:00:00+08:00',
    'tomorrow morning', '2026-11-16T01:00:00Z', '2026-11-16T09:00:00+08:00'])
def test_invalid_or_unchanged_meeting(value):
    context = deepcopy(CONTEXTS['meeting_time_changed'])
    context['meeting']['new_start'] = value
    with pytest.raises(DisruptionSimulationError) as error:
        DisruptionSimulator().simulate('meeting_time_changed', context)
    assert error.value.code == 'invalid_time'


def test_meeting_offset_change_preserves_explicit_instants():
    context = deepcopy(CONTEXTS['meeting_time_changed'])
    context['meeting'].update(original_start='2026-11-01T01:30:00-04:00', new_start='2026-11-01T01:30:00-05:00')
    event = DisruptionSimulator().simulate('meeting_time_changed', context)
    assert event['affected_trip']['meeting'] == context['meeting']


@pytest.mark.parametrize('field,value', [('currency', 'sgd'), ('currency', 'dollar'),
    ('original_amount', '0'), ('original_amount', 'NaN'), ('original_amount', '1e5'),
    ('original_amount', '1000000000000'), ('new_amount', '-1'), ('new_amount', 'Infinity'),
    ('new_amount', '2500.00'), ('new_amount', '2500.01'), ('new_amount', '1.999'),
    ('new_amount', 100.0), ('new_amount', True)])
def test_invalid_budget(field, value):
    context = deepcopy(CONTEXTS['budget_reduced'])
    context['budget'][field] = value
    with pytest.raises(DisruptionSimulationError):
        DisruptionSimulator().simulate('budget_reduced', context)


def test_zero_budget_and_decimal_context_are_supported():
    context = deepcopy(CONTEXTS['budget_reduced'])
    context['budget']['new_amount'] = '0'
    with localcontext(Context(prec=2)):
        event = DisruptionSimulator().simulate('budget_reduced', context)
    assert event['affected_trip']['budget']['new_amount'] == '0.00'
    assert event['affected_trip']['budget']['original_amount'] == '2500.00'


def test_existing_monitoring_contract_without_calling_agents():
    for scenario, context in CONTEXTS.items():
        event = DisruptionSimulator().simulate(scenario, context)
        assert event['severity'] in {'HIGH', 'MEDIUM', 'LOW'}
        assert event['type'].isupper() and isinstance(event['message'], str)


def test_all_scenarios_work_without_importing_agents_llms_or_live_providers():
    import subprocess
    import sys
    code = '''
import builtins, json, sys
original_import = builtins.__import__
forbidden = ("agents", "llm", "openai", "langchain", "requests", "tools.flight_search",
             "tools.weather_search", "tools.openmeteo_client")
def guarded_import(name, *args, **kwargs):
    if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden):
        raise AssertionError("C4 imported an agent, LLM or live provider dependency")
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
from tools.disruption_simulator import DisruptionSimulator
contexts = json.loads(sys.stdin.read())
print(json.dumps([DisruptionSimulator().simulate(scenario, context)
                  for scenario, context in contexts.items()], allow_nan=False))
'''
    result = subprocess.run([sys.executable, '-c', code], input=json.dumps(CONTEXTS),
                            text=True, capture_output=True, check=True, timeout=10)
    assert len(json.loads(result.stdout)) == 4
