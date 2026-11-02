"""Графики matplotlib для браузера, PDF и оконного клиента."""
import matplotlib
from matplotlib.axes import Axes
from matplotlib.figure import Figure

matplotlib.rcParams["font.sans-serif"] = ["Segoe UI", "DejaVu Sans"]
INK, MUTED, ACCENT, PALE = "#203344", "#647483", "#176b83", "#c9d6df"

COORDINATES = {"Владивосток": (131.89, 43.12), "Москва": (37.62, 55.75), "Санкт-Петербург": (30.32, 59.94),
               "Казань": (49.11, 55.8), "Нижний Новгород": (44.0, 56.3),
               "Екатеринбург": (60.6, 56.84), "Новосибирск": (82.92, 55.03),
               "Краснодар": (38.98, 45.04), "Ростов-на-Дону": (39.72, 47.23),
               "Самара": (50.1, 53.2), "Красноярск": (92.87, 56.01),
               "Воронеж": (39.2, 51.67), "Уфа": (55.97, 54.74),
               "Челябинск": (61.4, 55.16), "Пермь": (56.25, 58.01),
               "Омск": (73.37, 54.99), "Волгоград": (44.52, 48.71)}

def format_value(value: float, kind: str) -> str:
    """Записать значение по-русски: пробел в тысячах, запятая в дробях."""
    if kind in {"vacancies", "salary"}:
        return f"{value:,.0f}".replace(",", " ")
    text = f"{value:,.1f}".replace(",", " ").replace(".", ",")
    return text + "%" if kind == "remote" else text

def draw_bars(ax: Axes, valid: list[dict], field: str, kind: str, title: str) -> None:
    """Нарисовать упорядоченные полоски с выделенным лидером и линией среднего."""
    data = sorted(valid, key=lambda r: r[field])
    values = [r[field] for r in data]
    top = max(max(values), 1)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, labelcolor=INK, labelsize=11)
    ax.set_xticks([])
    ax.set_yticks(range(len(data)), [r["city"] for r in data])
    ax.set_xlim(-top * .01, top * 1.17)
    ax.set_ylim(-.7, len(data) - .3)
    ax.set_title(title, loc="left", color=INK, fontsize=13, fontweight="bold", pad=22)
    if len(data) > 1:
        average = sum(values) / len(values)
        ax.axvline(average, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=3)
        ax.text(average, len(data) - .45, "среднее по городам " + format_value(average, kind), color=MUTED, fontsize=9.5,
                ha="right" if average > top * .75 else "left", va="bottom")
    width = min(14, 150 / len(data))
    for place, value in enumerate(values):
        leader = place == len(data) - 1
        ax.hlines(place, 0, value, color=ACCENT if leader else PALE, linewidth=width, capstyle="round", zorder=2)
        ax.text(value + top * .025, place, format_value(value, kind), va="center", color=INK, fontsize=10.5, zorder=4,
                fontweight="bold" if leader else "normal", bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})

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
        ax.grid(axis="x", alpha=.2)
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
        if valid:
            draw_bars(ax, valid, field, kind, title)
        else:
            ax.set_title(title)
            ax.text(.5, .5, "Значения отсутствуют", ha="center")
            ax.axis("off")
    return figure
