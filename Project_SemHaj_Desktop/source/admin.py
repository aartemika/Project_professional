"""Административные формы CRUD через HTTP API."""
from typing import Any, Callable
from PySide6.QtWidgets import (QWidget, QComboBox, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QFormLayout, QMessageBox, QAbstractItemView, QHeaderView)

class AdminController:
    """Редактор всех сущностей без прямого доступа к SQLite."""
    def __init__(self, owner: Any, window: QWidget) -> None:
        """Связать загруженную UI форму с HTTP операциями."""
        self.owner = owner
        self.window = window
        self.entity = window.findChild(QComboBox, "entityCombo")
        self.search = window.findChild(QLineEdit, "searchEdit")
        self.table = window.findChild(QTableWidget, "recordsTable")
        self.status = window.findChild(QLabel, "pageLabel")
        self.form = QFormLayout(window.findChild(QWidget, "fieldsArea"))
        self.inputs: dict[str, QWidget] = {}
        self.schema: list[dict] = []
        self.rows: list[dict] = []
        self.identifier: str | None = None
        self.page = 1
        self.pages = 1
        self.busy = False
        for label, key in [("Вакансии", "vacancies"), ("Города", "cities"), ("Области", "categories"),
            ("Форматы работы", "formats"), ("Пользователи", "users"), ("Журнал импорта", "imports")]:
            self.entity.addItem(label, key)
        self.entity.currentIndexChanged.connect(self.change_entity)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.select_record)
        for name, action in [("loadButton", self.reload), ("newButton", self.new_record),
            ("saveButton", self.save), ("deleteButton", self.delete),
            ("previousButton", self.previous), ("nextButton", self.next_page)]:
            window.findChild(QPushButton, name).clicked.connect(action)

    def change_entity(self) -> None:
        """Сменить таблицу и начать просмотр с первой страницы."""
        self.page = 1
        self.reload()

    def run(self, action: Callable, callback: Callable) -> None:
        """Выполнить запрос в отдельном потоке с блокировкой редактора."""
        if self.busy:
            return
        from PySide6.QtCore import QThread, Signal
        class RequestJob(QThread):
            """Фоновый исполнитель административной HTTP операции."""
            success = Signal(object)
            failure = Signal(str)

            def run(self) -> None:
                """Передать в UI результат или понятное описание ошибки."""
                try:
                    self.success.emit(action())
                except Exception as error:
                    self.failure.emit(str(error))
        self.busy = True
        self.window.findChild(QWidget, "controlsArea").setEnabled(False)
        def completed(result: dict) -> None:
            """Вернуть управление форме после успешного запроса."""
            self.busy = False
            self.window.findChild(QWidget, "controlsArea").setEnabled(True)
            callback(result)
        def failed(message: str) -> None:
            """Вернуть управление форме после ошибки запроса."""
            self.busy = False
            self.window.findChild(QWidget, "controlsArea").setEnabled(True)
            QMessageBox.warning(self.window, "Ошибка", message)
        job = RequestJob(self.window)
        self.owner.jobs.append(job)
        job.success.connect(completed)
        job.failure.connect(failed)
        job.start()

    def reload(self) -> None:
        """Загрузить текущую страницу выбранной таблицы."""
        entity = self.entity.currentData()
        page, search = self.page, self.search.text().strip()
        self.run(lambda: self.owner.client.request("GET", "/api/admin/" + entity,
            params={"page": page, "q": search}), self.set_records)

    def set_records(self, result: dict) -> None:
        """Заполнить таблицу и перестроить поля формы по схеме сервера."""
        self.rows = result["rows"]
        self.schema = result["schema"]
        self.page, self.pages = result["page"], result["pages"]
        self.table.clearSelection()
        self.table.setRowCount(0)
        columns = ["id"] + [f["name"] for f in self.schema if f["name"] not in {"id", "password"}]
        self.table.setColumnCount(len(columns))
        labels = {f["name"]: f["label"] for f in self.schema}
        self.table.setHorizontalHeaderLabels([labels.get(c, "ID") for c in columns])
        self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            for j, column in enumerate(columns):
                self.table.setItem(i, j, QTableWidgetItem("" if row.get(column) is None else str(row[column])))
        while self.form.rowCount():
            self.form.removeRow(0)
        self.inputs.clear()
        for field in self.schema:
            kind = field["kind"]
            if kind == "bool":
                widget = QComboBox()
                widget.addItem("Нет", False)
                widget.addItem("Да", True)
            elif kind in {"city", "category", "format"}:
                widget = QComboBox()
                widget.addItem("Выберите", None)
                for choice in field["choices"]:
                    widget.addItem(choice["name"], choice["id"])
            else:
                widget = QLineEdit()
                if kind == "password":
                    widget.setEchoMode(QLineEdit.EchoMode.Password)
            self.inputs[field["name"]] = widget
            self.form.addRow(field["label"], widget)
        self.status.setText(f"Записей: {result['total']} · страница {self.page} из {self.pages}")
        self.new_record()

    def new_record(self) -> None:
        """Очистить форму для создания новой записи."""
        self.identifier = None
        self.table.clearSelection()
        for name, widget in self.inputs.items():
            widget.setEnabled(True)
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(1 if name == "active" else 0)

    def select_record(self) -> None:
        """Перенести выбранную строку в форму редактирования."""
        index = self.table.currentRow()
        if index < 0 or index >= len(self.rows) or not self.table.selectedItems():
            return
        row = self.rows[index]
        self.identifier = str(row["id"])
        for name, widget in self.inputs.items():
            value = row.get(name)
            if isinstance(widget, QLineEdit):
                widget.setText("" if value is None else str(value))
            else:
                widget.setCurrentIndex(max(0, widget.findData(value)))
            widget.setEnabled(name != "id")

    def payload(self) -> dict:
        """Собрать значения полей без хешей паролей."""
        return {name: widget.text() if isinstance(widget, QLineEdit) else widget.currentData()
                for name, widget in self.inputs.items()}

    def saved(self, result: dict) -> None:
        """Обновить страницу после изменения данных."""
        self.reload()

    def save(self) -> None:
        """Создать запись либо сохранить выбранную строку."""
        entity, identifier, values = self.entity.currentData(), self.identifier, self.payload()
        url = "/api/admin/" + entity + ("/" + identifier if identifier is not None else "")
        method = "PUT" if identifier is not None else "POST"
        self.run(lambda: self.owner.client.request(method, url, json=values), self.saved)

    def delete(self) -> None:
        """Удалить выбранную запись после явного выбора пользователя."""
        if self.identifier is None:
            QMessageBox.information(self.window, "Удаление", "Сначала выберите запись в таблице")
            return
        answer = QMessageBox.question(self.window, "Удаление", "Удалить выбранную запись?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            url = "/api/admin/" + self.entity.currentData() + "/" + self.identifier
            self.run(lambda: self.owner.client.request("DELETE", url), self.saved)

    def previous(self) -> None:
        """Перейти к предыдущей странице."""
        self.page = max(1, self.page-1)
        self.reload()

    def next_page(self) -> None:
        """Перейти к следующей странице."""
        self.page = min(self.pages, self.page+1)
        self.reload()
