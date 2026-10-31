"""Аналитические страницы и экспорт графиков."""
from io import BytesIO
from threading import Lock
from typing import Any
from flask import Blueprint, render_template, request, send_file, abort
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from ..charts import make_chart
from .auth_api import login_required
from ..services import summary, references, recommendation, frame
from ..database.models import db, ImportLog

bp = Blueprint("pages", __name__)
plot_lock = Lock()

def selection() -> tuple[str, list[str]]:
    """Прочитать и проверить параметры аналитического запроса."""
    category = request.args.get("category", "")
    cities = request.args.getlist("city")
    refs = references()
    if category and category not in refs["categories"]:
        abort(400, description="Неизвестная профессиональная область")
    if any(city not in refs["cities"] for city in cities):
        abort(400, description="Неизвестный город")
    return category, cities

@bp.get("/")
@login_required
def index() -> str:
    """Показать метрики выбранного среза и фильтры сравнения."""
    category, cities = selection()
    rows = summary(category, cities)
    cluster = request.args.get("cluster", "")
    if cluster:
        rows = [r for r in rows if r["cluster"] == cluster]
    compare_error = "Для сравнения выберите от двух до трёх городов." if request.args.get("compare") and not 2 <= len(cities) <= 3 else ""
    return render_template("index.html", rows=rows, refs=references(), category=category, cities=cities,
        recommendation=recommendation(rows), cluster=cluster, compare_error=compare_error,
        source=db.session.scalar(db.select(ImportLog).order_by(ImportLog.id.desc()).limit(1)))

@bp.get("/chart.png")
@login_required
def chart() -> Any:
    """Сформировать PNG средствами matplotlib без внешних ресурсов."""
    category, cities = selection()
    kind = request.args.get("kind", "vacancies")
    if kind not in {"vacancies", "salary", "responses", "remote", "indicator", "map"}:
        abort(400, description="Неизвестный график")
    rows = summary(category, cities)
    if request.args.get("cluster"):
        rows = [r for r in rows if r["cluster"] == request.args["cluster"]]
    stream = BytesIO()
    with plot_lock:
        figure = make_chart(rows, kind)
        figure.savefig(stream, format="png", dpi=120)
        figure.clear()
    stream.seek(0)
    return send_file(stream, mimetype="image/png")

@bp.get("/report.pdf")
@login_required
def report() -> Any:
    """Экспортировать графики и текстовую рекомендацию в PDF."""
    category, cities = selection()
    rows = summary(category, cities)
    if not rows:
        abort(400, description="Нет данных для отчёта")
    stream = BytesIO()
    with plot_lock, PdfPages(stream) as pdf:
        title = Figure(figsize=(8.27, 11.69))
        title.text(.1, .9, "Экономико-кадровый навигатор", fontsize=17)
        import textwrap
        text = "Область: " + (category or "Все области") + "\n\n" + recommendation(rows)
        text += "\n\nИндекс = 100 × число вакансий города / максимум по городам выбранной области."
        text += "\n\nОтклики не равны числу уникальных соискателей. Доли форматов могут пересекаться."
        source = db.session.scalar(db.select(ImportLog).order_by(ImportLog.id.desc()).limit(1))
        if source:
            text += f"\n\nИсточник: {source.filename}; импортировано {source.rows} вакансий."
        wrapped = "\n".join(textwrap.fill(line, 75) for line in text.splitlines())
        title.text(.1, .82, wrapped, va="top", fontsize=11, linespacing=1.6)
        pdf.savefig(title)
        title.clear()
        for kind in ["vacancies", "salary", "responses", "remote"]:
            figure = make_chart(rows, kind)
            pdf.savefig(figure)
            figure.clear()
    stream.seek(0)
    return send_file(stream, mimetype="application/pdf", as_attachment=True, download_name="navigator_report.pdf")

@bp.get("/vacancies")
@login_required
def vacancies() -> str:
    """Показать постраничный список вакансий выбранного среза."""
    category, cities = selection()
    data = frame(category, cities)
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        abort(400, description="Номер страницы должен быть целым")
    search = request.args.get("q", "").strip()
    if search:
        data = data[data.name.str.contains(search, case=False, regex=False)]
    pages = max(1, (len(data) + 49) // 50)
    page = min(page, pages)
    records = data.iloc[(page - 1) * 50:page * 50].where(data.notna(), None).to_dict("records")
    return render_template("vacancies.html", records=records, page=page, pages=pages, count=len(data),
        category=category, cities=cities, search=search)

@bp.get("/help")
def help_page() -> str:
    """Показать инструкцию и методику расчётов."""
    return render_template("help.html")

@bp.get("/contacts")
def contacts() -> str:
    """Показать контакты сопровождения учебного проекта."""
    return render_template("contacts.html")
