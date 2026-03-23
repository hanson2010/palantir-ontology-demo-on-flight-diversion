// 1. 创建对象 (Objects)
// 1.1 创建航班和原机场
CREATE (f:Flight {iata: 'CA123', status: 'EN_ROUTE'})
CREATE (a1:Airport {iata: 'CAN', name: 'Guangzhou Baiyun International Airport'})
CREATE (f)-[:DESTINED_FOR]->(a1)

// 1.2 创建备降机场和协议酒店
CREATE (a2:Airport {iata: 'SZX', name: 'Shenzhen Bao\'an International Airport', hasGroundService: true})
CREATE (h1:Hotel {name: 'Hyatt Airport', star: 5, totalRooms: 50, availableRooms: 5})
CREATE (h2:Hotel {name: 'Comfort Inn', star: 3, totalRooms: 100, availableRooms: 60})
CREATE (a2)-[:HAS_PROTOCOL_HOTEL]->(h1)
CREATE (a2)-[:HAS_PROTOCOL_HOTEL]->(h2)

// 1.3 创建旅客及其Link
CREATE (p1:Passenger {name: 'Alice VIP', id: 'P001', loyalty: 'GOLD'})
CREATE (p2:Passenger {name: 'Bob Conventional', id: 'P002', loyalty: 'REGULAR'})
CREATE (p1)-[:ON_BOARD]->(f)
CREATE (p2)-[:ON_BOARD]->(f)
