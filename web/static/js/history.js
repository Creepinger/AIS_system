// 历史数据 CRUD 模块
(function () {
    "use strict";

    var backdrop;
    var currentShips = [];

    function $(id) { return document.getElementById(id); }

    // ── 模态框 ──────────────────────────────────────────────
    function showModal() {
        backdrop.hidden = false;
        doQuery();
    }

    function hideModal() {
        backdrop.hidden = true;
    }

    // ── 工具 ────────────────────────────────────────────────
    function esc(v) {
        if (v == null) return "";
        var d = document.createElement("div");
        d.textContent = String(v);
        return d.innerHTML;
    }

    function fmtLatLon(v) {
        if (v == null) return "-";
        return parseFloat(v).toFixed(5);
    }

    function fmtSpeed(v) {
        if (v == null) return "-";
        return parseFloat(v).toFixed(1);
    }

    // ── 表格渲染 ────────────────────────────────────────────
    function clearTable() {
        $("history-tbody").innerHTML = "";
        currentShips = [];
    }

    function renderTable(ships) {
        var tbody = $("history-tbody");
        tbody.innerHTML = "";
        currentShips = ships;
        ships.forEach(function (s) {
            appendRow(tbody, s);
        });
    }

    function appendRow(tbody, s) {
        var tr = document.createElement("tr");
        tr.dataset.id = s.id;

        // 最后一列为操作按钮
        var opHtml =
            "<button class=\"tbl-btn edit-btn\" title=\"编辑\" onclick=\"History.edit(" + s.id + ")\">&#9998;</button>" +
            "<button class=\"tbl-btn del-btn\"  title=\"删除\" onclick=\"History.del(" + s.id + ")\">&#10005;</button>";

        tr.innerHTML =
            "<td>" + esc(s.ts || "-") + "</td>" +
            "<td>" + esc(s.mmsi || "-") + "</td>" +
            "<td>" + fmtLatLon(s.latitude) + "</td>" +
            "<td>" + fmtLatLon(s.longitude) + "</td>" +
            "<td>" + fmtSpeed(s.sog) + "</td>" +
            "<td>" + (s.cog == null ? "-" : s.cog) + "</td>" +
            "<td>" + esc(s.shipname || "-") + "</td>" +
            "<td class=\"ops-cell\">" + opHtml + "</td>";

        tbody.appendChild(tr);
    }

    // ── 行内编辑 ────────────────────────────────────────────
    window.History = {
        edit: function (id) {
            var ship = currentShips.find(function (s) { return s.id === id; });
            if (!ship) return;

            var tbody = $("history-tbody");
            var rows = tbody.querySelectorAll("tr");
            rows.forEach(function (tr) {
                if (parseInt(tr.dataset.id) !== id) return;
                var tds = tr.querySelectorAll("td");

                // 第 1 列: ts 只读
                // 第 2 列: MMSI 可编辑
                tds[1].innerHTML = "<input type=\"number\" class=\"edit-inp\" data-field=\"mmsi\" value=\"" + esc(ship.mmsi || "") + "\" />";
                // 第 3 列: latitude
                tds[2].innerHTML = "<input type=\"number\" class=\"edit-inp\" data-field=\"latitude\" value=\"" + esc(ship.latitude || "") + "\" step=\"0.00001\" />";
                // 第 4 列: longitude
                tds[3].innerHTML = "<input type=\"number\" class=\"edit-inp\" data-field=\"longitude\" value=\"" + esc(ship.longitude || "") + "\" step=\"0.00001\" />";
                // 第 5 列: sog
                tds[4].innerHTML = "<input type=\"number\" class=\"edit-inp\" data-field=\"sog\" value=\"" + esc(ship.sog || "") + "\" step=\"0.1\" />";
                // 第 6 列: cog
                tds[5].innerHTML = "<input type=\"number\" class=\"edit-inp\" data-field=\"cog\" value=\"" + esc(ship.cog || "") + "\" min=\"0\" max=\"359\" />";
                // 第 7 列: shipname
                tds[6].innerHTML = "<input type=\"text\" class=\"edit-inp\" data-field=\"shipname\" value=\"" + esc(ship.shipname || "") + "\" />";
                // 第 8 列: 操作
                tds[7].innerHTML =
                    "<button class=\"tbl-btn save-btn\" onclick=\"History.save(" + id + ")\">&#10003;</button>" +
                    "<button class=\"tbl-btn cancel-btn\" onclick=\"History.cancel(" + id + ")\">&#10005;</button>";
            });
        },

        save: function (id) {
            var tr = $("history-tbody").querySelector("tr[data-id=\"" + id + "\"]");
            if (!tr) return;
            var fields = {};
            tr.querySelectorAll(".edit-inp").forEach(function (inp) {
                var key = inp.dataset.field;
                var val = inp.value;
                if (key === "mmsi") val = parseInt(val) || 0;
                else if (key === "latitude" || key === "longitude" || key === "sog") val = parseFloat(val) || 0;
                else if (key === "cog") val = parseInt(val) || 0;
                else val = String(val);
                fields[key] = val;
            });

            fetch("/api/ships/" + id, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(fields),
            })
            .then(function (r) {
                if (r.status === 404) {
                    alert("记录不存在，可能已被删除");
                    return null;
                }
                return r.json();
            })
            .then(function (data) {
                if (!data) return;
                // 更新 currentShips 中的数据
                var idx = currentShips.findIndex(function (s) { return s.id === id; });
                if (idx >= 0) {
                    Object.assign(currentShips[idx], fields);
                }
                doQuery(); // 重新渲染
                showToast("保存成功");
            })
            .catch(function (e) { console.error(e); alert("保存失败: " + e); });
        },

        cancel: function (id) {
            doQuery(); // 重新渲染原数据
        },

        del: function (id) {
            if (!confirm("确定要删除这条记录吗？")) return;
            fetch("/api/ships/" + id, { method: "DELETE" })
            .then(function (r) {
                if (r.status === 404) {
                    alert("记录不存在，可能已被删除");
                    return null;
                }
                return r.json();
            })
            .then(function (data) {
                if (!data) return;
                currentShips = currentShips.filter(function (s) { return s.id !== id; });
                var tr = $("history-tbody").querySelector("tr[data-id=\"" + id + "\"]");
                if (tr) tr.remove();
                var total = parseInt($("history-count-num").textContent) || 0;
                $("history-count-num").textContent = Math.max(0, total - 1);
                showToast("已删除");
            })
            .catch(function (e) { console.error(e); });
        },

        delAll: function () {
            if (!confirm("确定要清空所有记录吗？此操作不可恢复！")) return;
            fetch("/api/ships", { method: "DELETE" })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                clearTable();
                $("history-count-num").textContent = "0";
                showToast("已清空 " + data.deleted + " 条记录");
            })
            .catch(function (e) { console.error(e); });
        },

        create: function () {
            var mmsi = prompt("请输入 MMSI（9位数字）:");
            if (!mmsi) return;
            mmsi = parseInt(mmsi);
            if (!mmsi || mmsi < 100000000 || mmsi > 999999999) {
                alert("MMSI 必须为 9 位数字");
                return;
            }
            fetch("/api/ships", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mmsi: mmsi }),
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.ok) { alert("创建失败"); return; }
                doQuery();
                showToast("创建成功，ID=" + data.id);
            })
            .catch(function (e) { console.error(e); });
        },
    };

    // ── API 调用 ────────────────────────────────────────────
    function doQuery() {
        var mmsi     = $("history-mmsi").value.trim();
        var lat      = $("history-lat").value.trim();
        var lon      = $("history-lon").value.trim();
        var sog      = $("history-sog").value.trim();
        var cog      = $("history-cog").value.trim();
        var shipname = $("history-shipname").value.trim();
        var limit    = parseInt($("history-limit").value) || 500;

        var params = [];
        if (mmsi)     params.push("mmsi=" + encodeURIComponent(mmsi));
        if (lat)      params.push("latitude=" + encodeURIComponent(lat));
        if (lon)      params.push("longitude=" + encodeURIComponent(lon));
        if (sog)      params.push("sog=" + encodeURIComponent(sog));
        if (cog)      params.push("cog=" + encodeURIComponent(cog));
        if (shipname) params.push("shipname=" + encodeURIComponent(shipname));
        params.push("limit=" + limit);

        fetch("/api/ships/query?" + params.join("&"))
            .then(function (r) {
                console.log("[History] query status:", r.status, r.statusText);
                if (!r.ok) {
                    alert("查询失败: HTTP " + r.status);
                    return null;
                }
                return r.json();
            })
            .then(function (data) {
                if (!data) return;
                console.log("[History] got", data.count, "rows");
                var cnt = $("history-count-num");
                if (cnt) cnt.textContent = data.count;
                renderTable(data.ships || []);
            })
            .catch(function (e) { console.error(e); alert("查询出错: " + e); });
    }

    function showToast(msg) {
        var el = $("history-toast");
        if (!el) return;
        el.textContent = msg;
        el.classList.add("show");
        clearTimeout(el._timer);
        el._timer = setTimeout(function () { el.classList.remove("show"); }, 2000);
    }

    // ── 初始化 ──────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", function () {
        backdrop = $("history-modal-backdrop");

        if ($("btn-history")) {
            $("btn-history").addEventListener("click", showModal);
        } else {
            document.addEventListener("click", function (e) {
                if (e.target && e.target.id === "btn-history") showModal();
            });
        }
        $("history-modal-close").addEventListener("click", hideModal);
        backdrop.addEventListener("click", function (e) {
            if (e.target === backdrop) hideModal();
        });
        $("btn-history-query").addEventListener("click", doQuery);
        $("btn-history-new").addEventListener("click", function () { window.History.create(); });
        $("btn-history-del-all").addEventListener("click", function () { window.History.delAll(); });

        // 回车触发查询
        ["history-mmsi", "history-lat", "history-lon", "history-sog",
         "history-cog", "history-shipname", "history-limit"].forEach(function (id) {
            $(id).addEventListener("keydown", function (e) {
                if (e.key === "Enter") doQuery();
            });
        });

        // 仅在 WSClient 可用时（主页面）订阅实时状态
        if (window.WSClient) {
            WSClient.on(function (payload) {
                if (payload && payload.stats) {
                    $("history-info").innerHTML =
                        "当前内存船舶数 <b>" + (payload.stats.ship_count || 0) + "</b>，数据库已启用";
                }
            });
        }
    });
}());
