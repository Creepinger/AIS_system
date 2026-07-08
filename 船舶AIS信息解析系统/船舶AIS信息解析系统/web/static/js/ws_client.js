// WebSocket 客户端。
// 零依赖纯 JS,通过 ES5 全局命名空间与其它脚本通信。
(function (global) {
    "use strict";

    var listeners = [];
    var ws = null;
    var stateEl = null;
    var backoff = 1000;
    var maxBackoff = 10000;

    function setState(connected) {
        if (!stateEl) stateEl = document.getElementById("ws-state");
        if (!stateEl) return;
        if (connected) {
            stateEl.textContent = "已连接";
            stateEl.className = "ws-state on";
        } else {
            stateEl.textContent = "断开";
            stateEl.className = "ws-state off";
        }
    }

    function connect() {
        var proto = location.protocol === "https:" ? "wss" : "ws";
        var url = proto + "://" + location.host + "/ws";
        ws = new WebSocket(url);

        ws.onopen = function () {
            backoff = 1000;
            setState(true);
        };

        ws.onclose = function () {
            setState(false);
            setTimeout(connect, backoff);
            backoff = Math.min(backoff * 2, maxBackoff);
        };

        ws.onerror = function () {
            try { ws.close(); } catch (e) {}
        };

        ws.onmessage = function (evt) {
            try {
                var payload = JSON.parse(evt.data);
                listeners.forEach(function (cb) { cb(payload); });
            } catch (e) {
                console.warn("WS bad frame", e);
            }
        };
    }

    function on(cb) {
        listeners.push(cb);
    }

    function send(obj) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(obj));
        } else {
            console.warn("WS not open; drop command", obj);
        }
    }

    global.WSClient = { connect: connect, on: on, send: send, setState: setState };

    // 自动启动
    document.addEventListener("DOMContentLoaded", connect);
}(window));
