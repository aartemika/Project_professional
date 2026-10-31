"""Консольное исследование CSV через pandas и matplotlib."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from matplotlib.figure import Figure
from source.dataset import load_dataset

ROOT = Path(__file__).resolve().parents[1]
RESULTS = Path(__file__).resolve().parent / "results"

def analyze_file(path: Path, output: Path = RESULTS) -> dict:
    """Проверить файл и сохранить таблицы, отчёт и четыре графика."""
    data, report = load_dataset(path)
    folder = output / path.stem
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "quality.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    by_city = data.groupby("area_name").agg(vacancies=("vacancy_id", "count"),
        salary_median=("salary", "median"), salary_known=("salary", "count"),
        responses_mean=("responses_count", "mean"), remote_share=("is_remote", "mean"))
    by_city.to_csv(folder / "cities.csv", encoding="utf-8-sig")
    data.category.value_counts().to_csv(folder / "categories.csv", encoding="utf-8-sig")
    for name, series, title in [
        ("cities", by_city.vacancies.sort_values().tail(15), "Число вакансий по городам"),
        ("categories", data.category.value_counts().head(12).sort_values(), "Ведущие профессиональные области"),
        ("salary", by_city.salary_median.dropna().sort_values().tail(15), "Медиана зарплаты, руб./месяц")]:
        figure = Figure(figsize=(11, 7), layout="constrained")
        ax = figure.subplots()
        ax.barh(series.index, series.values, color="#247b92")
        ax.set_title(title)
        ax.grid(axis="x", alpha=.2)
        figure.savefig(folder / (name + ".png"), dpi=140)
        figure.clear()
    figure = Figure(figsize=(10, 6), layout="constrained")
    ax = figure.subplots()
    values = data.salary.dropna()
    limit = float(values.quantile(.99)) if len(values) else 0
    ax.hist(values[values <= limit], bins=40, color="#247b92")
    ax.set(title="Распределение зарплат до 99-го процентиля", xlabel="Рубли в месяц", ylabel="Вакансии")
    figure.savefig(folder / "salary_distribution.png", dpi=140)
    figure.clear()
    text = (f"Источник: {path.name}\nСтрок: {report['raw_rows']}\nУникальных вакансий: {report['rows']}\n"
            f"Городов: {report['cities']}\nКатегорий: {report['categories']}\n"
            f"Зарплата известна: {report['salary_known']}\nОтклики известны: {report['responses_known']}\n"
            "Снимки анализируются отдельно. Зарплата только месячная, в рублях.\n"
            "Данные о резюме и отдельных Hard Skills отсутствуют.\n"
            "Гистограмма ограничена 99-м процентилем только для отображения; таблицы содержат все значения.\n")
    (folder / "report.txt").write_text(text, encoding="utf-8")
    print(text)
    print("Результаты:", folder)
    return report

def compare_files(paths: list[Path], output: Path = RESULTS) -> pd.DataFrame:
    """Сравнить состав файлов и пересечение ID, не трактуя это как динамику."""
    records, identifiers = [], []
    for path in paths:
        data, report = load_dataset(path)
        identifiers.append(set(data.vacancy_id))
        records.append({k: report[k] for k in ["source", "raw_rows", "rows", "cities", "categories", "salary_known"]})
    result = pd.DataFrame(records)
    output.mkdir(parents=True, exist_ok=True)
    result.to_csv(output / "files_comparison.csv", index=False, encoding="utf-8-sig")
    overlap = pd.DataFrame([[len(a & b) for b in identifiers] for a in identifiers],
                           index=[p.name for p in paths], columns=[p.name for p in paths])
    overlap.to_csv(output / "id_overlap.csv", encoding="utf-8-sig")
    print(result.to_string(index=False))
    print("Пересечение уникальных ID:")
    print(overlap.to_string())
    return result

def main() -> None:
    """Запустить простое меню без аргументов командной строки."""
    while True:
        files = sorted((ROOT / "data").glob("*.csv"))
        print("\n1 — Выбрать и исследовать файл\n2 — Исследовать все файлы отдельно\n3 — Сравнить состав файлов\n0 — Выход")
        try:
            choice = input("Команда: ").strip()
            if choice == "0":
                return
            if not files:
                print("CSV в папке data не найдены")
                continue
            if choice == "1":
                for number, path in enumerate(files, 1):
                    print(number, path.name)
                index = int(input("Номер файла: ")) - 1
                if not 0 <= index < len(files):
                    raise ValueError("Неверный номер файла")
                analyze_file(files[index])
            elif choice == "2":
                for path in files:
                    analyze_file(path)
            elif choice == "3":
                compare_files(files)
            else:
                print("Неизвестная команда")
        except (ValueError, OSError, pd.errors.ParserError) as error:
            print("Ошибка:", error)
        except (EOFError, KeyboardInterrupt):
            print("\nЗавершение работы")
            return

if __name__ == "__main__":
    main()
