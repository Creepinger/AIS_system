// 船舶信息解析子页面逻辑
(function () {
    "use strict";

    // 字段中英文映射（用于友好展示）
    var FIELD_LABELS = {
        mmsi: "MMSI",
        msg_type: "消息类型",
        lat: "纬度(°)",
        lon: "经度(°)",
        latitude: "纬度(°)",
        longitude: "经度(°)",
        speed: "航速(节)",
        sog: "航速(节)",
        course: "航向(°)",
        cog: "航向(°)",
        heading: "船首向(°)",
        true_heading: "真船首向(°)",
        timestamp: "时间戳(秒)",
        utc_second: "UTC秒",
        day: "日",
        month: "月",
        year: "年",
        hour: "小时",
        minute: "分钟",
        status: "航行状态",
        nav_status: "航行状态",
        rot: "转向率",
        turn: "转向指示",
        pos_accuracy: "位置精度",
        raim: "RAIM",
        shipname: "船名",
        ship_type: "船舶类型",
        type: "船舶类型",
        imo: "IMO",
        callsign: "呼号",
        dest: "目的地",
        destination: "目的地",
        to_bow: "船首到天线(m)",
        to_stern: "船尾到天线(m)",
        to_port: "左舷到天线(m)",
        to_starboard: "右舷到天线(m)",
        dim_bow: "船首尺寸(m)",
        dim_stern: "船尾尺寸(m)",
        dim_port: "左舷尺寸(m)",
        dim_starboard: "右舷尺寸(m)",
        draught: "吃水(m)",
        draft: "吃水(m)",
        slot_increment: "时隙增量",
        slots: "时隙数",
        timeout: "超时值",
        slot_offset: "时隙偏移",
        repeat: "重复指示",
        rxtype: "接收机类型",
        signal: "信号状态",
        unit: "B类单元",
        cs: "载波侦听",
        display: "显示标志",
        dsc: "DSC标志",
        band: "频段",
        band_f: "频段标志",
        msg22: "Msg22",
        msg22_f: "Msg22标志",
        mode: "模式",
        assigned: "指派模式",
        spare: "备用",
        reserved: "保留",
        comm_state: "通信状态",
        name_to_20: "船名(msg19)",
    };

    function getLabel(k) { return FIELD_LABELS[k] || k; }

    function fmt(k, v) {
        if (v === null || v === undefined || v === "") return "-";
        if (typeof v !== "number") return String(v);
        if (k === "lat" || k === "latitude") {
            return v.toFixed(6) + (v >= 0 ? " N" : " S");
        }
        if (k === "lon" || k === "longitude") {
            return v.toFixed(6) + (v >= 0 ? " E" : " W");
        }
        if (k === "speed" || k === "sog" || k === "course" || k === "cog"
            || k === "heading" || k === "true_heading" || k === "rot" || k === "turn") {
            return v.toFixed(1);
        }
        if (k === "draught" || k === "draft") return v.toFixed(2);
        if (Number.isInteger(v)) return String(v);
        return v.toFixed(2);
    }

    function isOk(name, val) {
        if (name === "Δlat" || name === "Δlon") return val < 0.0001;
        if (name === "Δsog") return val < 0.5;
        if (name === "Δcog") return val < 0.5;
        return val < 0.0001;
    }

    function hasWarn(err) {
        if (!err) return false;
        return err.lat > 0.0001 || err.lon > 0.0001
            || err.sog > 0.5 || err.cog > 0.5;
    }

    // DOM 引用
    var inputEl, resultEl, decoderSelect;
    var lineCountEl, parseResultInfoEl;
    var btnParse, btnClearInput, btnExample;

    // 示例数据（确保 BCC 校验码正确）
    var EXAMPLE_LINES = [
        "!AIVDM,1,1,,A,15MwkRUOidG?GLaKG>R;wT4F>4F2220,0*1F",
        "!AIVDM,1,1,,B,100u99kP0QHrqN6LqCMA:6F2220,0*3A",
        "!AIVDM,1,1,,A,B6:6Ir00FJ;K:=TJ>P99CweT2000,0*52",
        "!AIVDM,1,1,,B,B6:BiD00C2;Jh9TJ@j9D94=SQP06,0*73",
        "!AIVDM,1,1,,A,403t>UivUcRsI`gcpFAMqdo004Cd,0*4B",
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
        parseResultInfoEl.textContent = "就绪";
        resultEl.innerHTML = "<div class=\"parse-empty-hint\">解析结果将在这里显示</div>";
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
        parseResultInfoEl.textContent = "解析中…";
        btnParse.disabled = true;

        fetch("/api/parse_text", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lines: lines, mode: mode })
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
            resultEl.innerHTML = "<div class=\"parse-error-box\">" + escapeHtml(String(err)) + "</div>";
        })
        .finally(function () {
            btnParse.disabled = false;
        });
    }

    function renderResults(results) {
        if (!results.length) {
            resultEl.innerHTML = "<div class=\"parse-empty-hint\">无解析结果</div>";
            return;
        }
        resultEl.innerHTML = "";
        results.forEach(function (r, idx) {
            resultEl.appendChild(buildResultItem(r, idx));
        });
    }

    function buildResultItem(r) {
        var item = document.createElement("div");
        item.className = "parse-result-item";

        // 头部
        var head = document.createElement("div");
        head.className = "parse-result-head";

        var left = document.createElement("div");
        left.className = "parse-result-head-left";

        var statusTag;
        if (!r.success) {
            statusTag = "<span class=\"parse-tag tag-error\">失败</span>";
        } else if (r.errors && hasWarn(r.errors)) {
            statusTag = "<span class=\"parse-tag tag-warn\">有偏差</span>";
        } else {
            statusTag = "<span class=\"parse-tag tag-ok\">通过</span>";
        }
        left.innerHTML = statusTag
            + "<span class=\"parse-tag tag-type\">类型 " + (r.msg_type || "-") + "</span>"
            + "<span class=\"parse-tag tag-mmsi\">MMSI " + (r.mmsi || "-") + "</span>";

        var right = document.createElement("div");
        right.className = "raw";
        right.textContent = r.raw || "";

        head.appendChild(left);
        head.appendChild(right);
        item.appendChild(head);

        // 主体
        var body = document.createElement("div");
        body.className = "parse-result-body";

        if (!r.success) {
            var eb = document.createElement("div");
            eb.className = "parse-error-box";
            eb.textContent = r.error || "解码失败";
            body.appendChild(eb);
            item.appendChild(body);
            return item;
        }

        if (r.custom && r.pyais) {
            body.appendChild(buildCompareSection(r));
        } else if (r.custom) {
            body.appendChild(buildSingleSection("自研解析器结果", r.custom));
        } else if (r.pyais) {
            body.appendChild(buildSingleSection("pyais 库结果", r.pyais));
        } else {
            var ok = document.createElement("div");
            ok.className = "parse-summary-ok";
            ok.textContent = "解析成功";
            body.appendChild(ok);
        }

        item.appendChild(body);
        return item;
    }

    function buildCompareSection(r) {
        var sec = document.createElement("div");
        sec.className = "parse-compare-section";

        var title = document.createElement("div");
        title.className = "parse-section-title";
        title.textContent = "自研 vs pyais 对比";
        sec.appendChild(title);

        var grid = document.createElement("div");
        grid.className = "parse-field-grid";

        // 自研 -> pyais 字段名映射
        var pairs = [
            ["纬度(°)",    "latitude", "lat"],
            ["经度(°)",    "longitude", "lon"],
            ["航速(节)",   "sog", "speed"],
            ["航向(°)",    "cog", "course"],
            ["船首向(°)",  "heading", "true_heading"],
            ["UTC秒",      "utc_second", "timestamp"],
            ["年",         "year", "year"],
            ["月",         "month", "month"],
            ["日",         "day", "day"],
            ["小时",       "hour", "hour"],
            ["分钟",       "minute", "minute"],
            ["航行状态",   "status", "status"],
            ["转向率",     "rot", "rot"],
            ["位置精度",   "pos_accuracy", "pos_accuracy"],
            ["RAIM",       "raim", "raim"],
            ["船名",       "shipname", "shipname"],
            ["船舶类型",   "ship_type", "type"],
            ["IMO",        "imo", "imo"],
            ["呼号",       "callsign", "callsign"],
            ["目的地",     "dest", "destination"],
            ["吃水(m)",    "draught", "draught"],
            ["重复指示",   "repeat", "repeat"],
        ];

        var shown = {};

        pairs.forEach(function (f) {
            var label = f[0], ck = f[1], pk = f[2];
            shown[ck] = true; shown[pk] = true;

            var cv = r.custom[ck], pv = r.pyais[pk];
            if (cv === undefined && pv === undefined) return;

            var lbl = document.createElement("div");
            lbl.className = "lbl";
            lbl.textContent = label;
            grid.appendChild(lbl);

            var cdiv = document.createElement("div");
            cdiv.className = "custom-val";
            cdiv.textContent = fmt(ck, cv);
            grid.appendChild(cdiv);

            var pdiv = document.createElement("div");
            pdiv.className = "pyais-val";
            pdiv.textContent = fmt(pk, pv);
            grid.appendChild(pdiv);
        });

        // 动态补充其他字段
        appendExtraFields(grid, r.custom, "custom-val", shown);
        appendExtraFields(grid, r.pyais, "pyais-val", shown);

        // 误差行
        if (r.errors) {
            var errs = [
                ["Δlat", r.errors.lat, 6],
                ["Δlon", r.errors.lon, 6],
                ["Δsog", r.errors.sog, 2],
                ["Δcog", r.errors.cog, 1],
            ];
            errs.forEach(function (f) {
                var lbl = document.createElement("div");
                lbl.className = "lbl";
                lbl.textContent = f[0];
                grid.appendChild(lbl);

                var c = document.createElement("div");
                c.className = "custom-val";
                c.textContent = "-";
                grid.appendChild(c);

                var p = document.createElement("div");
                p.className = "err-val " + (isOk(f[0], f[1]) ? "ok" : "warn");
                p.textContent = f[1].toFixed(f[2]);
                grid.appendChild(p);
            });
        }

        sec.appendChild(grid);
        return sec;
    }

    function appendExtraFields(grid, obj, valClass, shown) {
        Object.keys(obj).forEach(function (k) {
            if (shown[k]) return;
            shown[k] = true;
            var v = obj[k];
            if (v === undefined || typeof v === "object") return;

            var lbl = document.createElement("div");
            lbl.className = "lbl";
            lbl.textContent = getLabel(k);
            grid.appendChild(lbl);

            var c = document.createElement("div");
            c.className = valClass;
            c.textContent = fmt(k, v);
            grid.appendChild(c);

            var p = document.createElement("div");
            p.className = (valClass === "custom-val" ? "pyais-val" : "custom-val");
            p.textContent = "-";
            grid.appendChild(p);
        });
    }

    function buildSingleSection(title, obj) {
        var sec = document.createElement("div");
        sec.className = "parse-compare-section";

        var t = document.createElement("div");
        t.className = "parse-section-title";
        t.textContent = title;
        sec.appendChild(t);

        var grid = document.createElement("div");
        grid.className = "parse-field-grid";

        // 优先级字段
        var order = [
            "mmsi", "msg_type",
            "latitude", "lat", "longitude", "lon",
            "sog", "speed", "cog", "course", "heading", "true_heading",
            "utc_second", "timestamp", "year", "month", "day", "hour", "minute",
            "status", "nav_status", "rot", "turn",
            "pos_accuracy", "raim", "repeat",
            "shipname", "ship_type", "type", "imo", "callsign", "destination", "dest",
            "to_bow", "to_stern", "to_port", "to_starboard",
            "dim_bow", "dim_stern", "dim_port", "dim_starboard",
            "draught", "draft",
            "slot_increment", "slots", "timeout", "slot_offset",
            "reserved", "comm_state", "mode", "spare",
            "unit", "cs", "display", "dsc", "band_f", "msg22_f",
        ];
        var shown = {};
        order.forEach(function (k) {
            if (shown[k] || obj[k] === undefined) return;
            shown[k] = true;
            appendSingleRow(grid, k, obj[k]);
        });
        Object.keys(obj).forEach(function (k) {
            if (shown[k]) return;
            shown[k] = true;
            appendSingleRow(grid, k, obj[k]);
        });

        sec.appendChild(grid);
        return sec;
    }

    function appendSingleRow(grid, k, v) {
        if (v === undefined || typeof v === "object") return;

        var lbl = document.createElement("div");
        lbl.className = "lbl";
        lbl.textContent = getLabel(k);
        grid.appendChild(lbl);

        var c = document.createElement("div");
        c.className = "custom-val";
        c.textContent = fmt(k, v);
        grid.appendChild(c);

        var p = document.createElement("div");
        p.className = "pyais-val";
        p.textContent = "-";
        grid.appendChild(p);
    }

    function escapeHtml(s) {
        return String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();