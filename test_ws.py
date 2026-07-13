import websocket
import json

ws = websocket.create_connection('ws://127.0.0.1:8080/ws')
for i in range(5):
    data = ws.recv()
    msg = json.loads(data)
    print(f"=== Frame {i+1} ===")
    print(f"Type: {msg['type']}")
    ships = msg.get('ships', [])
    print(f"Ships count: {len(ships)}")
    if ships:
        for ship in ships[:3]:
            mmsi = ship.get('mmsi')
            msg_type = ship.get('msg_type')
            lat = ship.get('latitude')
            lon = ship.get('longitude')
            print(f"  MMSI:{mmsi} Type:{msg_type} Lat:{lat:.4f} Lon:{lon:.4f}")
    stats = msg.get('stats', {})
    print(f"Stats: rx={stats.get('rx',0)} decoded={stats.get('decoded',0)}")
    print()
ws.close()
