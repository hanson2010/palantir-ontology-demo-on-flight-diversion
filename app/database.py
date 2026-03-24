"""Database operations module.

This module contains all Neo4j database operations for retrieving
and updating ontology data.
"""

from .config import neo4j_driver


def get_ontology_data(flight_iata: str, alternate_iata: str) -> dict:
    """Retrieve relevant ontology data from Neo4j AuraDB.

    Args:
        flight_iata: The IATA code of the flight.
        alternate_iata: The IATA code of the alternate airport.

    Returns:
        A dictionary containing flight, passengers, alternate airport,
        hotels, and sub-flight data.

    Raises:
        ValueError: If flight or alternate airport data is not found.
    """
    query = '''
    MATCH (f:Flight {iata: $flight})
    OPTIONAL MATCH (p:Passenger)-[:ON_BOARD]->(f)
    MATCH (a:Airport {iata: $alternate})-[:HAS_PROTOCOL_HOTEL]->(h:Hotel)
    OPTIONAL MATCH (f)-[:HAS_SUB_FLIGHT]->(sf:SubFlight)
    RETURN
        {iata: f.iata, status: f.status} as flight,
        collect(DISTINCT CASE WHEN p IS NOT NULL THEN {id: p.id, name: p.name, loyalty: p.loyalty, terminated: COALESCE(p.terminated, false)} ELSE NULL END) as passengers,
        {iata: a.iata, name: a.name} as alternateAirport,
        collect(DISTINCT {name: h.name, star: h.star, availableRooms: h.availableRooms}) as hotels,
        sf as subFlight
    '''
    with neo4j_driver.session() as session:
        result = session.run(query, flight=flight_iata, alternate=alternate_iata)
        record = result.single()
        if record is None:
            raise ValueError(f"未找到航班 {flight_iata} 或备降机场 {alternate_iata} 的数据")
        # Filter out null passengers
        passengers = [p for p in record['passengers'] if p is not None]
        return {
            'flight': record['flight'],
            'passengers': passengers,
            'alternateAirport': record['alternateAirport'],
            'hotels': record['hotels'],
            'subFlight': record['subFlight']
        }


def set_flight_status(iata: str, status: str) -> None:
    """Update flight status in the database.

    Args:
        iata: The IATA code of the flight.
        status: The new status to set.
    """
    with neo4j_driver.session() as session:
        session.run(
            'MATCH (f:Flight {iata: $iata}) SET f.status = $status',
            iata=iata, status=status
        )


def update_hotel_inventory(hotel_name: str) -> None:
    """Decrease available rooms count for a hotel.

    Args:
        hotel_name: The name of the hotel to update.
    """
    with neo4j_driver.session() as session:
        session.run(
            'MATCH (h:Hotel {name: $name}) SET h.availableRooms = h.availableRooms - 1',
            name=hotel_name
        )


def create_sub_flight(main_flight: str, sub_flight_iata: str, scheduled_time: str) -> None:
    """Create a sub-flight (recovery flight) in the database.

    Args:
        main_flight: The IATA code of the main flight.
        sub_flight_iata: The IATA code for the new sub-flight.
        scheduled_time: The scheduled time for the sub-flight.
    """
    with neo4j_driver.session() as session:
        session.run('''
            MATCH (f:Flight {iata: $mainFlight})
            CREATE (sf:SubFlight {
                iata: $subFlightIata,
                scheduledTime: $scheduledTime,
                status: 'Planned'
            })
            CREATE (f)-[:HAS_SUB_FLIGHT]->(sf)
            WITH sf
            MATCH (f:Flight {iata: $mainFlight})-[:ON_BOARD]->(p:Passenger)
            WHERE NOT p.terminated = true
            CREATE (sf)-[:CARRIES]->(p)
        ''', mainFlight=main_flight, subFlightIata=sub_flight_iata, scheduledTime=scheduled_time)


def terminate_passenger(passenger_id: str) -> None:
    """Mark a passenger's journey as terminated.

    Args:
        passenger_id: The ID of the passenger to terminate.
    """
    with neo4j_driver.session() as session:
        session.run('''
            MATCH (p:Passenger {id: $passengerId})
            SET p.terminated = true
        ''', passengerId=passenger_id)


def terminate_passengers(passenger_ids: list) -> None:
    """Mark multiple passengers' journeys as terminated.

    Args:
        passenger_ids: List of passenger IDs to terminate.
    """
    with neo4j_driver.session() as session:
        for passenger_id in passenger_ids:
            session.run('''
                MATCH (p:Passenger {id: $passengerId})
                SET p.terminated = true
            ''', passengerId=passenger_id)


def get_flight_status(flight_iata: str) -> dict:
    """Retrieve flight status from Neo4j.

    Args:
        flight_iata: The IATA code of the flight.

    Returns:
        A dictionary containing flight status information.
    """
    query = '''
    MATCH (f:Flight {iata: $flight})
    RETURN {iata: f.iata, status: f.status} as flight
    '''
    with neo4j_driver.session() as session:
        result = session.run(query, flight=flight_iata)
        record = result.single()
        if record is None:
            return {'iata': flight_iata, 'status': 'Unknown'}
        return record['flight']


def get_system_status() -> dict:
    """Retrieve system status for AIP dashboard.

    Returns:
        A dictionary containing system status information.
    """
    query = '''
    MATCH (f:Flight)
    OPTIONAL MATCH (p:Passenger)
    OPTIONAL MATCH (h:Hotel)
    OPTIONAL MATCH (sf:SubFlight)
    RETURN {
        flights: count(DISTINCT f),
        passengers: count(DISTINCT p),
        hotels: count(DISTINCT h),
        subFlights: count(DISTINCT sf)
    } as status
    '''
    with neo4j_driver.session() as session:
        result = session.run(query)
        record = result.single()
        return record['status'] if record else {}


def reset_database() -> None:
    """Reset the database to initial state.

    This function:
    1. Deletes all existing data
    2. Recreates the initial objects from the original setup
    """
    with neo4j_driver.session() as session:
        # Delete all existing data
        session.run('MATCH (n) DETACH DELETE n')

        # Recreate initial objects
        session.run('''
            // 1.1 创建航班和原机场
            CREATE (f:Flight {iata: 'CA123', status: 'EN_ROUTE'})
            CREATE (a1:Airport {iata: 'CAN', name: 'Guangzhou Baiyun International Airport'})
            CREATE (f)-[:DESTINED_FOR]->(a1)

            // 1.2 创建备降机场和协议酒店
            CREATE (a2:Airport {iata: 'SZX', name: "Shenzhen Bao'an International Airport", hasGroundService: true})
            CREATE (h1:Hotel {name: 'Hyatt Airport', star: 5, totalRooms: 50, availableRooms: 5})
            CREATE (h2:Hotel {name: 'Comfort Inn', star: 3, totalRooms: 100, availableRooms: 60})
            CREATE (a2)-[:HAS_PROTOCOL_HOTEL]->(h1)
            CREATE (a2)-[:HAS_PROTOCOL_HOTEL]->(h2)

            // 1.3 创建旅客及其Link
            CREATE (p1:Passenger {name: 'Alice VIP', id: 'P001', loyalty: 'GOLD'})
            CREATE (p2:Passenger {name: 'Bob Conventional', id: 'P002', loyalty: 'REGULAR'})
            CREATE (p1)-[:ON_BOARD]->(f)
            CREATE (p2)-[:ON_BOARD]->(f)
        ''')
