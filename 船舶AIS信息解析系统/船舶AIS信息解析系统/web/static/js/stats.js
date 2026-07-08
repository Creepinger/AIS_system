// 状态面板 + 侧边船舶列表。
// 通过 WSClient.on 与 on_ship_list 渲染,完全独立于 Qt 版本。
(function (global) {
    "use strict";

    var statRx, statBcc, statDec, statCount, statTypes, statSource;
    var body;
    var shipRows = {};

    function init() {
        statRx = document.getElementById("stat-rx");
        statBcc = document.getElementById("stat-bcc");
        statDec = document.getElementById("stat-dec");
        statCount = document.getElementById("stat-count");
        statTypes = document.getElementById("stat-types");
        statSource = document.getElementById("stat-source");
        body = document.getElementById("ship-list-body");

        document.getElementById("btn-apply").onclick = applySource;
        document.getElementById("btn-pause").onclick = function () {
            WSClient.send({ cmd: "pause" });
        };
        document.getElementById("btn-resume").onclick = function () {
            WSClient.send({ cmd: "resume" });
        };
        document.getElementById("btn-clear").onclick = function () {
            WSClient.send({ cmd: "clear" });
            shipRows = {};
            body.innerHTML = "";
            // 清空地图上的船舶标记,并重置自动 fit
            if (global.MapMod && global.MapMod.clearAll) {
                global.MapMod.clearAll();
            }
        };
        document.getElementById("btn-upload").onclick = function () {
            document.getElementById("upload-file").click();
        };
        document.getElementById("upload-file").onchange = function (e) {
            var f = e.target.files[0];
            if (!f) return;
            var fd = new FormData();
            fd.append("kind", "file");
            fd.append("upload", f);
            fetch("/api/load", { method: "POST", body: fd })
                .then(function (r) { return r.json(); })
                .then(function (j) {
                    document.getElementById("source-path").value = f.name;
                    console.log("uploaded", j);
                })
                .catch(function (err) { alert("上传失败: " + err); });
        };
    }

    function applySource() {
        var kind = document.getElementById("source-kind").value;
        var path = document.getElementById("source-path").value.trim();
        if (!path) { alert("请输入路径 / 端口 / host:port"); return; }
        WSClient.send({ cmd: "set_source", kind: kind, path: path });
    }

    function update(msg) {
        if (!msg.stats) return;
        if (statRx) statRx.textContent = msg.stats.rx || 0;
        if (statBcc) statBcc.textContent = (msg.stats.bcc_pass || 0)
            + "/" + (msg.stats.bcc_fail || 0);
        if (statDec) statDec.textContent = msg.stats.decoded || 0;
        if (statCount) statCount.textContent = msg.stats.ship_count || 0;
        if (statTypes) {
            var t = msg.stats.by_type || {};
            statTypes.textContent = Object.keys(t).length === 0
                ? "-" : Object.keys(t).map(function (k) { return k + ":" + t[k]; }).join(" ");
        }
        if (statSource) statSource.textContent = msg.source || "-";
    }

    function renderShips(ships) {
        // 用最近一次窗口的船只列表全量替换
        shipRows = {};
        if (!body) return;
        body.innerHTML = "";
        (ships || []).forEach(function (s) {
            addRow(s);
        });
    }

    function addRow(s) {
        if (!body) return;
        var row = document.createElement("div");
        row.className = "ship-row";
        row.dataset.mmsi = s.mmsi;
        row.innerHTML =
            "<span>" + s.mmsi + "</span>" +
            "<span>" + s.latitude.toFixed(4) + "</span>" +
            "<span>" + s.longitude.toFixed(4) + "</span>" +
            "<span>" + s.sog.toFixed(1) + "</span>" +
            "<span>" + s.cog + "</span>" +
            "<span>" + (s.shipname || "-") + "</span>";
        row.onclick = function () {
            // 简易 click 行为:聚焦地图到该船舶
            if (global.MapMod && global.MapMod.applyShips) {
                global.MapMod.applyShips([s]);
            }
        };
        body.appendChild(row);
        shipRows[s.mmsi] = row;
    }

    global.StatsMod = { init: init, update: update, renderShips: renderShips, addRow: addRow };
}(window));

document.addEventListener("DOMContentLoaded", function () {
    StatsMod.init();
    WSClient.on(function (msg) {
        if (msg.type === "batch") {
            StatsMod.update(msg);
            StatsMod.renderShips(msg.ships || []);
        }
    });
});
