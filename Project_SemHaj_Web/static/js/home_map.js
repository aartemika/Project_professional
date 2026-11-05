/* Карта главной: нажатие на город раскрывает карточку с короткими фактами. Работает без интернета. */
(function () {
    const container = document.getElementById("city-map");
    if (!container) return;
    const points = JSON.parse(document.getElementById("map-data").textContent);
    const panel = document.getElementById("city-panel");
    const specialization = container.dataset.mode === "specialization";
    const SCALE = 1000;
    const SHARE_COLORS = ["#cfe8f3", "#8cc5dc", "#4a9fc4", "#2a78ab", "#1c5489", "#142f66"];
    const COEFFICIENT_COLORS = ["#8c510a", "#d8b365", "#f6e8c3", "#f5f5f5", "#c7eae5", "#5ab4ac", "#01665e"];
    const COLORS = specialization ? COEFFICIENT_COLORS : SHARE_COLORS;
    const maxShare = Math.max(...points.map((p) => p.share), 1);
    const maxCount = Math.max(...points.map((p) => p.count), 1);
    const radius = (count) => 9 + 6 * Math.sqrt(count / maxCount);
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
    const position = (p) => specialization ? (Math.log2(Math.max(p.coefficient, 0.5)) + 1) / 2 : p.share / maxShare;
    function colorFor(pos) {
        const place = Math.min(Math.max(pos, 0), 1) * (COLORS.length - 1);
        const low = Math.floor(place), high = Math.min(low + 1, COLORS.length - 1);
        const ch = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
        const [a, b] = [ch(COLORS[low]), ch(COLORS[high])];
        return "rgb(" + a.map((v, i) => Math.round(v + (b[i] - v) * (place - low))).join(",") + ")";
    }
    const el = (tag, text, cls) => { const x = document.createElement(tag); if (text !== undefined) x.textContent = text; if (cls) x.className = cls; return x; };

    function stat(label, value) {
        const box = el("div");
        box.append(el("span", label), el("b", value));
        return box;
    }

    function factList(title, items) {
        if (!items.length) return [];
        const list = el("ul", undefined, "sc-facts");
        items.forEach(([main, note]) => {
            const li = el("li", main);
            li.append(el("small", note));
            list.append(li);
        });
        return [el("h4", title), list];
    }

    function showCity(point) {
        panel.replaceChildren(el("h3", point.city));
        if (point.badge) panel.append(el("span", point.badge, "sc-badge"));
        const stats = el("div", undefined, "sc-panel-stats");
        stats.append(stat(specialization ? "Вакансий по профессии" : "Вакансий", point.vacancies.replace(/\s\S+$/, "")));
        if (point.typical) stats.append(stat("Обычная зарплата", point.typical));
        panel.append(stats);
        panel.append(...factList("Чаще других ищут", point.famous.map((i) => [i.category, i.share + " вакансий города, в среднем " + i.average])));
        panel.append(...factList("Лучше всего платят", point.paid.map((i) => [i.category, "обычно " + i.salary + ", у лучших предложений от " + i.top])));
        const actions = el("div", undefined, "sc-panel-actions");
        const pick = el("a", "Подобрать город", "sc-btn-small");
        pick.href = "/navigator";
        const compare = el("a", "Сравнить с другим городом", "sc-btn-small sc-btn-small-ghost");
        compare.href = "/navigator?mode=overview&a=" + encodeURIComponent(point.city);
        actions.append(pick, compare);
        panel.append(actions);
    }

    const map = L.map(container, { crs: L.CRS.Simple, minZoom: -4, maxZoom: 3, zoomSnap: 0.25, scrollWheelZoom: false, attributionControl: false });
    map.fitBounds(L.latLngBounds(points.map((p) => project(p.lon, p.lat))).pad(0.4));
    let selected = null;
    const select = (marker, point) => {
        if (selected) selected.setStyle({ weight: 2, color: "#ffffff" });
        selected = marker;
        marker.setStyle({ weight: 4, color: "#203344" });
        showCity(point);
    };
    const markers = [...points].sort((a, b) => b.count - a.count).map((point) => {
        const color = point.count ? colorFor(position(point)) : "#c5ccd3";
        const marker = L.circleMarker(project(point.lon, point.lat), { radius: radius(point.count), weight: 2, color: "#ffffff", fillColor: color, fillOpacity: 0.92 })
            .bindTooltip(point.city, { direction: "top", offset: [0, -4], className: "map-tooltip", opacity: 1 }).addTo(map);
        marker.on("click", () => select(marker, point));
        return [marker, point];
    });
    const legend = L.control({ position: "bottomleft" });
    legend.onAdd = () => {
        const box = L.DomUtil.create("div", "map-legend");
        box.append(el("b", specialization ? "Насколько чаще ищут эту профессию" : "Доля города на рынке труда"));
        const bar = el("div", undefined, "map-legend-bar");
        bar.style.background = "linear-gradient(to right," + COLORS.join(",") + ")";
        box.append(bar);
        const scale = el("div", undefined, "map-legend-scale");
        (specialization ? ["реже", "как везде", "чаще"] : ["меньше", "", "больше"]).forEach((t) => scale.append(el("span", t)));
        box.append(scale, el("b", "Размер круга — число вакансий", "map-legend-title"));
        return box;
    };
    legend.addTo(map);
    fetch(container.dataset.outline).then((r) => r.json()).then((outline) => {
        const shape = L.geoJSON(outline, { interactive: false, coordsToLatLng: (co) => project(co[0], co[1]),
            style: { className: "country", color: "#ffffff", weight: 1.5, fillColor: "#dde6ee", fillOpacity: 1 } }).addTo(map).bringToBack();
        map.fitBounds(shape.getBounds(), { padding: [12, 12], animate: false });
    });
    if (markers.length) showCity(markers[0][1]);
})();
