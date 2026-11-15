(() => {
    const button = document.getElementById("sj-more");
    if (!button) return;
    const error = document.getElementById("sj-more-error");
    const count = document.getElementById("sj-count");
    const results = document.getElementById("sj-results");
    const vacancyWord = (n) => n % 10 === 1 && n % 100 !== 11 ? "вакансию" :
        [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "вакансии" : "вакансий";
    const updateButton = () => {
        const remaining = Math.min(Number(button.dataset.total), 500) - Number(button.dataset.shown);
        const next = Math.min(20, Math.max(0, remaining));
        button.textContent = `Показать ещё ${next} ${vacancyWord(next)}`;
    };
    button.addEventListener("click", async () => {
        button.disabled = true;
        button.textContent = "Загружаем…";
        error.hidden = true;
        const params = new URLSearchParams({keyword: button.dataset.keyword, town: button.dataset.town, page: button.dataset.page});
        try {
            const response = await fetch(button.dataset.url + "?" + params, { headers: { Accept: "application/json" } });
            const data = await response.json();
            if (!response.ok || data.error) throw new Error(data.error || "Не удалось загрузить вакансии.");
            results.insertAdjacentHTML("beforeend", data.html);
            const shown = Number(button.dataset.shown) + data.added;
            button.dataset.shown = shown;
            button.dataset.total = data.total;
            button.dataset.page = data.next_page;
            count.textContent = `Найдено: ${data.total} · показано: ${shown}${data.total > 500 ? " (SuperJob позволяет просмотреть не более 500)" : ""}`;
            if (!data.has_more || !data.added) { button.remove(); return; }
        } catch (ex) {
            error.textContent = ex.message || "Не удалось загрузить вакансии. Попробуйте ещё раз.";
            error.hidden = false;
        }
        button.disabled = false;
        updateButton();
    });
})();
