// AIS 在线解析页面逻辑
(function () {
    "use strict";

    var inputEl, resultEl, decoderSelect;
    var lineCountEl, parseResultInfoEl;
    var btnParse, btnClearInput, btnExample;

    // 字段中英文映射（用于友好展示）
    var FIELD_LABELS = {
        // 基础字段
        "mmsi": "MMSI",
        "msg_type": "消息类型",
        // 位置字段
        "lat": "纬度(°)",
        "lon": "经度(°)",
        "latitude": "纬度(°)",
        "longitude": "经度(°)",
        // 运动状态
        "speed": "航速(节)",
        "sog": "航速(节)",
        "course": "航向(°)",
        "cog": "航向(°)",
        "heading": "船首向(°)",
        "true_heading": "真船首向(°)",
        // 时间
        "timestamp": "时间戳(秒)",
        "utc_second": "UTC秒",
        "day": "日期(天)",
        "month": "日期(月)",
        "year": "日期(年)",
        "hour": "小时",
        "minute": "分钟",
        // 航行状态
        "status": "航行状态",
        "nav_status": "航行状态",
        "rot": "转向率",
        "turn": "转向指示",
        // 位置精度
        "pos_accuracy": "位置精度",
        "raim": "RAIM标志",
        // 船舶信息
        "shipname": "船名",
        "ship_type": "船舶类型",
        "type": "船舶类型",
        "imo": "IMO编号",
        "callsign": "呼号",
        "dest": "目的地",
        "destination": "目的地",
        // 尺寸
        "to_bow": "船首到天线(m)",
        "to_stern": "船尾到天线(m)",
        "to_port": "左舷到天线(m)",
        "to_starboard": "右舷到天线(m)",
        "dim_bow": "船首尺寸(m)",
        "dim_stern": "dim_stern",
        "dim_port": "dim_port",
        "dim_starboard": "dim_starboard",
        // 吃水
        "draught": "吃水(m)",
        "draft": "吃水(m)",
        // 数据链路
        "slot_increment": "时隙增量",
        "slots": "时隙数",
        "timeout": "超时值",
        "slot_offset": "时隙偏移",
        // 其他
        "reserved": "保留字段",
        "comm_state": "通信状态",
        "disp": "显示标志",
        "band": "频段标志",
        "msg22": "Msg22频道",
        "assigned": "指派模式",
        "spare": "备用",
        // B 类
        "unit": "B类单元类型",
        "cs": "载波侦听",
        "display": "显示标志",
        "dsc": "DSC标志",
        "band_f": "频段标志",
        "msg22_f": "Msg22标志",
        "mode": "模式标志",
        // A 类
        "repeat": "重复指示",
        "rxtype": "接收机类型",
        "signal": "信号状态",
    };

    function getLabel(key) {
        return FIELD_LABELS[key] || key;
    }

    // 数值格式化
    function formatValue(k, v) {
        if (v === null || v === undefined || v === "") return "-";
        if (typeof v === "number") {
            // 经纬度保留6位小数，并附 E/W/N/S 半球标志
            if (k === "lat" || k === "latitude") {
                return v.toFixed(6) + (v >= 0 ? " N" : " S");
            }
            if (k === "lon" || k === "longitude") {
                return v.toFixed(6) + (v >= 0 ? " E" : " W");
            }
            // 速度/航向保留1位小数
            if (k === "speed" || k === "sog" || k === "course" || k === "cog"
                || k === "heading" || k === "true_heading" || k === "rot" || k === "turn") {
                return v.toFixed(1);
            }
            // 吃水保留2位
            if (k === "draught" || k === "draft") {
                return v.toFixed(2);
            }
            // 整数直接返回
            if (Number.isInteger(v)) return String(v);
            return v.toFixed(2);
        }
        return String(v);
    }

    // 示例数据（取自真实 AIS 数据文件，确保 BCC 校验码正确）
    var EXAMPLE_LINES = [
        "!ABVDM,1,1,8,A,403t>UivUcRsI`gcpFAMqdo004Cd,0*4B",
        "!ABVDM,1,1,,B,16::vBP01M8ei7rAWfeF`h0j0000,0*71",
        "!ABVDM,1,1,9,A,16:M6u0P008g6i0Ac6tQ5?vl0@?r,0*6B",
        "!ABVDM,1,1,0,A,B6:6Ir00FJ;K:=TJ>P99CweT2000,0*52",
        "!ABVDM,1,1,,B,B6:BiD00C2;Jh9TJ@j9D94=SQP06,0*73"
    ];

    function init() {
        inputEl = document.getElementById("nmea-input");
        resultEl = document.getElementById("result-list");
        decoderSelect = document.getElementById("decoder-select");
        lineCountEl = document.getElementById("line-count");
        parseResultInfoEl = document.getElementById("parse-result-info");
        btnParse = document.getElementById("btn-parse");
        btnClearInput = document.getElementById("btn-clear-input");
        btnExample = document.getElementById("btn-example");

        inputEl.addEventListener("input", updateLineCount);
        btnParse.addEventListener("click", onParse);
        btnClearInput.addEventListener("click", onClearInput);
        btnExample.addEventListener("click", onLoadExample);

        updateLineCount();
    }

    function updateLineCount() {
        var lines = (inputEl.value || "").split(/\r?\n/).filter(function (l) {
            return l.trim().length > 0;
        });
        lineCountEl.textContent = lines.length;
    }

    function onClearInput() {
        inputEl.value = "";
        updateLineCount();
        parseResultInfoEl.textContent = "";
    }

    function onLoadExample() {
        inputEl.value = EXAMPLE_LINES.join("\n");
        updateLineCount();
    }

    function onParse() {
        var lines = (inputEl.value || "").split(/\r?\n/)
            .map(function (l) { return l.trim(); })
            .filter(function (l) { return l.length > 0; });

        if (lines.length === 0) {
            parseResultInfoEl.textContent = "无有效内容";
            return;
        }

        var mode = decoderSelect.value;
        parseResultInfoEl.textContent = "解析中...";
        btnParse.disabled = true;

        // 通过后端 API 一次性解析所有行
        fetch("/api/parse_text", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                lines: lines,
                mode: mode
            })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data || !data.results) {
                parseResultInfoEl.textContent = "解析失败";
                return;
            }
            renderResults(data.results);
            var succ = data.results.filter(function (x) { return x.success; }).length;
            parseResultInfoEl.textContent = "成功 " + succ + " / " + data.results.length;
        })
        .catch(function (err) {
            parseResultInfoEl.textContent = "错误: " + err;
            resultEl.innerHTML = "<div class='error-box'>" + err + "</div>";
        })
        .finally(function () {
            btnParse.disabled = false;
        });
    }

    function renderResults(results) {
        resultEl.innerHTML = "";
        results.forEach(function (r, idx) {
            var item = buildResultItem(r, idx);
            resultEl.appendChild(item);
        });
    }

    function buildResultItem(r, idx) {
        var item = document.createElement("div");
        item.className = "result-item";

        // 头部：消息类型、MMSI、状态、原始报文
        var head = document.createElement("div");
        head.className = "result-item-head";

        var left = document.createElement("div");
        var statusTag;
        if (!r.success) {
            statusTag = "<span class='tag tag-error'>失败</span>";
        } else if (r.errors && hasWarn(r.errors)) {
            statusTag = "<span class='tag tag-warn'>有偏差</span>";
        } else {
            statusTag = "<span class='tag tag-ok'>通过</span>";
        }
        left.innerHTML = statusTag
            + "<span class='tag tag-type'>类型" + (r.msg_type || "-") + "</span>"
            + "<span class='mmsi'>MMSI: " + (r.mmsi || "-") + "</span>";

        var right = document.createElement("div");
        right.className = "raw";
        right.textContent = r.raw || "";

        head.appendChild(left);
        head.appendChild(right);
        item.appendChild(head);

        // 主体
        var body = document.createElement("div");
        body.className = "result-item-body";

        if (!r.success) {
            var eb = document.createElement("div");
            eb.className = "error-box";
            eb.textContent = r.error || "解码失败";
            body.appendChild(eb);
            item.appendChild(body);
            return item;
        }

        // 对比模式：分别展示自研 / pyais 数据
        if (r.custom && r.pyais) {
            body.appendChild(buildCompareSection(r));
        } else if (r.custom) {
            body.appendChild(buildSingleSection("自研解析器结果", r.custom, null));
        } else if (r.pyais) {
            body.appendChild(buildSingleSection("pyais 库结果", null, r.pyais));
        }

        item.appendChild(body);
        return item;
    }

    function hasWarn(err) {
        if (!err) return false;
        return err.lat > 0.0001 || err.lon > 0.0001
            || err.sog > 0.5 || err.cog > 0.5;
    }

    function buildCompareSection(r) {
        var sec = document.createElement("div");
        sec.className = "compare-section";

        var title = document.createElement("div");
        title.className = "section-title";
        title.textContent = "自研 vs pyais 对比";
        sec.appendChild(title);

        var grid = document.createElement("div");
        grid.className = "field-grid";

        // 自研 → pyais 字段名映射（同名或异名都统一展示）
        var fieldPairs = [
            // 位置
            ["纬度(°)", "latitude", "lat"],
            ["经度(°)", "longitude", "lon"],
            // 运动
            ["航速(节)", "sog", "speed"],
            ["航向(°)", "cog", "course"],
            ["船首向(°)", "heading", "true_heading"],
            // 时间
            ["UTC秒", "utc_second", "timestamp"],
            ["年", "year", "year"],
            ["月", "month", "month"],
            ["日", "day", "day"],
            ["小时", "hour", "hour"],
            ["分钟", "minute", "minute"],
            // 状态
            ["航行状态", "status", "status"],
            ["转向率", "rot", "rot"],
            ["转向指示", "turn", "turn"],
            // 精度
            ["位置精度", "pos_accuracy", "pos_accuracy"],
            ["RAIM", "raim", "raim"],
            // 船舶信息
            ["船名", "shipname", "shipname"],
            ["船舶类型", "ship_type", "type"],
            ["IMO", "imo", "imo"],
            ["呼号", "callsign", "callsign"],
            ["目的地", "dest", "destination"],
            // 尺寸
            ["船首到天线(m)", "to_bow", "to_bow"],
            ["船尾到天线(m)", "to_stern", "to_stern"],
            ["左舷到天线(m)", "to_port", "to_port"],
            ["右舷到天线(m)", "to_starboard", "to_starboard"],
            // 吃水
            ["吃水(m)", "draught", "draught"],
            // 通信
            ["时隙增量", "slot_increment", "slot_increment"],
            ["时隙数", "slots", "slots"],
            ["超时值", "timeout", "timeout"],
            ["时隙偏移", "slot_offset", "slot_offset"],
            // 其他
            ["重复指示", "repeat", "repeat"],
            ["B类单元", "unit", "unit"],
            ["载波侦听", "cs", "cs"],
        ];

        // 收集已展示的 key（用于避免重复）
        var shown = {};

        // 先按固定顺序展示
        fieldPairs.forEach(function (f) {
            var label = f[0];
            var custKey = f[1];
            var pyaisKey = f[2];
            shown[custKey] = true;
            shown[pyaisKey] = true;

            var cv = r.custom[custKey];
            var pv = r.pyais[pyaisKey];

            // 两者都为 undefined/null 则跳过
            if (cv === undefined && pv === undefined) return;

            var lbl = document.createElement("div");
            lbl.className = "lbl";
            lbl.textContent = label;

            var custDiv = document.createElement("div");
            custDiv.className = "custom-val";
            custDiv.textContent = formatValue(custKey, cv);

            var pyaisDiv = document.createElement("div");
            pyaisDiv.className = "pyais-val";
            pyaisDiv.textContent = formatValue(pyaisKey, pv);

            grid.appendChild(lbl);
            grid.appendChild(custDiv);
            grid.appendChild(pyaisDiv);
        });

        // 再动态展示两方中各自有、对方没有的字段
        Object.keys(r.custom).forEach(function (k) {
            if (shown[k]) return;
            shown[k] = true;
            var v = r.custom[k];
            if (v === undefined || typeof v === "object") return;
            var lbl = document.createElement("div");
            lbl.className = "lbl";
            lbl.textContent = getLabel(k);
            var custDiv = document.createElement("div");
            custDiv.className = "custom-val";
            custDiv.textContent = formatValue(k, v);
            var pyaisDiv = document.createElement("div");
            pyaisDiv.className = "pyais-val";
            pyaisDiv.textContent = "-";
            grid.appendChild(lbl);
            grid.appendChild(custDiv);
            grid.appendChild(pyaisDiv);
        });

        Object.keys(r.pyais).forEach(function (k) {
            if (shown[k]) return;
            shown[k] = true;
            var v = r.pyais[k];
            if (v === undefined || typeof v === "object") return;
            var lbl = document.createElement("div");
            lbl.className = "lbl";
            lbl.textContent = getLabel(k);
            var custDiv = document.createElement("div");
            custDiv.className = "custom-val";
            custDiv.textContent = "-";
            var pyaisDiv = document.createElement("div");
            pyaisDiv.className = "pyais-val";
            pyaisDiv.textContent = formatValue(k, v);
            grid.appendChild(lbl);
            grid.appendChild(custDiv);
            grid.appendChild(pyaisDiv);
        });

        // 误差行（如果有）
        if (r.errors) {
            var errFields = [
                ["Δlat", r.errors.lat, 6],
                ["Δlon", r.errors.lon, 6],
                ["Δsog", r.errors.sog, 2],
                ["Δcog", r.errors.cog, 1]
            ];
            errFields.forEach(function (f) {
                var lbl = document.createElement("div");
                lbl.className = "lbl";
                lbl.textContent = f[0];

                var cv = document.createElement("div");
                cv.className = "custom-val";
                cv.textContent = "-";

                var pv = document.createElement("div");
                pv.className = "err-val " + (isOk(f[0], f[1]) ? "ok" : "warn");
                pv.textContent = f[1].toFixed(f[2]);

                grid.appendChild(lbl);
                grid.appendChild(cv);
                grid.appendChild(pv);
            });
        }

        sec.appendChild(grid);
        return sec;
    }

    function buildSingleSection(title, customObj, pyaisObj) {
        var sec = document.createElement("div");
        sec.className = "compare-section";

        var t = document.createElement("div");
        t.className = "section-title";
        t.textContent = title;
        sec.appendChild(t);

        var grid = document.createElement("div");
        grid.className = "field-grid";

        var obj = customObj || pyaisObj || {};
        var isCustom = !!customObj;

        // 按固定顺序排列重要字段，其余按字母序
        var priorityKeys = ["mmsi", "msg_type", "lat", "latitude", "lon", "longitude",
            "speed", "sog", "course", "cog", "heading", "true_heading",
            "timestamp", "utc_second", "year", "month", "day", "hour", "minute",
            "status", "nav_status", "rot", "turn",
            "pos_accuracy", "raim", "repeat",
            "shipname", "ship_type", "type", "imo", "callsign", "dest", "destination",
            "to_bow", "to_stern", "to_port", "to_starboard",
            "dim_bow", "dim_stern", "dim_port", "dim_starboard",
            "draught", "draft",
            "slot_increment", "slots", "timeout", "slot_offset",
            "reserved", "comm_state", "disp", "band", "msg22", "assigned", "spare",
            "unit", "cs", "display", "dsc", "band_f", "msg22_f", "mode",
            "rxtype", "signal", "name_to_20"];

        // 收集已展示的字段（去重）
        var shown = {};

        // 先展示优先级字段
        priorityKeys.forEach(function (k) {
            if (shown[k] || obj[k] === undefined) return;
            shown[k] = true;
            renderFieldRow(grid, k, obj[k], isCustom);
        });

        // 再展示其余字段
        Object.keys(obj).forEach(function (k) {
            if (shown[k]) return;
            shown[k] = true;
            renderFieldRow(grid, k, obj[k], isCustom);
        });

        sec.appendChild(grid);
        return sec;
    }

    function renderFieldRow(grid, k, v, isCustom) {
        if (v === undefined) return;
        if (typeof v === "object") return;  // 嵌套对象不展示

        var lbl = document.createElement("div");
        lbl.className = "lbl";
        lbl.textContent = getLabel(k);

        var cv = document.createElement("div");
        cv.className = isCustom ? "custom-val" : "pyais-val";
        cv.textContent = formatValue(k, v);

        var pv = document.createElement("div");
        pv.textContent = "-";

        grid.appendChild(lbl);
        grid.appendChild(cv);
        grid.appendChild(pv);
    }

    function formatVal(v, digits) {
        if (v === null || v === undefined) return "-";
        if (typeof v !== "number") return String(v);
        if (Math.abs(v) < 0.000001) return "0";
        return v.toFixed(digits);
    }

    function formatNum(v) {
        if (typeof v !== "number") return String(v);
        if (Number.isInteger(v)) return String(v);
        return v.toFixed(2);
    }

    function isOk(name, val) {
        if (name === "Δlat") return val < 0.0001;
        if (name === "Δlon") return val < 0.0001;
        if (name === "Δsog") return val < 0.5;
        if (name === "Δcog") return val < 0.5;
        return val < 0.0001;
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();