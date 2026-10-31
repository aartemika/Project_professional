"""Оконный клиент с отдельными UI, QSS и локальной справкой."""
import sys
from pathlib import Path
from typing import Callable, Any
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QFile, QIODevice, QThread, Signal
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (QApplication, QWidget, QDialog, QLineEdit, QPushButton, QLabel,
    QComboBox, QListWidget, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout,
    QAbstractItemView, QFileDialog, QMessageBox, QHeaderView)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from source.charts import make_chart
from source.api_client import ApiClient
from source.config import SERVER_URL

ROOT = Path(__file__).resolve().parents[1]

def load_ui(name: str) -> QWidget:
    """Загрузить форму Qt Designer без генерации Python кода."""
    file = QFile(str(ROOT / "ui" / name))
    if not file.open(QIODevice.OpenModeFlag.ReadOnly):
        raise RuntimeError("Не удалось открыть форму " + name)
    loader = QUiLoader()
    widget = loader.load(file)
    file.close()
    if widget is None:
        raise RuntimeError(loader.errorString())
    return widget

class Worker(QThread):
    """Исполнитель HTTP запроса вне потока интерфейса."""
    success = Signal(object)
    failure = Signal(str)

    def __init__(self, action: Callable, parent: QWidget) -> None:
        """Сохранить функцию запроса."""
        super().__init__(parent)
        self.action = action

    def run(self) -> None:
        """Выполнить запрос и передать результат в главный поток."""
        try:
            self.success.emit(self.action())
        except Exception as error:
            self.failure.emit(str(error))

