/* Карта спроса: контур России и города. Цвет — доля вакансий или коэффициент специализации, размер — число вакансий. Работает без интернета. */
(function () {
    const container = document.getElementById("city-map");
    if (!container) return;
    const points = JSON.parse(document.getElementById("map-data").textContent);
    const specialization = container.dataset.mode === "specialization";
    const SCALE = 1000;
    const SHARE_COLORS = ["#cfe8f3", "#8cc5dc", "#4a9fc4", "#2a78ab", "#1c5489", "#142f66"];
    const COEFFICIENT_COLORS = ["#8c510a", "#d8b365", "#f6e8c3", "#f5f5f5", "#c7eae5", "#5ab4ac", "#01665e"];
    const COLORS = specialization ? COEFFICIENT_COLORS : SHARE_COLORS;
    const EMPTY_COLOR = "#c5ccd3";
    const maxShare = Math.max(...points.map((p) => p.share), 1);
    const maxCount = Math.max(...points.map((p) => p.count), 1);
    const radius = (count) => 9 + 6 * Math.sqrt(count / maxCount);

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

    function element(tag, text, className) {
        const node = document.createElement(tag);
        if (text !== undefined) node.textContent = text;
        if (className) node.className = className;
        return node;
    }

    const number = (value) => value.toLocaleString("ru-RU");

    function row(label, value) {
        const line = element("div", undefined, "line");
        line.append(element("span", label), element("b", value));
        return line;
    }

    function details(point, color) {
        const box = element("div", undefined, "map-card");
        box.append(element("div", point.city, "name"), element("div", number(point.count), "big"), element("div", "вакансий", "sub"));
        if (specialization) {
            box.append(row("Доля в городе", number(point.share) + "%"));
            box.append(row("Коэффициент", point.count ? number(point.coefficient) : "—"));
        } else {
            box.append(row("Доля от всех вакансий", number(point.share) + "%"));
        }
        const track = element("div", undefined, "track");
        const fill = element("div", undefined, "fill");
        fill.style.width = Math.round(Math.min(Math.max(scalePosition(point), 0.04), 1) * 100) + "%";
        fill.style.background = color;
        track.append(fill);
        box.append(track);
        return box;
    }

    const map = L.map(container, { crs: L.CRS.Simple, minZoom: -4, maxZoom: 3, zoomSnap: 0.25,
        scrollWheelZoom: false, attributionControl: false });
    map.fitBounds(L.latLngBounds(points.map((p) => project(p.lon, p.lat))).pad(0.4));

    [...points].sort((a, b) => b.count - a.count).forEach((point) => {
        const color = point.count ? colorFor(scalePosition(point)) : EMPTY_COLOR;
        const marker = L.circleMarker(project(point.lon, point.lat), { radius: radius(point.count), weight: 2,
            color: "#ffffff", fillColor: color, fillOpacity: 0.92 })
            .bindTooltip(details(point, color), { direction: "top", offset: [0, -4], className: "map-tooltip", opacity: 1 }).addTo(map);
        marker.on("mouseover", () => marker.setStyle({ weight: 4, color: "#203344" }));
        marker.on("mouseout", () => marker.setStyle({ weight: 2, color: "#ffffff" }));
    });

    const legend = L.control({ position: "bottomleft" });
    legend.onAdd = () => {
        const box = L.DomUtil.create("div", "map-legend");
        box.append(element("b", specialization ? "Коэффициент специализации" : "Доля от всех вакансий, %"));
        const bar = element("div", undefined, "map-legend-bar");
        bar.style.background = "linear-gradient(to right," + COLORS.join(",") + ")";
        box.append(bar);
        const scale = element("div", undefined, "map-legend-scale");
        const labels = specialization ? ["≤0,5", "1", "≥2"] : ["0", number(Math.round(maxShare / 2)), number(Math.round(maxShare))];
        labels.forEach((label) => scale.append(element("span", label)));
        box.append(scale);
        box.append(element("b", "Размер — число вакансий", "map-legend-title"));
        const sizes = element("div", undefined, "map-legend-sizes");
        [1000, 5000, 15000].filter((value) => value <= maxCount * 1.2).forEach((value) => {
            const item = element("div");
            const dot = element("i");
            dot.style.width = dot.style.height = 2 * radius(value) + "px";
            item.append(dot, document.createTextNode(number(value)));
            sizes.append(item);
        });
        box.append(sizes);
        return box;
    };
    legend.addTo(map);

    fetch(container.dataset.outline).then((response) => response.json()).then((outline) => {
        const shape = L.geoJSON(outline, { interactive: false, coordsToLatLng: (coords) => project(coords[0], coords[1]),
            style: { className: "country", color: "#ffffff", weight: 1.5, fillColor: "#dde6ee", fillOpacity: 1 } }).addTo(map).bringToBack();
        map.fitBounds(shape.getBounds(), { padding: [12, 12], animate: false });
    });
})();
