"""Графики matplotlib для браузера, PDF и оконного клиента."""
from matplotlib.figure import Figure

COORDINATES = {"Владивосток": (131.89, 43.12), "Москва": (37.62, 55.75), "Санкт-Петербург": (30.32, 59.94),
               "Казань": (49.11, 55.8), "Нижний Новгород": (44.0, 56.3),
               "Екатеринбург": (60.6, 56.84), "Новосибирск": (82.92, 55.03),
               "Краснодар": (38.98, 45.04), "Ростов-на-Дону": (39.72, 47.23),
               "Самара": (50.1, 53.2), "Красноярск": (92.87, 56.01),
               "Воронеж": (39.2, 51.67), "Уфа": (55.97, 54.74),
               "Челябинск": (61.4, 55.16), "Пермь": (56.25, 58.01),
               "Омск": (73.37, 54.99), "Волгоград": (44.52, 48.71)}

def make_chart(rows: list[dict], kind: str = "vacancies") -> Figure:
    """Построить сравнительный график или схему расположения городов."""
    figure = Figure(figsize=(10, 5.5), layout="constrained", facecolor="white")
    ax = figure.subplots()
    if not rows:
        ax.text(.5, .5, "Нет данных для выбранных фильтров", ha="center")
        ax.axis("off")
        return figure
    if kind == "map":
        points = [r for r in rows if r["city"] in COORDINATES]
        if points:
            x, y = zip(*(COORDINATES[r["city"]] for r in points))
            dots = ax.scatter(x, y, c=[r["indicator"] for r in points], s=160, cmap="YlGnBu", vmin=0, vmax=100)
            for r, lon, lat in zip(points, x, y):
                ax.annotate(r["city"], (lon, lat), xytext=(4, 8), textcoords="offset points", fontsize=8)
            figure.colorbar(dots, ax=ax, label="Индекс спроса, 0–100")
        ax.set(xlabel="Долгота", ylabel="Широта", title="Города России — координатная схема")
        ax.text(.01, .01, "Без географических границ; города без координат не показаны", transform=ax.transAxes, fontsize=8)
    else:
        field, title = {"vacancies": ("count", "Число вакансий"),
                        "salary": ("salary", "Медианная предлагаемая зарплата, руб./месяц"),
                        "responses": ("responses", "Среднее число откликов на вакансию"),
                        "remote": ("remote", "Доля вакансий с удалённой работой, %"),
                        "indicator": ("indicator", "Относительный индекс спроса, 0–100")}[kind]
        valid = [r for r in rows if r[field] is not None]
        if len(valid) > 20:
            valid = sorted(valid, key=lambda r: r[field], reverse=True)[:20]
            title += " — первые 20 городов по значению"
        ax.barh([r["city"] for r in valid], [r[field] for r in valid], color="#247b92")
        ax.set_title(title)
        ax.invert_yaxis()
        if not valid:
            ax.text(.5, .5, "Значения отсутствуют", ha="center")
    ax.grid(axis="x", alpha=.2)
    return figure
