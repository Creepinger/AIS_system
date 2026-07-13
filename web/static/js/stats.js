// 状态面板 + 侧边船舶列表 + 解码器对比。
// 通过 WSClient.on 与 on_ship_list 渲染,完全独立于 Qt 版本。
(function (global) {
    "use strict";

    var statRx, statBcc, statDec, statCount, statTypes, statSource;
    var body;
    var shipRows = {};
    var decoderSelect;
    var comparePanel;
    var compareList;
    var currentMode = "custom";

    // 对比结果缓存（用于追加显示）
    var comparisonCache = [];
    var maxComparisonItems = 50;

    function init() {
        statRx = document.getElementById("stat-rx");
        statBcc = document.getElementById("stat-bcc");
        statDec = document.getElementById("stat-dec");
        statCount = document.getElementById("stat-count");
        statTypes = document.getElementById("stat-types");
        statSource = document.getElementById("stat-source");
        body = document.getElementById("ship-list-body");
        decoderSelect = document.getElementById("decoder-select");
        comparePanel = document.getElementById("compare-panel");
        compareList = document.getElementById("compare-list");

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
            // 清空对比缓存
            comparisonCache = [];
            if (compareList) compareList.innerHTML = "";
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

        // 解码器切换
        if (decoderSelect) {
            decoderSelect.onchange = function () {
                var mode = decoderSelect.value;
                currentMode = mode;
                WSClient.send({ cmd: "set_decoder", mode: mode });

                // 显示/隐藏对比面板
                if (comparePanel) {
                    comparePanel.style.display = mode === "compare" ? "block" : "none";
                }

                // 切换模式时清空缓存
                if (mode !== "compare") {
                    comparisonCache = [];
                    if (compareList) compareList.innerHTML = "";
                }
            };
        }
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

        // 更新解码器模式
        if (msg.decoder_mode) {
            currentMode = msg.decoder_mode;
            if (decoderSelect) {
                decoderSelect.value = msg.decoder_mode;
            }
            if (comparePanel) {
                comparePanel.style.display = msg.decoder_mode === "compare" ? "block" : "none";
            }
        }

        // 更新对比结果（追加模式）
        if (msg.comparison && msg.comparison.length > 0) {
            // 将新的对比结果添加到缓存
            msg.comparison.forEach(function(r) {
                // 检查是否已存在（根据 mmsi 和 msg_type 简单去重）
                var key = r.mmsi + "_" + r.msg_type;
                var exists = comparisonCache.some(function(item) {
                    return (item.mmsi + "_" + item.msg_type) === key;
                });
                if (!exists) {
                    comparisonCache.push(r);
                }
            });

            // 限制缓存大小
            if (comparisonCache.length > maxComparisonItems) {
                comparisonCache = comparisonCache.slice(-maxComparisonItems);
            }

            // 渲染对比结果
            renderComparison();
        }
    }

    function renderComparison() {
        if (!compareList) return;

        // 清空并重新渲染
        compareList.innerHTML = "";

        comparisonCache.forEach(function (r) {
            var item = createCompareItem(r);
            compareList.appendChild(item);
        });

        // 滚动到底部
        compareList.scrollTop = compareList.scrollHeight;
    }

    function createCompareItem(r) {
        var item = document.createElement("div");
        item.className = "compare-item";

        var msgType = r.msg_type || "-";
        var mmsi = r.mmsi || "-";

        // 创建头部
        var head = document.createElement("div");
        head.className = "compare-head";
        head.innerHTML = "<span class='msg-type'>类型" + msgType + "</span>"
            + "<span class='mmsi'>" + mmsi + "</span>";

        item.appendChild(head);

        // 如果有误差数据，创建数据行
        if (r.errors) {
            var err = r.errors;
            var dataDiv = document.createElement("div");
            dataDiv.className = "compare-data";

            // 纬度行
            dataDiv.appendChild(createDataRow("纬度",
                r.custom ? r.custom.latitude : null,
                r.pyais ? r.pyais.lat : null,
                err.lat, 0.0001));

            // 经度行
            dataDiv.appendChild(createDataRow("经度",
                r.custom ? r.custom.longitude : null,
                r.pyais ? r.pyais.lon : null,
                err.lon, 0.0001));

            // 航速行
            dataDiv.appendChild(createDataRow("航速",
                r.custom ? r.custom.sog : null,
                r.pyais ? r.pyais.speed : null,
                err.sog, 0.5));

            // 航向行
            dataDiv.appendChild(createDataRow("航向",
                r.custom ? r.custom.cog : null,
                r.pyais ? r.pyais.course : null,
                err.cog, 0.5, true));

            item.appendChild(dataDiv);
        } else {
            // 无误差数据时，显示原始值
            var infoDiv = document.createElement("div");
            infoDiv.className = "compare-info";
            var hasCustom = r.custom && r.custom.mmsi;
            var hasPyais = r.pyais && r.pyais.mmsi;
            infoDiv.innerHTML = "<span class='info-text'>"
                + (hasCustom ? "自研" : "")
                + (hasCustom && hasPyais ? " vs " : "")
                + (hasPyais ? "pyais" : "")
                + "</span>";
            item.appendChild(infoDiv);
        }

        return item;
    }

    function createDataRow(label, customVal, pyaisVal, error, threshold, isInteger) {
        var row = document.createElement("div");
        row.className = "data-row";

        var labelSpan = document.createElement("span");
        labelSpan.className = "label";
        labelSpan.textContent = label;

        var customSpan = document.createElement("span");
        customSpan.className = "custom";
        customSpan.textContent = customVal !== null ? (isInteger ? customVal : customVal.toFixed(5)) : "-";

        var pyaisSpan = document.createElement("span");
        pyaisSpan.className = "pyais";
        pyaisSpan.textContent = pyaisVal !== null ? (isInteger ? Math.round(pyaisVal) : pyaisVal.toFixed(5)) : "-";

        var errorSpan = document.createElement("span");
        errorSpan.className = "error " + (error < threshold ? "ok" : "warn");
        errorSpan.textContent = error.toFixed(6);

        row.appendChild(labelSpan);
        row.appendChild(customSpan);
        row.appendChild(pyaisSpan);
        row.appendChild(errorSpan);

        return row;
    }

    function renderShips(ships) {
        shipRows = {};
        if (!body) return;
        body.innerHTML = "";
        (ships || []).forEach(function (s) {
            addRow(s);
        });
    }

    // 按 msg_type 返回徽章颜色类 (msg1=红, msg5=绿, msg18=黄, 其他=蓝)
    function _badgeClass(msgType) {
        if (msgType === 1) return "msg1";
        if (msgType === 5) return "msg5";
        if (msgType === 18) return "msg18";
        return "msgoth";
    }

    function addRow(s) {
        if (!body) return;
        var row = document.createElement("div");
        row.className = "ship-row";
        row.dataset.mmsi = s.mmsi;
        // MMSI 单元格内增加 msg_type 颜色徽章 (仅渲染增强, 数据逻辑不变)
        var badgeCls = _badgeClass(s.msg_type);
        row.innerHTML =
            "<span class='mmsi-cell'>" +
                "<span class='type-badge " + badgeCls + "'>" + s.msg_type + "</span>" +
                s.mmsi +
            "</span>" +
            "<span>" + s.latitude.toFixed(4) + "</span>" +
            "<span>" + s.longitude.toFixed(4) + "</span>" +
            "<span>" + s.sog.toFixed(1) + "</span>" +
            "<span>" + s.cog + "</span>" +
            "<span>" + (s.shipname || "-") + "</span>";
        row.onclick = function () {
            // 行高亮: 移除其他行的 active, 标记当前行 (仅渲染增强)
            var prevActive = body.querySelector(".ship-row.active");
            if (prevActive) prevActive.classList.remove("active");
            row.classList.add("active");
            if (global.MapMod && global.MapMod.applyShips) {
                global.MapMod.applyShips([s]);
            }
        };
        body.appendChild(row);
        shipRows[s.mmsi] = row;
    }

    global.StatsMod = {
        init: init,
        update: update,
        renderShips: renderShips,
        addRow: addRow,
        renderComparison: renderComparison,
        clearComparison: function() {
            comparisonCache = [];
            if (compareList) compareList.innerHTML = "";
        }
    };
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
