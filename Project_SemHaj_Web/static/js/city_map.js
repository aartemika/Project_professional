/* Карта спроса: контур России и города, окрашенные по доле вакансий или коэффициенту специализации. Работает без интернета. */
(function () {
    const container = document.getElementById("city-map");
    if (!container) return;
    const points = JSON.parse(document.getElementById("map-data").textContent);
    const specialization = container.dataset.mode === "specialization";
    const SCALE = 1000;
    const SHARE_COLORS = ["#ffffd9", "#edf8b1", "#c7e9b4", "#7fcdbb", "#41b6c4", "#1d91c0", "#225ea8", "#253494", "#081d58"];
    const COEFFICIENT_COLORS = ["#8c510a", "#d8b365", "#f6e8c3", "#f5f5f5", "#c7eae5", "#5ab4ac", "#01665e"];
    const COLORS = specialization ? COEFFICIENT_COLORS : SHARE_COLORS;
    const maxShare = Math.max(...points.map((p) => p.share), 1);

    /* Коническая проекция Альберса: привычный вид России без растяжения севера. */
    const rad = Math.PI / 180;
    const [lat1, lat2, lat0, lon0] = [52 * rad, 64 * rad, 60 * rad, 100 * rad];
    const n = (Math.sin(lat1) + Math.sin(lat2)) / 2;
    const c = Math.cos(lat1) ** 2 + 2 * n * Math.sin(lat1);
    const rho = (lat) => Math.sqrt(c - 2 * n * Math.sin(lat)) / n;
    function project(lon, lat) {
        const theta = n * (lon * rad - lon0);
        const r = rho(lat * rad);
        return L.latLng((rho(lat0) - r * Math.cos(theta)) * SCALE, r * Math.sin(theta) * SCALE);
    }

    /* Положение на шкале от 0 до 1. Коэффициент берётся в логарифме, чтобы 0,5 и 2 были симметричны относительно 1. */
    function scalePosition(point) {
        if (!specialization) return point.share / maxShare;
        return (Math.log2(Math.max(point.coefficient, 0.5)) + 1) / 2;
    }

    function colorFor(position) {
        const place = Math.min(Math.max(position, 0), 1) * (COLORS.length - 1);
        const low = Math.floor(place);
        const high = Math.min(low + 1, COLORS.length - 1);
        const channels = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
        const [a, b] = [channels(COLORS[low]), channels(COLORS[high])];
        return "rgb(" + a.map((v, i) => Math.round(v + (b[i] - v) * (place - low))).join(",") + ")";
    }

    function element(tag, text) {
        const node = document.createElement(tag);
        node.textContent = text;
        return node;
    }

    const number = (value) => value.toLocaleString("ru-RU");

    function details(point) {
        const box = document.createElement("div");
        box.append(element("strong", point.city));
        box.append(element("div", "Вакансий: " + number(point.count)));
        if (specialization) {
            box.append(element("div", "Среди вакансий города: " + number(point.share) + "%"));
            box.append(element("div", "Коэффициент специализации: " + number(point.coefficient)));
        } else {
            box.append(element("div", "Доля от всех вакансий: " + number(point.share) + "%"));
        }
        return box;
    }

    const map = L.map(container, { crs: L.CRS.Simple, minZoom: -4, maxZoom: 3, zoomSnap: 0.25,
        scrollWheelZoom: false, attributionControl: false });
    map.fitBounds(L.latLngBounds(points.map((p) => project(p.lon, p.lat))).pad(0.4));

    points.forEach((point) => {
        L.circleMarker(project(point.lon, point.lat), { radius: 10, weight: 1.5, color: "#203344",
            fillColor: point.count ? colorFor(scalePosition(point)) : "#c5ccd3", fillOpacity: 1 })
            .bindTooltip(details(point), { direction: "top", offset: [0, -8] }).addTo(map);
    });

    const legend = L.control({ position: "bottomleft" });
    legend.onAdd = () => {
        const box = L.DomUtil.create("div", "map-legend");
        box.append(element("div", specialization ? "Коэффициент специализации" : "Доля от всех вакансий, %"));
        const bar = element("div", "");
        bar.className = "map-legend-bar";
        bar.style.background = "linear-gradient(to right," + COLORS.join(",") + ")";
        box.append(bar);
        const scale = element("div", "");
        scale.className = "map-legend-scale";
        const labels = specialization ? ["≤0,5", "1", "≥2"] : ["0", number(Math.round(maxShare))];
        labels.forEach((label) => scale.append(element("span", label)));
        box.append(scale);
        return box;
    };
    legend.addTo(map);

    fetch(container.dataset.outline).then((response) => response.json()).then((outline) => {
        const shape = L.geoJSON(outline, { interactive: false, coordsToLatLng: (coords) => project(coords[0], coords[1]),
            style: { color: "#8fa3b3", weight: 1, fillColor: "#dfe7ed", fillOpacity: 1 } }).addTo(map).bringToBack();
        map.fitBounds(shape.getBounds(), { padding: [12, 12], animate: false });
    });
})();
