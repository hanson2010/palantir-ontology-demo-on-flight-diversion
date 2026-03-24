"""Business logic services module.

This module contains business logic functions for processing
ontology data and executing actions.
"""

import json
import re

from .database import (
    set_flight_status,
    update_hotel_inventory,
    create_sub_flight,
    terminate_passengers
)


def get_passenger_summary(passengers: list) -> dict:
    """Generate a passenger summary for ground service reference.

    Args:
        passengers: List of passenger dictionaries.

    Returns:
        A summary dictionary containing counts and hotel needs.
    """
    gold_passengers = [p for p in passengers if p.get('loyalty', '').upper() == 'GOLD' and not p.get('terminated')]
    regular_passengers = [p for p in passengers if p.get('loyalty', '').upper() == 'REGULAR' and not p.get('terminated')]
    terminated_passengers = [p for p in passengers if p.get('terminated')]

    summary = {
        'total': len(passengers),
        'gold_count': len(gold_passengers),
        'regular_count': len(regular_passengers),
        'terminated_count': len(terminated_passengers),
        'gold_names': [p['id'] for p in gold_passengers],
        'regular_names': [p['id'] for p in regular_passengers],
        'terminated_names': [p['id'] for p in terminated_passengers],
        'hotel_needs': {
            '5_star': len(gold_passengers),
            '3_star': len(regular_passengers)
        }
    }
    return summary


def extract_json_from_response(response_text: str):
    """Extract JSON array from LLM response.

    Args:
        response_text: The raw text response from the LLM.

    Returns:
        Parsed JSON data.

    Raises:
        ValueError: If no valid JSON can be extracted.
    """
    # Try direct parsing
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown code block
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_text)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try extracting JSON array surrounded by brackets
    array_match = re.search(r'\[[\s\S]*\]', response_text)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 LLM 响应中提取有效的 JSON:\n{response_text[:500]}...")


def execute_action(action_json: str) -> list:
    """Execute actions based on LLM-generated JSON instructions.

    This function synchronizes Neo4j state based on the action types
    (AIP Action Execution).

    Args:
        action_json: JSON string containing action definitions.

    Returns:
        List of executed actions.
    """
    actions = extract_json_from_response(action_json)

    for action in actions:
        if action['type'] == 'SetFlightStatus':
            set_flight_status(
                iata=action['params']['iata'],
                status=action['params']['status']
            )
        elif action['type'] == 'UpdateHotelInventory':
            update_hotel_inventory(hotel_name=action['params']['name'])
        elif action['type'] == 'CreateSubFlight':
            params = action['params']
            create_sub_flight(
                main_flight=params['mainFlight'],
                sub_flight_iata=params['subFlightIata'],
                scheduled_time=params['scheduledTime']
            )
        elif action['type'] == 'TerminatePassengerJourney':
            terminate_passengers([action['params']['passengerId']])

    return actions


def execute_terminate_passengers(passenger_ids: list) -> list:
    """Execute passenger journey termination.

    Args:
        passenger_ids: List of passenger IDs to terminate.

    Returns:
        List of termination actions executed.
    """
    terminate_passengers(passenger_ids)
    return [
        {
            'type': 'TerminatePassengerJourney',
            'params': {'passengerId': passenger_id}
        }
        for passenger_id in passenger_ids
    ]
