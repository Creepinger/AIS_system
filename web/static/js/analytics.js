// AIS 规律分析页面逻辑
(function () {
    "use strict";

    var charts = {}; // chart 实例缓存，便于销毁

    // AIS 消息类型权威名称（来自 ITU-R M.1371）
    var MSG_TYPE_LABEL = {
        1: "A 位置报告",
        2: "A 位置报告 (分配)",
        3: "A 位置报告 (应答)",
        4: "基站报告",
        5: "静态与航程",
        6: "二值地址",
        7: "二值确认",
        8: "二值广播",
        9: "SAR 飞机位置",
        10: "UTC/日期查询",
        11: "UTC/日期应答",
        12: "地址安全",
        13: "安全确认",
        14: "安全广播",
        15: "询问",
        16: "分配",
        17: "DGNSS 广播",
        18: "B 位置报告 (标准)",
        19: "B 位置报告 (扩展)",
        20: "数据链管理",
        21: "助航报告",
        22: "信道管理",
        23: "群组分配",
        24: "静态数据报告",
        25: "单时隙二进制",
        26: "多时隙二进制",
        27: "长距离 AIS",
    };

    // ── 工具 ────────────────────────────────
    function $(id) { return document.getElementById(id); }

    function fmtTs(s) {
        if (!s) return "-";
        return s.replace("T", " ").replace("Z", "");
    }

    function fetchJSON(url) {
        return fetch(url)
            .then(function (r) {
                if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || ("HTTP " + r.status)); });
                return r.json();
            });
    }

    function destroyChart(key) {
        if (charts[key]) {
            charts[key].destroy();
            charts[key] = null;
        }
    }

    // Chart.js 全局默认（深色主题）
    Chart.defaults.color = "#c3cfe0";
    Chart.defaults.borderColor = "rgba(120,180,220,0.12)";
    Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto";

    // ── 概览 ────────────────────────────────
    function loadOverview() {
        return fetchJSON("/api/analytics/overview").then(function (d) {
            $("ov-total").textContent = d.total.toLocaleString();
            $("ov-ships").textContent = d.ship_count.toLocaleString();
            $("ov-latest").textContent = fmtTs(d.latest).slice(5, 16);
            $("ov-earliest").textContent = "首发: " + fmtTs(d.earliest);
            $("ov-today").textContent = d.today.toLocaleString();
            $("ov-today-sub").textContent = "以最新消息日期计";
        });
    }

    // ── Tab 1: 总览 / 类型 ──────────────────────
    function loadMsgType() {
        return fetchJSON("/api/analytics/msg-types").then(function (d) {
            destroyChart("msgType");
            var labels = d.rows.map(function (r) {
                return "T" + r.msg_type + " " + (MSG_TYPE_LABEL[r.msg_type] || "");
            });
            var counts = d.rows.map(function (r) { return r.count; });
            var ctx = $("chart-msg-type").getContext("2d");
            charts.msgType = new Chart(ctx, {
                type: "bar",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "消息数",
                        data: counts,
                        backgroundColor: "rgba(45, 212, 191, 0.6)",
                        borderColor: "rgba(45, 212, 191, 1)",
                        borderWidth: 1,
                    }],
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) { return ctx.parsed.x.toLocaleString() + " 条"; },
                            },
                        },
                    },
                    scales: {
                        x: { beginAtZero: true, grid: { color: "rgba(120,180,220,0.06)" } },
                        y: { grid: { display: false } },
                    },
                },
            });
        });
    }

    function loadTopShips() {
        return fetchJSON("/api/analytics/top-ships?limit=20").then(function (d) {
            destroyChart("topShips");
            var labels = d.rows.map(function (r) { return String(r.mmsi); });
            var counts = d.rows.map(function (r) { return r.count; });
            var ctx = $("chart-top-ships").getContext("2d");
            charts.topShips = new Chart(ctx, {
                type: "bar",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "消息数",
                        data: counts,
                        backgroundColor: "rgba(249, 115, 22, 0.6)",
                        borderColor: "rgba(249, 115, 22, 1)",
                        borderWidth: 1,
                    }],
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) { return ctx.parsed.x.toLocaleString() + " 条"; },
                            },
                        },
                    },
                    scales: {
                        x: { beginAtZero: true, grid: { color: "rgba(120,180,220,0.06)" } },
                        y: { grid: { display: false } },
                    },
                },
            });
        });
    }

    // ── Tab 2: 时间分布 ──────────────────────
    function loadTemporal() {
        var mins = parseInt($("bucket-minutes").value, 10) || 5;
        return fetchJSON("/api/analytics/temporal?bucket_minutes=" + mins)
            .then(function (d) {
                destroyChart("temporal");
                // 配色（每种 msg_type 一种色）
                var palette = [
                    "rgba(45,212,191,0.7)", "rgba(249,115,22,0.7)",
                    "rgba(96,165,250,0.7)", "rgba(245,158,11,0.7)",
                    "rgba(239,68,68,0.7)", "rgba(168,85,247,0.7)",
                    "rgba(34,197,94,0.7)", "rgba(236,72,153,0.7)",
                ];
                var types = Object.keys(d.by_type);
                var datasets = types.map(function (t, idx) {
                    return {
                        label: "T" + t + " " + (MSG_TYPE_LABEL[t] || ""),
                        data: d.by_type[t],
                        backgroundColor: palette[idx % palette.length],
                        borderColor: palette[idx % palette.length].replace("0.7", "1"),
                        fill: true,
                        stack: "1",
                    };
                });

                var ctx = $("chart-temporal").getContext("2d");
                charts.temporal = new Chart(ctx, {
                    type: "bar",
                    data: { labels: d.labels, datasets: datasets },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: "index", intersect: false },
                        plugins: {
                            legend: {
                                position: "bottom",
                                labels: { boxWidth: 10, padding: 8, font: { size: 10 } },
                            },
                            tooltip: {
                                callbacks: {
                                    footer: function (items) {
                                        var s = 0;
                                        items.forEach(function (i) { s += i.parsed.y; });
                                        return "合计: " + s.toLocaleString();
                                    },
                                },
                            },
                        },
                        scales: {
                            x: {
                                stacked: true,
                                grid: { color: "rgba(120,180,220,0.06)" },
                                ticks: {
                                    autoSkip: true,
                                    maxRotation: 0,
                                    callback: function (val, idx, ticks) {
                                        if (d.labels[idx]) return d.labels[idx];
                                        return null;
                                    },
                                },
                            },
                            y: {
                                stacked: true,
                                beginAtZero: true,
                                grid: { color: "rgba(120,180,220,0.06)" },
                            },
                        },
                    },
                });
            });
    }

    function loadHeatmap() {
        return fetchJSON("/api/analytics/hourly-heatmap").then(function (d) {
            destroyChart("heatmap");
            var maxN = 0, sumN = 0;
            d.grid.forEach(function (row) {
                row.forEach(function (v) { if (v > maxN) maxN = v; sumN += v; });
            });
            $("heat-sub").textContent = "共 " + sumN.toLocaleString() + " 条 · 峰值 " + maxN;

            // 简单 HTML 渲染（Chart.js 没有原生 heatmap，用 div 实现更轻量更清晰）
            var canvas = $("chart-heatmap");
            canvas.style.display = "none";
            var parent = canvas.parentElement;
            var existing = parent.querySelector(".heatmap-table");
            if (existing) existing.remove();

            var table = document.createElement("div");
            table.className = "heatmap-table";
            table.style.fontSize = "10px";
            table.style.color = "var(--ink-300)";
            table.style.fontFamily = "ui-monospace, monospace";
            table.style.display = "grid";
            table.style.gridTemplateColumns = "auto repeat(24, 1fr)";
            table.style.gridAutoRows = "22px";
            table.style.gap = "2px";
            table.style.width = "100%";

            // header
            var h00 = document.createElement("div");
            h00.textContent = "";
            table.appendChild(h00);
            for (var h = 0; h < 24; h++) {
                var c = document.createElement("div");
                c.textContent = h;
                c.style.textAlign = "center";
                c.style.color = "var(--ink-400)";
                table.appendChild(c);
            }
            for (var day = 0; day < 7; day++) {
                var dc = document.createElement("div");
                dc.textContent = d.days[day];
                dc.style.color = "var(--ink-300)";
                dc.style.paddingRight = "6px";
                dc.style.textAlign = "right";
                table.appendChild(dc);
                for (var hh = 0; hh < 24; hh++) {
                    var v = d.grid[day][hh];
                    var cell = document.createElement("div");
                    cell.title = d.days[day] + " " + hh + ":00 — " + v + " 条";
                    cell.style.borderRadius = "3px";
                    if (maxN === 0) {
                        cell.style.background = "rgba(45,212,191,0.04)";
                    } else {
                        // log scale 防止某小时出现极端值
                        var ratio = Math.log(1 + v) / Math.log(1 + maxN);
                        var alpha = 0.1 + 0.9 * ratio;
                        cell.style.background = "rgba(45,212,191," + alpha.toFixed(2) + ")";
                        cell.textContent = v > 0 ? v : "";
                        cell.style.color = alpha > 0.5 ? "var(--ocean-900)" : "var(--ink-100)";
                        cell.style.textAlign = "center";
                        cell.style.lineHeight = "22px";
                    }
                    table.appendChild(cell);
                }
            }
            parent.appendChild(table);
        });
    }

    // ── Tab 3: 空间分布 ──────────────────────
    function loadSpatial() {
        return fetchJSON("/api/analytics/geo-grid?precision=2&top=50").then(function (d) {
            destroyChart("spatial");
            d.rows.forEach(function (r, i) {
                if (r.lon > 170) r.lon -= 360;  // 太平洋穿越日期线统一
            });
            // 散点图
            var ctx = $("chart-spatial").getContext("2d");
            charts.spatial = new Chart(ctx, {
                type: "scatter",
                data: {
                    datasets: [{
                        label: "船舶位置热点",
                        data: d.rows.map(function (r) { return { x: r.lon, y: r.lat, n: r.count }; }),
                        backgroundColor: "rgba(249,115,22,0.6)",
                        borderColor: "rgba(249,115,22,1)",
                        pointRadius: function (ctx) {
                            var v = ctx.raw && ctx.raw.n || 0;
                            return Math.max(3, Math.min(20, 3 + Math.log10(1 + v) * 4));
                        },
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) {
                                    var r = ctx.raw;
                                    return "经度 " + r.x.toFixed(2) + " · 纬度 " + r.y.toFixed(2)
                                        + " · " + r.n.toLocaleString() + " 条";
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            type: "linear",
                            title: { display: true, text: "经度" },
                            grid: { color: "rgba(120,180,220,0.06)" },
                            min: Math.min.apply(null, d.rows.map(function (r) { return r.lon; })) - 1,
                            max: Math.max.apply(null, d.rows.map(function (r) { return r.lon; })) + 1,
                        },
                        y: {
                            type: "linear",
                            title: { display: true, text: "纬度" },
                            grid: { color: "rgba(120,180,220,0.06)" },
                            min: Math.min.apply(null, d.rows.map(function (r) { return r.lat; })) - 1,
                            max: Math.max.apply(null, d.rows.map(function (r) { return r.lat; })) + 1,
                        },
                    },
                },
            });

            // 右侧 list
            var maxN = d.rows.length ? d.rows[0].count : 0;
            var html = "";
            d.rows.forEach(function (r, i) {
                if (i >= 15) return; // 只列前 15
                var pct = maxN ? (r.count / maxN * 100) : 0;
                html += '<div class="row">'
                    + '<span>#' + (i + 1) + ' ' + r.lat.toFixed(2) + ' ,' + r.lon.toFixed(2) + '</span>'
                    + '<span><span class="bar" style="width:' + pct.toFixed(0) + '%;"></span></span>'
                    + '<span>' + r.count + '</span>'
                    + '</div>';
            });
            $("geo-list").innerHTML = html || "<div class='empty-tip'>暂无数据</div>";
        });
    }

    // ── Tab 4: 航速 / 航向 ──────────────────────
    function loadSpeed() {
        return fetchJSON("/api/analytics/speed-distribution").then(function (d) {
            destroyChart("speed");
            var labels = d.rows.map(function (r) { return r.bucket + "–" + (r.bucket + 5); });
            var data = d.rows.map(function (r) { return r.count; });
            var ctx = $("chart-speed").getContext("2d");
            charts.speed = new Chart(ctx, {
                type: "bar",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "消息数",
                        data: data,
                        backgroundColor: "rgba(96,165,250,0.6)",
                        borderColor: "rgba(96,165,250,1)",
                        borderWidth: 1,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) { return ctx.parsed.y.toLocaleString() + " 条"; },
                                title: function (items) { return items[0].label + " 节"; },
                            },
                        },
                    },
                    scales: {
                        x: { grid: { display: false } },
                        y: { beginAtZero: true, grid: { color: "rgba(120,180,220,0.06)" } },
                    },
                },
            });
        });
    }

    function loadCourse() {
        return fetchJSON("/api/analytics/course-distribution").then(function (d) {
            destroyChart("course");
            var labels = d.rows.map(function (r) {
                return r.dir + "\n" + r.deg_start + "°";
            });
            var data = d.rows.map(function (r) { return r.count; });
            var ctx = $("chart-course").getContext("2d");
            charts.course = new Chart(ctx, {
                type: "polarArea",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "航向",
                        data: data,
                        backgroundColor: [
                            "rgba(45,212,191,0.7)", "rgba(74,222,128,0.7)",
                            "rgba(245,158,11,0.7)", "rgba(249,115,22,0.7)",
                            "rgba(239,68,68,0.7)", "rgba(236,72,153,0.7)",
                            "rgba(168,85,247,0.7)", "rgba(96,165,250,0.7)",
                            "rgba(45,212,191,0.7)", "rgba(74,222,128,0.7)",
                            "rgba(245,158,11,0.7)", "rgba(249,115,22,0.7)",
                            "rgba(239,68,68,0.7)", "rgba(236,72,153,0.7)",
                            "rgba(168,85,247,0.7)", "rgba(96,165,250,0.7)",
                        ],
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "right",
                            labels: { boxWidth: 10, padding: 6, font: { size: 10 } },
                        },
                    },
                    scales: {
                        r: {
                            beginAtZero: true,
                            grid: { color: "rgba(120,180,220,0.15)" },
                            angleLines: { color: "rgba(120,180,220,0.15)" },
                            ticks: { display: false },
                        },
                    },
                },
            });
        });
    }

    // ── Tab 5: 异常 ──────────────────────
    function esc(s) {
        if (s == null) return "";
        var d = document.createElement("div");
        d.textContent = String(s);
        return d.innerHTML;
    }

    function renderTable(targetId, rows, columns) {
        var target = $(targetId);
        if (!rows || rows.length === 0) {
            target.innerHTML = '<div class="empty-tip">无异常记录</div>';
            return;
        }
        var thead = "<tr>" + columns.map(function (c) { return "<th>" + c.label + "</th>"; }).join("") + "</tr>";
        var tbody = rows.map(function (r) {
            return "<tr>" + columns.map(function (c) {
                var v;
                if (typeof c.render === "function") v = c.render(r);
                else v = esc(r[c.field]);
                return "<td>" + (c.num ? '<span class="num">' + v + "</span>" : v) + "</td>";
            }).join("") + "</tr>";
        }).join("");
        target.innerHTML = '<table class="analytics-table"><thead>' + thead + '</thead><tbody>'
            + tbody + "</tbody></table>";
    }

    function loadAnomalies() {
        return fetchJSON("/api/analytics/anomalies").then(function (d) {
            $("an-1").textContent = d.summary.invalid_location_count.toLocaleString();
            $("an-2").textContent = d.summary.partial_decode_count.toLocaleString();
            $("an-3").textContent = d.summary.abnormal_speed_count.toLocaleString();
            $("an-4").textContent = d.summary.location_jumps_count.toLocaleString();

            renderTable("tbl-1", d.invalid_location, [
                { label: "时间", field: "ts", render: function (r) { return esc(fmtTs(r.ts)); } },
                { label: "MMSI", field: "mmsi", num: true },
                { label: "纬度", field: "latitude", num: true },
                { label: "经度", field: "longitude", num: true },
                { label: "类型", field: "msg_type", render: function (r) {
                    return "<span class=\"badge\">T" + r.msg_type + "</span>";
                }},
                { label: "原因", field: "reason" },
            ]);
            renderTable("tbl-3", d.abnormal_speed, [
                { label: "时间", field: "ts", render: function (r) { return esc(fmtTs(r.ts)); } },
                { label: "MMSI", field: "mmsi", num: true },
                { label: "SOG(节)", field: "sog", num: true, render: function (r) {
                    return r.sog != null ? Number(r.sog).toFixed(1) : "-";
                }},
                { label: "COG(°)", field: "cog", num: true },
                { label: "原因", field: "reason" },
            ]);
            renderTable("tbl-4", d.location_jumps, [
                { label: "MMSI", field: "mmsi", num: true },
                { label: "时间 A", render: function (r) { return esc(fmtTs(r.ts_a)); } },
                { label: "时间 B", render: function (r) { return esc(fmtTs(r.ts_b)); } },
                { label: "起点", render: function (r) {
                    return r.lat_a.toFixed(3) + ", " + r.lon_a.toFixed(3);
                }},
                { label: "终点", render: function (r) {
                    return r.lat_b.toFixed(3) + ", " + r.lon_b.toFixed(3);
                }},
                { label: "距离", field: "km", num: true, render: function (r) {
                    return "<span class=\"badge warning\">" + r.km + " km</span>";
                }},
            ]);
        });
    }

    // ── Tab 调度 ─────────────────────────────
    function activate(tab) {
        document.querySelectorAll(".analytics-tab").forEach(function (t) {
            t.classList.toggle("active", t.dataset.tab === tab);
        });
        document.querySelectorAll(".tab-pane").forEach(function (p) {
            p.hidden = (p.dataset.tab !== tab);
        });
        var loaders = {
            overview: function () { return Promise.all([loadMsgType(), loadTopShips()]); },
            temporal: function () { return Promise.all([loadTemporal(), loadHeatmap()]); },
            spatial: function () { return loadSpatial(); },
            motion: function () { return Promise.all([loadSpeed(), loadCourse()]); },
            anomaly: function () { return loadAnomalies(); },
        };
        loaders[tab]().catch(function (e) {
            console.error("[Analytics]", tab, e);
            alert("加载失败：" + e.message);
        });
    }

    function refreshAll() {
        return loadOverview().then(function () { return activate("overview"); });
    }

    // 入口
    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".analytics-tab").forEach(function (t) {
            t.addEventListener("click", function () { activate(t.dataset.tab); });
        });
        $("bucket-minutes").addEventListener("change", function () {
            if (!$(".tab-pane[data-tab='temporal']").hidden) loadTemporal();
        });
        $("btn-refresh").addEventListener("click", function () {
            refreshAll().catch(function (e) { alert("刷新失败：" + e.message); });
        });
        refreshAll().catch(function (e) { alert("初始化失败：" + e.message); });
    });
})();
