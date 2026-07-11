// 地图模块:Leaflet + 高德矢量瓦片(国内可访问)。
// marker 由 ws_client 推送的 ship 信息动态创建。
// 注意:高德使用 GCJ-02 坐标系,前端不做坐标纠偏,所以 marker 会有几百米偏移;
    // 想要精确显示可在 Python 端做 WGS-84 → GCJ-02 转换,这里仅保证可视化。
(function (global) {
    "use strict";

    var map = null;
    var markers = {};   // mmsi → L.marker
    var allShips = {};  // mmsi → ship dict
    var initialCenter = [22.3, 114.2];
    var initialZoom = 4;
    var userHasInteracted = false;  // 用户手动操作后不再自动 fit
    var selectedMmsi = null;        // 当前选中的船舶 mmsi

    function init() {
        var mapEl = document.getElementById("map");
        if (!mapEl) { console.error("找不到 map 元素"); return; }

        map = L.map(mapEl, {
            center: initialCenter,
            zoom: initialZoom,
            // 显式开启所有交互
            zoomControl: true,
            scrollWheelZoom: true,
            doubleClickZoom: true,
            dragging: true,
            tap: true,
            keyboard: true,
            // 限制缩放范围
            minZoom: 3,
            maxZoom: 18,
        });

        // 国内访问 OSM 极不稳定,改用高德矢量瓦片(无需 key,对 Leaflet 即用即得)。
        // 注意:高德为 GCJ-02 坐标系,和 AIS 解出的 WGS-84 经纬度会有几百米偏差,
        // 但保证地图能正常渲染。
        L.tileLayer("https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}", {
            subdomains: ["1", "2", "3", "4"],
            maxZoom: 18,
            attribution: '&copy; 高德地图'
        }).addTo(map);

        // 标记用户是否手动操作过地图(pan/zoom),操作后不再自动 fit
        map.on("mousedown",  function () { userHasInteracted = true; });
        map.on("mousewheel", function () { userHasInteracted = true; });
        map.on("touchstart", function () { userHasInteracted = true; });

        // 点击地图取消选中
        map.on("click", function () {
            global.WSClient.send({ cmd: "noop" });
        });
    }

    // 按消息类型返回主题色
    function _colorFor(msgType) {
        if (msgType === 1) return "#ef4444";       // A 类 - 红
        if (msgType === 5) return "#22c55e";       // 静态 - 绿
        if (msgType === 18) return "#f59e0b";      // B 类 - 黄
        return "#60a5fa";                          // 其他 - 蓝
    }

    // 升级版船形 SVG 图标: 带白色描边, 按 cog 旋转, 选中态高亮
    function _icon(cog, color, selected) {
        var c = color || "#ef4444";
        var sel = selected ? " selected" : "";
        var rot = cog || 0;
        // 船帆 (三角) + 船体 (梯形), 整体绕中心旋转
        var svg =
            '<svg viewBox="0 0 24 24" width="24" height="24" xmlns="http://www.w3.org/2000/svg"' +
            ' style="color:' + c + ';">' +
              '<g transform="rotate(' + rot + ' 12 12)">' +
                // 船帆/上层建筑: 三角形
                '<path d="M12 3 L17 13 L7 13 Z"' +
                ' fill="' + c + '" stroke="#ffffff" stroke-width="1.3"' +
                ' stroke-linejoin="round"/>' +
                // 船体: 梯形
                '<path d="M5 13 L19 13 L17 19 L7 19 Z"' +
                ' fill="' + c + '" stroke="#ffffff" stroke-width="1.3"' +
                ' stroke-linejoin="round"/>' +
                // 中线 (船头到船尾, 弱化)
                '<line x1="12" y1="4" x2="12" y2="18"' +
                ' stroke="#ffffff" stroke-width="0.5" stroke-opacity="0.55"/>' +
              '</g>' +
            '</svg>';
        return L.divIcon({
            className: "ship-icon" + sel,
            html: svg,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        });
    }

    // 选中某船: 切换 selectedMmsi 并更新相关 marker 图标
    function selectShip(mmsi) {
        if (selectedMmsi === mmsi) return;
        // 取消上一选中
        if (selectedMmsi && markers[selectedMmsi] && allShips[selectedMmsi]) {
            var prev = allShips[selectedMmsi];
            markers[selectedMmsi].setIcon(
                _icon(prev.cog, _colorFor(prev.msg_type), false)
            );
        }
        selectedMmsi = mmsi;
        // 应用新选中
        if (mmsi && markers[mmsi] && allShips[mmsi]) {
            var s = allShips[mmsi];
            markers[mmsi].setIcon(
                _icon(s.cog, _colorFor(s.msg_type), true)
            );
        }
    }

    function popupContent(s) {
        return (
            "<b>MMSI:</b> " + s.mmsi +
            "<br><b>船名:</b> " + (s.shipname || "-") +
            "<br><b>位置:</b> " + s.latitude.toFixed(5) + ", " + s.longitude.toFixed(5) +
            "<br><b>航速:</b> " + s.sog.toFixed(1) + " kn" +
            "<br><b>航向:</b> " + s.cog + "°" +
            "<br><b>UTC秒:</b> " + (s.utc_second >= 0 ? s.utc_second : "-") +
            "<br><b>类型:</b> " + s.msg_type
        );
    }

    function fitToShips() {
        if (userHasInteracted) return;  // 用户手动操作过,不再自动 fit
        var list = Object.values(allShips).filter(function (s) {
            // 过滤掉无效坐标(如 msg5 没有位置信息时,默认 0,0 会落在赤道大西洋)
            return Math.abs(s.latitude) <= 90 && Math.abs(s.longitude) <= 180 &&
                !(s.latitude === 0 && s.longitude === 0);
        });
        if (list.length === 0) {
            map.setView(initialCenter, initialZoom);
            return;
        }
        if (list.length === 1) {
            map.setView([list[0].latitude, list[0].longitude], 8);
            return;
        }
        var bounds = L.latLngBounds(list.map(function (s) {
            return [s.latitude, s.longitude];
        }));
        map.fitBounds(bounds, { padding: [40, 40] });
    }

    function applyShips(ships) {
        var latLngs = [];
        for (var i = 0; i < ships.length; i++) {
            var s = ships[i];
            allShips[s.mmsi] = s;
            // 跳过无效坐标(msg5 静态数据没位置时默认 0,0)
            if (!(s.latitude >= -90 && s.latitude <= 90 &&
                  s.longitude >= -180 && s.longitude <= 180)) continue;
            if (s.latitude === 0 && s.longitude === 0) continue;

            var color = _colorFor(s.msg_type);
            var isSelected = (selectedMmsi === s.mmsi);

            var prev = markers[s.mmsi];
            if (prev) {
                prev.setLatLng([s.latitude, s.longitude]);
                prev.setIcon(_icon(s.cog, color, isSelected));
                prev.setPopupContent(popupContent(s));
            } else {
                var m = L.marker([s.latitude, s.longitude], {
                    icon: _icon(s.cog, color, isSelected),
                }).addTo(map);
                m.bindPopup(popupContent(s));
                m.on("click", function (ev) {
                    var mm = Object.values(allShips).find(function (sh) {
                        return sh.latitude === ev.latlng.lat &&
                               sh.longitude === ev.latlng.lng;
                    });
                    if (mm) {
                        selectShip(mm.mmsi);
                        global.WSClient.send({ cmd: "noop" });
                    }
                });
                markers[s.mmsi] = m;
            }
            latLngs.push([s.latitude, s.longitude]);
        }
        // 收到任意船舶就自动调整视野,使之可见
        if (latLngs.length > 0) {
            fitToShips();
        }
    }

    function clearAll() {
        Object.values(markers).forEach(function (m) { map.removeLayer(m); });
        markers = {};
        allShips = {};
        selectedMmsi = null;  // 清空选中态
        userHasInteracted = false;  // 清空后恢复自动 fit
        map.setView(initialCenter, initialZoom);  // 地图回到初始视野
    }

    global.MapMod = {
        init: init,
        applyShips: applyShips,
        clearAll: clearAll,
        selectShip: selectShip
    };
}(window));

document.addEventListener("DOMContentLoaded", function () {
    MapMod.init();
    WSClient.on(function (msg) {
        if (msg.type === "batch") {
            MapMod.applyShips(msg.ships || []);
        } else if (msg.type === "clear") {
            MapMod.clearAll();
        }
    });
});