class Navigator:
    """Контроллер форм, фильтров и визуализации вакансий."""
    def __init__(self) -> None:
        """Загрузить главную форму и связать элементы управления."""
        self.window = load_ui("main.ui")
        self.client = ApiClient(SERVER_URL)
        self.jobs: list[Worker] = []
        self.rows: list[dict] = []
        self.loading = False
        self.admin_controller = None
        self.help_dialog: QDialog | None = None
        self.category = self.window.findChild(QComboBox, "categoryCombo")
        self.cities = self.window.findChild(QListWidget, "citiesList")
        self.cluster = self.window.findChild(QComboBox, "clusterCombo")
        self.table = self.window.findChild(QTableWidget, "summaryTable")
        self.note = self.window.findChild(QTextBrowser, "recommendationBrowser")
        self.status = self.window.findChild(QLabel, "statusLabel")
        self.chart_type = self.window.findChild(QComboBox, "chartCombo")
        for label, value in [("Число вакансий", "vacancies"), ("Зарплата", "salary"),
            ("Отклики", "responses"), ("Удалённая работа", "remote"), ("Индекс спроса", "indicator"), ("Схема городов", "map")]:
            self.chart_type.addItem(label, value)
        self.cities.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.cluster.addItems(["Все группы", "Группа 1", "Группа 2", "Группа 3"])
        self.cluster.currentIndexChanged.connect(self.render)
        self.chart_type.currentIndexChanged.connect(self.draw)
        for name, action in [("refreshButton", self.refresh), ("compareButton", self.compare),
            ("resetButton", self.reset), ("helpButton", self.show_help), ("exportButton", self.export),
            ("logoutButton", self.logout), ("adminButton", self.show_admin)]:
            self.window.findChild(QPushButton, name).clicked.connect(action)
        self.canvas = FigureCanvasQTAgg(make_chart([]))
        area = self.window.findChild(QWidget, "chartArea")
        layout = area.layout()
        layout.addWidget(self.canvas)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Город", "Вакансии", "Зарплата руб./мес.", "Средние отклики", "Удалённо %", "Индекс", "Кластер"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def start_job(self, action: Callable, callback: Callable, parent: QWidget | None = None) -> None:
        """Запустить сетевую операцию и удерживать поток до завершения."""
        worker = Worker(action, parent or self.window)
        self.jobs.append(worker)
        worker.success.connect(callback)
        worker.failure.connect(self.show_error)
        worker.finished.connect(self.job_finished)
        self.status.setText("Загрузка…")
        worker.start()

    def job_finished(self) -> None:
        """Снять блокировку элементов после сетевого запроса."""
        self.jobs = [job for job in self.jobs if job.isRunning()]
        for name in ["refreshButton", "compareButton", "resetButton"]:
            self.window.findChild(QPushButton, name).setEnabled(True)

    def show_error(self, message: str) -> None:
        """Показать пользователю сетевую ошибку."""
        self.loading = False
        self.status.setText(message)
        QMessageBox.warning(self.window if self.window.isVisible() else None, "Ошибка запроса", message)

    def authenticate(self) -> bool:
        """Показать окно входа, сохраняя пароль только до отправки."""
        dialog = load_ui("login.ui")
        server = dialog.findChild(QLineEdit, "serverEdit")
        username = dialog.findChild(QLineEdit, "usernameEdit")
        password = dialog.findChild(QLineEdit, "passwordEdit")
        button = dialog.findChild(QPushButton, "loginButton")
        message = dialog.findChild(QLabel, "messageLabel")
        server.setText(self.client.base_url)
        def submit() -> None:
            """Запустить авторизацию из формы входа."""
            address = server.text().strip().rstrip("/")
            if not address.startswith(("http://", "https://")):
                message.setText("Адрес должен начинаться с http:// или https://")
                return
            if not username.text().strip() or not password.text():
                message.setText("Введите логин и пароль")
                return
            self.client.base_url = address
            user, secret = username.text().strip(), password.text()
            password.clear()
            button.setEnabled(False)
            message.setText("Подключение…")
            job = Worker(lambda: self.client.login(user, secret), dialog)
            self.jobs.append(job)
            def accepted(result: dict) -> None:
                """Закрыть форму после успешной авторизации."""
                self.window.findChild(QPushButton, "adminButton").setVisible(result.get("is_admin", False))
                self.status.setText("Пользователь: " + result["username"])
                dialog.accept()
            def failed(error: str) -> None:
                """Разблокировать форму после отказа во входе."""
                message.setText(error)
                button.setEnabled(True)
            job.success.connect(accepted)
            job.failure.connect(failed)
            job.start()
        button.clicked.connect(submit)
        password.returnPressed.connect(submit)
        result = dialog.exec() == QDialog.DialogCode.Accepted
        for job in self.jobs:
            job.wait()
        self.jobs.clear()
        return result

    def open(self) -> None:
        """Показать главную форму и запросить справочники."""
        self.window.show()
        self.start_job(self.client.references, self.set_references)

    def set_references(self, refs: dict) -> None:
        """Заполнить фильтры значениями из базы сервера."""
        self.category.clear()
        self.category.addItem("Все области", "")
        for item in refs["categories"]:
            self.category.addItem(item, item)
        self.cities.clear()
        self.cities.addItems(refs["cities"])
        self.refresh()

    def selected_cities(self) -> list[str]:
        """Получить отмеченные пользователем города."""
        return [item.text() for item in self.cities.selectedItems()]

    def refresh(self) -> None:
        """Загрузить метрики по текущим фильтрам."""
        if self.loading:
            return
        self.loading = True
        for name in ["refreshButton", "compareButton", "resetButton"]:
            self.window.findChild(QPushButton, name).setEnabled(False)
        category, cities = self.category.currentData() or "", self.selected_cities()
        self.start_job(lambda: self.client.summary(category, cities), self.set_data)

    def set_data(self, result: dict) -> None:
        """Сохранить результаты HTTP запроса и обновить представление."""
        self.loading = False
        self.rows = result["rows"]
        self.note.setPlainText(result["recommendation"])
        self.render()

    def render(self) -> None:
        """Заполнить таблицу с учётом фильтра кластеров."""
        rows = self.visible_rows()
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, key in enumerate(["city", "count", "salary", "responses", "remote", "indicator", "cluster"]):
                value = row[key]
                item = QTableWidgetItem(str(value) if value is not None else "Нет данных")
                if key in {"salary", "responses"}:
                    item.setToolTip("Известных значений: " + str(row[key + "_known"]))
                self.table.setItem(i, j, item)
        self.status.setText(f"Городов в срезе: {len(rows)}. Для обновления фильтров нажмите «Применить».")
        self.draw()

    def visible_rows(self) -> list[dict]:
        """Отфильтровать полученные строки по номеру группы."""
        return [r for r in self.rows if self.cluster.currentIndex() == 0 or r["cluster"] == self.cluster.currentText()]

    def draw(self) -> None:
        """Обновить встроенный график matplotlib."""
        if not hasattr(self, "canvas"):
            return
        old = self.canvas.figure
        old.clear()
        self.canvas.figure = make_chart(self.visible_rows(), self.chart_type.currentData() or "vacancies")
        self.canvas.figure.set_canvas(self.canvas)
        dpi = self.canvas.figure.dpi
        self.canvas.figure.set_size_inches(max(self.canvas.width(), 1) / dpi, max(self.canvas.height(), 1) / dpi, forward=False)
        self.canvas.draw_idle()

    def compare(self) -> None:
        """Проверить выбор двух или трёх городов и запросить сравнение."""
        if not 2 <= len(self.selected_cities()) <= 3:
            QMessageBox.information(self.window, "Сравнение", "Выберите от двух до трёх городов в списке.")
            return
        self.refresh()

    def reset(self) -> None:
        """Вернуть фильтры к полному набору данных."""
        self.category.setCurrentIndex(0)
        self.cities.clearSelection()
        self.cluster.setCurrentIndex(0)
        self.refresh()

    def export(self) -> None:
        """Сохранить текущий график в PNG или PDF."""
        if not self.visible_rows():
            QMessageBox.information(self.window, "Экспорт", "Сначала загрузите непустой набор данных.")
            return
        path, selected_filter = QFileDialog.getSaveFileName(self.window, "Сохранить график", "navigator.png", "PNG (*.png);;PDF (*.pdf)")
        if path:
            if not Path(path).suffix:
                path += ".pdf" if "PDF" in selected_filter else ".png"
            try:
                self.canvas.figure.savefig(path, dpi=150)
                self.status.setText("Сохранено: " + path)
            except OSError as error:
                QMessageBox.warning(self.window, "Ошибка сохранения", str(error))

    def show_help(self) -> None:
        """Открыть локальную справку в отдельной форме."""
        if self.help_dialog is None:
            self.help_dialog = load_ui("help.ui")
            browser = self.help_dialog.findChild(QTextBrowser, "helpBrowser")
            browser.setHtml((ROOT / "resources/help.html").read_text(encoding="utf-8"))
        self.help_dialog.show()
        self.help_dialog.raise_()

    def show_admin(self) -> None:
        """Открыть HTTP редактор всех таблиц для администратора."""
        from source.admin import AdminController
        if self.admin_controller is None:
            self.admin_controller = AdminController(self, load_ui("admin.ui"))
            self.admin_controller.window.finished.connect(self.reload_references)
        self.admin_controller.window.show()
        self.admin_controller.reload()

    def reload_references(self) -> None:
        """Обновить фильтры после закрытия редактора данных."""
        if self.client.token and self.window.isVisible():
            self.start_job(self.client.references, self.set_references)

    def logout(self) -> None:
        """Удалить токен и завершить клиентский сеанс."""
        self.client.token = ""
        if self.admin_controller is not None:
            self.admin_controller.window.close()
        if self.help_dialog is not None:
            self.help_dialog.close()
        self.window.close()

    def wait_jobs(self) -> None:
        """Дождаться завершения запросов перед уничтожением Qt объектов."""
        for job in self.jobs:
            job.wait()

def main() -> None:
    """Настроить приложение и запустить цикл событий Qt."""
    app = QApplication(sys.argv)
    app.setApplicationName("Экономико-кадровый навигатор")
    app.setStyleSheet((ROOT / "resources/style.qss").read_text(encoding="utf-8"))
    navigator = Navigator()
    if navigator.authenticate():
        navigator.open()
        app.exec()
        navigator.wait_jobs()

if __name__ == "__main__":
    main()
