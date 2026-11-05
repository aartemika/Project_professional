/* Подбор города: свои данные и оценки важности, рейтинг городов, вывод и сравнение. */
(function () {
    const $ = (id) => document.getElementById(id);
    let data = JSON.parse($("rating-data").textContent);
    const profiles = JSON.parse($("profiles-data").textContent);
    const params = new URLSearchParams(location.search);
    const MIN_RELIABLE = 30;
    const SALARY_WEIGHT = 10;
    const COLORS = { salary: "#2a9d8f", count: "#12627c", competition: "#e9806e", remote: "#f2c14e" };

    const TEXT = {
        seeker: {
            inputs: "Ваши данные",
            salaryLabel: "Какую зарплату вы хотите",
            rangeLabel: "Допуск",
            rangeHint: "Вакансии чуть ниже желаемой зарплаты учитываются наполовину",
            experienceLabel: "Ваш опыт",
            title: "Рейтинг городов для соискателя",
            labels: { count: "Много вакансий", competition: "Мало соперников на место", remote: "Удалённая работа" },
            hints: { count: "Шире выбор, из чего выбирать", competition: "На вакансию откликается меньше людей", remote: "Можно работать из дома" },
            direction: { count: 1, competition: -1, remote: 1 },
            good: { count: "много вакансий", competition: "на вакансию откликается меньше людей", remote: "много удалённой работы" },
            bad: { count: "вакансий немного", competition: "на вакансию откликается много людей", remote: "удалённой работы мало" },
            salaryRule: "Вакансии от вашей зарплаты считаются полностью, вакансии в пределах допуска ниже неё считаются наполовину",
        },
        business: {
            inputs: "Что вы предлагаете",
            salaryLabel: "Сколько вы готовы платить",
            rangeLabel: "Диапазон",
            rangeHint: "Шире диапазон, больше похожих вакансий для сравнения",
            experienceLabel: "Какой опыт нужен",
            title: "Рейтинг городов для бизнеса",
            labels: { count: "Мало других работодателей", competition: "Много откликов на вакансию", remote: "Можно нанять удалённо" },
            hints: { count: "Меньше вакансий, меньше борьбы за людей", competition: "Больше кандидатов на одно место", remote: "Много удалённых вакансий в этой сфере" },
            direction: { count: -1, competition: 1, remote: 1 },
            good: { count: "вакансий меньше, другие работодатели слабее борются за людей", competition: "на вакансию откликается много людей", remote: "удалённая работа здесь распространена" },
            bad: { count: "вакансий много, работодатели борются за тех же людей", competition: "откликов на вакансию немного", remote: "удалённая работа здесь редкость" },
            salaryRule: "Вакансии, которые платят не больше вашей суммы, считаются полностью, вакансии в пределах диапазона выше неё считаются наполовину",
        },
    };

    const state = {
        mode: ["seeker", "business", "overview"].includes(params.get("mode")) ? params.get("mode") : "seeker",
        view: params.get("view") === "profession" ? "profession" : "city",
        experience: $("experience").value,
        salary: { seeker: null, business: null },
        edited: { seeker: false, business: false },
        range: { seeker: 10000, business: 30000 },
        weights: { seeker: { count: 5, competition: 5, remote: 3 }, business: { count: 5, competition: 5, remote: 3 } },
        checked: {},
        compareOpen: false,
    };

    const escapeHtml = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c]));
    const number = (n) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    const money = (n) => number(n) + " ₽";
    const decimal = (n) => String(Number(n.toFixed(1))).replace(".", ",");
    const byCity = () => Object.fromEntries(data.map((d) => [d.city, d]));
    const reliable = (d) => d.count >= MIN_RELIABLE;
    const competitionWord = (i) => i === null || i === undefined ? "нет данных" : i >= 150 ? "очень высокая" : i >= 120 ? "высокая" : i <= 80 ? "низкая" : "средняя";
    const isRanking = () => state.mode !== "overview";

    function plural(n, one, few, many) {
        const tail = n % 100, last = n % 10;
        return number(n) + " " + (tail >= 11 && tail <= 14 ? many : last === 1 ? one : last >= 2 && last <= 4 ? few : many);
    }

    const percent = (value) => decimal(value) + "%";

    /* Доля вакансий города по таблице процентилей зарплат. */
    const below = (d, x) => d.distribution.filter((v) => v < x).length / d.distribution.length;
    const upTo = (d, x) => d.distribution.filter((v) => v <= x).length / d.distribution.length;

    function salaryFit(d) {
        const salary = state.salary[state.mode], range = state.range[state.mode];
        if (!salary || !d.distribution.length) return null;
        let full, half;
        if (state.mode === "seeker") {
            full = 1 - below(d, salary);
            half = below(d, salary) - below(d, salary - range);
        } else {
            full = upTo(d, salary);
            half = upTo(d, salary + range) - upTo(d, salary);
        }
        const near = Math.round((upTo(d, salary + range) - below(d, salary - range)) * d.salary_count);
        return { value: full + half / 2, percent: Math.round(full * 100), near };
    }

    /* Шкалу задают города с достаточным числом вакансий: иначе случайные цифры по 3–4 вакансиям исказят её для всех. */
    function scale(key) {
        const known = (rows) => rows.map((d) => d[key]).filter((v) => v !== null && v !== undefined);
        const values = known(data.filter(reliable)).length ? known(data.filter(reliable)) : known(data);
        const low = Math.min(...values), high = Math.max(...values);
        return (v) => v === null || v === undefined || high === low ? 0.5 : Math.min(Math.max((v - low) / (high - low), 0), 1);
    }

    function rating() {
        const text = TEXT[state.mode], weights = state.weights[state.mode];
        const scales = { count: scale("count"), competition: scale("competition"), remote: scale("remote") };
        const useSalary = Boolean(state.salary[state.mode]);
        const total = Object.values(weights).reduce((sum, w) => sum + w, 0) + (useSalary ? SALARY_WEIGHT : 0);
        return data.map((d) => {
            const parts = {};
            let score = 0;
            Object.keys(weights).forEach((key) => {
                let v = scales[key](d[key]);
                if (text.direction[key] < 0) v = 1 - v;
                score += weights[key] * v;
                parts[key] = { v, points: total ? 100 * weights[key] * v / total : 0 };
            });
            const fit = salaryFit(d);
            if (useSalary) {
                const v = fit ? fit.value : 0;
                score += SALARY_WEIGHT * v;
                parts.salary = { v, points: total ? 100 * SALARY_WEIGHT * v / total : 0 };
            }
            return { d, fit, parts, score: total ? 100 * score / total : 0 };
        }).sort((a, b) => Number(reliable(b.d)) - Number(reliable(a.d)) || b.score - a.score);
    }

    function salarySentence(x) {
        const salary = money(state.salary[state.mode]);
        if (!x.fit) return { good: "", bad: "по зарплате мало данных" };
        const p = x.fit.percent;
        if (state.mode === "seeker") return { good: p + "% вакансий платят от " + salary, bad: "от " + salary + " платят только " + p + "% вакансий" };
        return { good: "ваша зарплата не ниже, чем в " + p + "% вакансий", bad: "ваша зарплата не ниже только чем в " + p + "% вакансий" };
    }

    function reasons(x) {
        const text = TEXT[state.mode], weights = state.weights[state.mode];
        const keys = Object.keys(weights).filter((k) => weights[k] > 0);
        const pro = keys.filter((k) => x.parts[k].v >= 0.6).sort((a, b) => x.parts[b].points - x.parts[a].points).slice(0, 2).map((k) => text.good[k]);
        const con = keys.filter((k) => x.parts[k].v <= 0.35).sort((a, b) => weights[b] * (1 - x.parts[b].v) - weights[a] * (1 - x.parts[a].v)).slice(0, 2).map((k) => text.bad[k]);
        if (state.salary[state.mode]) {
            const sentence = salarySentence(x);
            if (x.fit && x.fit.value >= 0.45) pro.unshift(sentence.good);
            else if (x.fit && x.fit.value < 0.3) con.unshift(sentence.bad);
            if (!x.fit) con.unshift(sentence.bad);
            if (x.fit && x.fit.near < 10) con.push("похожих вакансий мало, оценка приблизительная");
        }
        return { pro, con };
    }

    function renderVerdict(rows) {
        const box = $("verdict");
        const weights = state.weights[state.mode];
        const empty = !state.salary[state.mode] && Object.values(weights).every((w) => !w);
        if (empty) {
            box.innerHTML = "<div class=\"nv-verdict nv-verdict-plain\"><b>Укажите зарплату или оцените хотя бы один пункт</b></div>";
            return;
        }
        if (!rows.length || !reliable(rows[0].d)) {
            box.innerHTML = "<div class=\"nv-verdict nv-verdict-plain\"><b>По этим условиям мало вакансий</b><p class=\"nv-hint\">Выберите другую профессию или другой опыт: для вывода нужно хотя бы " + MIN_RELIABLE + " вакансий в городе.</p></div>";
            return;
        }
        const top = rows[0], why = reasons(top), second = rows[1];
        const score = Math.round(top.score);
        const list = (title, items) => "<div><h4>" + title + "</h4>" + (items.length ? "<ul>" + items.map((t) => "<li>" + escapeHtml(t) + "</li>").join("") + "</ul>" : "<ul><li>ничего заметного</li></ul>") + "</div>";
        let note = "";
        if (second && reliable(second.d)) {
            const gap = top.score - second.score;
            note = "<p class=\"nv-verdict-note\">Следом идёт " + escapeHtml(second.d.city) + " (" + Math.round(second.score) + " из 100)" + (gap < 5 ? ": города очень близки, сравните их подробнее." : ".") + "</p>";
        }
        box.innerHTML = "<div class=\"nv-verdict\"><div class=\"nv-verdict-main\"><div class=\"nv-ring\" style=\"--p:" + score + "\"><div><b>" + score + "</b><span>из 100</span></div></div>" +
            "<div class=\"nv-verdict-city\"><span>Лучше всего подходит</span><b>" + escapeHtml(top.d.city) + "</b></div></div>" +
            list("Почему", why.pro) + list("Что учесть", why.con) + note + "</div>";
    }

    function legend() {
        const text = TEXT[state.mode], weights = state.weights[state.mode];
        const items = [];
        if (state.salary[state.mode]) items.push(["salary", "Зарплата"]);
        Object.keys(weights).filter((k) => weights[k] > 0).forEach((k) => items.push([k, text.labels[k]]));
        return "<div class=\"nv-legend\">" + items.map(([k, label]) => "<span><i style=\"background:" + COLORS[k] + "\"></i>" + label + "</span>").join("") + "</div>";
    }

    function fitLine(x) {
        if (!state.salary[state.mode] || !x.fit) return "";
        return (state.mode === "seeker" ? x.fit.percent + "% вакансий от " + money(state.salary.seeker) : "ваша зарплата не ниже, чем в " + x.fit.percent + "% вакансий") + " · ";
    }

    function renderRanking() {
        const rows = rating();
        renderVerdict(rows);
        $("rank-title").textContent = TEXT[state.mode].title;
        if (!rows.length) {
            $("ranking").innerHTML = "<p class=\"nv-hint\">Нет вакансий по этим условиям.</p>";
            updateCompareButton();
            return;
        }
        let html = legend() + "<ol class=\"rank\">";
        rows.forEach((x, i) => {
            const d = x.d;
            const stack = Object.keys(x.parts).filter((k) => x.parts[k].points > 0).sort().map((k) => "<i style=\"width:" + x.parts[k].points + "%;background:" + COLORS[k] + "\"></i>").join("");
            const low = reliable(d) ? "" : "<small class=\"nv-low\">мало данных</small>";
            const salary = d.salary ? "обычно " + money(d.salary) : "зарплата неизвестна";
            html += "<li class=\"" + (i === 0 && reliable(d) ? "top" : "") + "\"><div class=\"rank-head\"><input type=\"checkbox\" aria-label=\"Сравнить\" data-city=\"" + escapeHtml(d.city) + "\"" + (state.checked[d.city] ? " checked" : "") + "><span class=\"place\">" + (i + 1) + "</span><b>" + escapeHtml(d.city) + "</b>" + low + "<span class=\"score\">" + Math.round(x.score) + " из 100</span></div>" +
                "<div class=\"nv-stack\">" + stack + "</div><small>" + fitLine(x) + salary + " · " + plural(d.count, "вакансия", "вакансии", "вакансий") + " · ≈ " + plural(d.week || 0, "отклик", "отклика", "откликов") + " в неделю на вакансию · удалённо " + String(d.remote).replace(".", ",") + "%</small></li>";
        });
        $("ranking").innerHTML = html + "</ol>";
        $("ranking").querySelectorAll("input[type=checkbox]").forEach((box) => box.addEventListener("change", () => {
            if (box.checked && selected().length >= 3) { box.checked = false; return; }
            state.checked[box.dataset.city] = box.checked;
            updateCompareButton();
        }));
        $("how-text").textContent = TEXT[state.mode].salaryRule + ". Так получается доля подходящих вакансий в городе. Остальные показатели сравниваются между городами: лучший получает максимум, худший ноль. Затем всё складывается с учётом ваших оценок, зарплата считается самым важным. Оценка показывает, насколько город подходит под ваши условия среди этих городов. Это не прогноз и не оценка самого города.";
        updateCompareButton();
    }

    function selected() {
        const cities = byCity();
        return Object.keys(state.checked).filter((c) => state.checked[c] && cities[c]);
    }

    function updateCompareButton() {
        const n = selected().length, button = $("compare-btn");
        button.disabled = n < 2;
        button.textContent = n < 2 ? "Отметьте 2–3 города" : "Сравнить выбранные (" + n + ")";
    }

    function winners(cities, rows) {
        const result = {};
        if (cities.length < 2 || !isRanking()) return result;
        const info = byCity(), weights = state.weights[state.mode], direction = TEXT[state.mode].direction;
        Object.keys(weights).filter((k) => weights[k] > 0).forEach((k) => {
            const values = cities.map((c) => info[c][k]);
            if (values.some((v) => v === null || v === undefined)) return;
            const best = direction[k] > 0 ? Math.max(...values) : Math.min(...values);
            if (values.filter((v) => v === best).length === 1) result[k] = cities[values.indexOf(best)];
        });
        const fits = cities.map((c) => rows.find((x) => x.d.city === c).fit);
        if (fits.every(Boolean)) {
            const best = Math.max(...fits.map((f) => f.value));
            if (fits.filter((f) => f.value === best).length === 1) result.salary = cities[fits.findIndex((f) => f.value === best)];
        }
        return result;
    }

    function card(city, win, x) {
        const d = byCity()[city], p = profiles[city] || { famous: [], paid: [] };
        const stat = (key, label, value) => "<div class=\"nv-stat" + (win[key] === city ? " win" : "") + "\"><span>" + label + "</span><b>" + value + "</b></div>";
        let html = "<article class=\"nv-card\"><h3>" + escapeHtml(city) + "</h3><div class=\"nv-stats\">";
        html += stat("salary", "Обычная зарплата", d.salary ? money(d.salary) : "нет данных");
        html += stat("competition", "Конкуренция за место", competitionWord(d.competition));
        html += stat("count", "Вакансий", number(d.count));
        html += stat("remote", "Удалённо", String(d.remote).replace(".", ",") + "%");
        html += "</div>";
        if (!reliable(d)) html += "<p class=\"nv-low-note\">По этим условиям в городе меньше " + MIN_RELIABLE + " вакансий, цифры приблизительные.</p>";
        if (x) {
            if (x.fit) html += "<p class=\"nv-hint\">" + escapeHtml(fitLine(x).replace(" · ", "")) + "</p>";
            html += "<p class=\"nv-hint\">Подходит под ваши условия на <b>" + Math.round(x.score) + " из 100</b></p>";
        }
        html += "<h4>Чаще других ищут</h4><ul>" + (p.famous.length ? p.famous.map((i) => "<li><span>" + escapeHtml(i.category) + "</span><b>" + i.share + "<small>в среднем " + i.average + "</small></b></li>").join("") : "<li>ничего заметного</li>") + "</ul>";
        html += "<h4>Лучше всего платят</h4><ul>" + (p.paid.length ? p.paid.map((i) => "<li><span>" + escapeHtml(i.category) + "</span><b>обычно " + money(i.salary) + "<small>от " + money(i.top) + " у лучших</small></b></li>").join("") : "<li>нет данных</li>") + "</ul></article>";
        return html;
    }

    function renderCompare() {
        const list = selected(), box = $("compare-box");
        if (list.length < 2 || !state.compareOpen) { box.hidden = true; return; }
        const rows = rating(), win = winners(list, rows);
        const row = (c) => rows.find((x) => x.d.city === c);
        $("compare-cards").innerHTML = list.map((c) => card(c, win, row(c))).join("");
        const order = list.slice().sort((a, b) => row(b).score - row(a).score), lead = order[0];
        const text = TEXT[state.mode];
        const names = Object.keys(win).filter((k) => win[k] === lead).map((k) => k === "salary" ? "зарплата" : text.labels[k].toLowerCase());
        const gap = row(lead).score - row(order[1]).score;
        $("compare-verdict").innerHTML = "<div class=\"nv-compare-note\"><b>По вашим условиям лучше подходит " + escapeHtml(lead) + "</b>" + (gap < 5 ? "Разница небольшая, города очень близки. " : "") + (names.length ? "Сильнее по пунктам: " + names.join(", ") + "." : "Перевес даёт сочетание показателей.") + "</div>";
        box.hidden = false;
    }

    function renderWeights() {
        const text = TEXT[state.mode], weights = state.weights[state.mode], box = $("weights-grid");
        box.innerHTML = Object.keys(weights).map((k) => "<div class=\"nv-weight\"><label for=\"w-" + k + "\">" + text.labels[k] + " <b id=\"v-" + k + "\">" + weights[k] + " из 10</b></label><input id=\"w-" + k + "\" type=\"range\" min=\"0\" max=\"10\" step=\"1\" value=\"" + weights[k] + "\" data-k=\"" + k + "\"><div class=\"nv-scale\"><span>не важно</span><span>очень важно</span></div><small>" + text.hints[k] + "</small></div>").join("");
        box.querySelectorAll("input").forEach((input) => input.addEventListener("input", () => {
            weights[input.dataset.k] = Number(input.value);
            $("v-" + input.dataset.k).textContent = input.value + " из 10";
            renderRanking();
            renderCompare();
        }));
    }

    function typicalSalary() {
        const values = data.filter(reliable).map((d) => d.salary).filter(Boolean).sort((a, b) => a - b);
        return values.length ? values[Math.floor(values.length / 2)] : null;
    }

    function renderInputs() {
        const ranking = isRanking();
        document.querySelectorAll("[data-rank-only]").forEach((el) => { el.hidden = !ranking; });
        if (!ranking) {
            $("inputs-title").textContent = "Что посмотреть";
            return;
        }
        const text = TEXT[state.mode];
        $("inputs-title").textContent = text.inputs;
        $("salary-label").textContent = text.salaryLabel;
        $("range-label").textContent = text.rangeLabel;
        $("range-hint").textContent = text.rangeHint;
        $("experience-label").textContent = text.experienceLabel;
        if (state.salary[state.mode] === null) {
            const typical = typicalSalary();
            state.salary[state.mode] = typical ? Math.round(typical / 5000) * 5000 : 0;
        }
        $("salary").value = state.salary[state.mode] || "";
        $("range").value = String(state.range[state.mode]);
        const medians = data.filter(reliable).map((d) => d.salary).filter(Boolean);
        $("salary-hint").textContent = medians.length ? "Обычно в этих городах от " + money(Math.round(Math.min(...medians) / 1000) * 1000) + " до " + money(Math.round(Math.max(...medians) / 1000) * 1000) : "";
    }

    function fillCitySelects() {
        const sorted = data.slice().sort((x, y) => y.count - x.count);
        const a = $("city-a"), b = $("city-b"), keepA = a.value || params.get("a"), keepB = b.value || params.get("b");
        const options = sorted.map((d) => "<option>" + escapeHtml(d.city) + "</option>").join("");
        a.innerHTML = options;
        b.innerHTML = "<option value=\"\">Без сравнения</option>" + options;
        const info = byCity();
        if (keepA && info[keepA]) a.value = keepA;
        b.value = keepB && info[keepB] && keepB !== a.value ? keepB : "";
    }

    function renderOverview() {
        const a = $("city-a").value, b = $("city-b").value;
        const list = a ? (b && b !== a ? [a, b] : [a]) : [];
        $("overview-cards").innerHTML = list.length ? list.map((c) => card(c, {})).join("") : "<p class=\"nv-hint\">Нет вакансий по этим условиям.</p>";
    }

    function renderProfession() {
        const category = $("category").value;
        $("prof-title").textContent = category || "Выберите профессию";
        if (!category) {
            $("prof-note").textContent = "Выберите профессию в списке выше, и сайт покажет, в каких городах её ищут чаще.";
            $("prof-insights").innerHTML = "";
            $("prof-table").innerHTML = "";
            return;
        }
        $("prof-note").textContent = "Города идут от тех, где у этой профессии самая большая доля среди вакансий, к тем, где самая маленькая.";
        const rows = data.slice().sort((x, y) => Number(reliable(y)) - Number(reliable(x)) || (y.coefficient || 0) - (x.coefficient || 0));
        const best = (key) => data.filter((d) => d[key] !== null && reliable(d)).sort((x, y) => y[key] - x[key])[0];
        const insights = [], most = best("count"), paid = best("salary"), first = rows[0];
        if (most) insights.push("Больше всего вакансий: <b>" + escapeHtml(most.city) + "</b> (" + number(most.count) + ").");
        if (first && reliable(first)) insights.push("Чаще всего ищут в городе <b>" + escapeHtml(first.city) + "</b>: " + percent(first.share) + " вакансий города, в среднем по городам " + percent(first.share / first.coefficient) + ".");
        if (paid) insights.push("Выше всего зарплаты: <b>" + escapeHtml(paid.city) + "</b>, обычно " + money(paid.salary) + ".");
        $("prof-insights").innerHTML = insights.map((t) => "<li>" + t + "</li>").join("");
        let html = "<thead><tr><th>Город</th><th>Вакансий</th><th>Доля среди вакансий города</th><th>Обычная зарплата</th><th>Откликов в неделю на вакансию</th></tr></thead><tbody>";
        rows.forEach((d) => {
            html += "<tr><td><b>" + escapeHtml(d.city) + "</b>" + (reliable(d) ? "" : "<small class=\"nv-low\">мало данных</small>") + "</td><td>" + number(d.count) + "</td><td>" + percent(d.share) + "<div class=\"comp-bar\"><i style=\"width:" + Math.min(100, (d.coefficient || 0) / 3 * 100) + "%\"></i></div></td><td>" + (d.salary ? money(d.salary) : "нет данных") + "</td><td>≈ " + number(d.week || 0) + "</td></tr>";
        });
        $("prof-table").innerHTML = html + "</tbody>";
    }

    function setView(view) {
        state.view = view;
        document.querySelectorAll("#views button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
        $("prof-box").hidden = view !== "profession";
        $("city-box").hidden = view !== "city";
        fillCitySelects();
        if (view === "profession") renderProfession(); else renderOverview();
    }

    function render() {
        document.querySelectorAll("#modes button").forEach((b) => b.classList.toggle("active", b.dataset.mode === state.mode));
        $("overview-box").hidden = isRanking();
        $("rank-box").hidden = !isRanking();
        renderInputs();
        if (isRanking()) {
            renderWeights();
            renderRanking();
            renderCompare();
        } else {
            setView(state.view);
        }
    }

    function remember() {
        const query = new URLSearchParams();
        if ($("category").value) query.set("category", $("category").value);
        query.set("mode", state.mode);
        if (isRanking() && state.experience) query.set("experience", state.experience);
        if (!isRanking()) {
            query.set("view", state.view);
            if ($("city-a").value) query.set("a", $("city-a").value);
            if ($("city-b").value) query.set("b", $("city-b").value);
        }
        history.replaceState(null, "", "?" + query.toString());
    }

    /* Загрузить показатели городов под выбранные профессию и опыт, не теряя настройки. */
    async function reload() {
        const query = new URLSearchParams();
        if ($("category").value) query.set("category", $("category").value);
        if (isRanking() && state.experience) query.set("experience", state.experience);
        try {
            const response = await fetch("/navigator/data?" + query.toString(), { headers: { Accept: "application/json" } });
            if (!response.ok || response.redirected) throw new Error("Нет ответа");
            data = await response.json();
        } catch (error) {
            location.reload();
            return;
        }
        ["seeker", "business"].forEach((mode) => { if (!state.edited[mode]) state.salary[mode] = null; });
        render();
        remember();
    }

    $("modes").addEventListener("click", (e) => {
        const button = e.target.closest("button");
        if (!button || button.dataset.mode === state.mode) return;
        const hadExperience = isRanking() && state.experience;
        const wasOverview = !isRanking();
        state.mode = button.dataset.mode;
        state.compareOpen = false;
        if ((hadExperience && !isRanking()) || (wasOverview && state.experience)) reload();
        else { render(); remember(); }
    });
    $("views").addEventListener("click", (e) => {
        const button = e.target.closest("button");
        if (button) { setView(button.dataset.view); remember(); }
    });
    $("category").addEventListener("change", reload);
    $("experience").addEventListener("change", () => { state.experience = $("experience").value; reload(); });
    $("salary").addEventListener("input", () => {
        state.edited[state.mode] = true;
        state.salary[state.mode] = Number($("salary").value) || 0;
        renderRanking();
        renderCompare();
    });
    $("range").addEventListener("change", () => {
        state.range[state.mode] = Number($("range").value);
        renderRanking();
        renderCompare();
    });
    $("city-a").addEventListener("change", () => {
        if ($("city-b").value === $("city-a").value) $("city-b").value = "";
        renderOverview();
        remember();
    });
    $("city-b").addEventListener("change", () => { renderOverview(); remember(); });
    $("compare-btn").addEventListener("click", () => {
        state.compareOpen = true;
        renderCompare();
        $("compare-box").scrollIntoView({ behavior: "smooth" });
    });
    render();
})();
