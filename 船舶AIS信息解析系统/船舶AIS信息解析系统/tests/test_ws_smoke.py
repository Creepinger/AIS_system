"""端到端测试:连接 WS,等 3 秒,统计收到的消息与船舶。"""
import asyncio
import json
import time

import websockets  # uvicorn[standard] 已带


async def main():
    url = "ws://127.0.0.1:8000/ws"
    async with websockets.connect(url) as ws:
        messages = []
        ships_seen = set()
        stats_rx = 0
        stats_decoded = 0
        try:
            for _ in range(20):
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(msg)
                messages.append(data)
                if data.get("type") == "batch":
                    for s in (data.get("ships") or []):
                        ships_seen.add(s["mmsi"])
                    st = data.get("stats", {})
                    stats_rx = max(stats_rx, st.get("rx", 0))
                    stats_decoded = max(stats_decoded, st.get("decoded", 0))
        except asyncio.TimeoutError:
            pass

        print(f"收到 {len(messages)} 条 WS 消息")
        print(f"不同船舶 MMSI: {len(ships_seen)} {sorted(ships_seen)}")
        print(f"stats.rx 最大值: {stats_rx}")
        print(f"stats.decoded 最大值: {stats_decoded}")
        if messages:
            print(f"\n首条消息 keys: {sorted(messages[0].keys())}")
            print(f"首条 ships 数量: {len(messages[0].get('ships', []))}")
            if messages[0].get('ships'):
                s = messages[0]['ships'][0]
                print(f"示例船舶字段: {sorted(s.keys())}")

        # 发命令:pause / resume / clear
        await ws.send(json.dumps({"cmd": "pause"}))
        await asyncio.sleep(0.5)
        await ws.send(json.dumps({"cmd": "resume"}))
        await ws.send(json.dumps({"cmd": "clear"}))
        print("\n命令 pause/resume/clear 已发送")


if __name__ == "__main__":
    asyncio.run(main())
