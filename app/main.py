import os
import sys

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPalette, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QSplitter,
    QTextEdit,
    QFileDialog,
    QStatusBar,
    QProgressBar,
    QFrame,
    QAbstractItemView,
    QGraphicsOpacityEffect,
    QGraphicsDropShadowEffect,  # ← ДОБАВИЛИ
)

# директории, которые не включаем в дерево
IGNORE_DIRS = {
    ".git", ".idea", ".vscode", "node_modules", "venv",
    "__pycache__", ".hg", ".svn", ".mypy_cache", ".pytest_cache",
}


class MainWindow(QMainWindow):
    FILE_SEPARATOR = "===END OF THE FILE==="
    def __init__(self):
        super().__init__()

        self.project_path: str | None = None
        self.export_path: str | None = None

        self.total_files: int = 0
        self.total_dirs: int = 0
        self.selected_files: int = 0
        self.selected_groups_count: int = 0

        self.setWindowTitle("AI Project Exporter")
        self.resize(1200, 760)
        self.setMinimumSize(1000, 600)

        # --- БАЗОВОЙ КОНТЕЙНЕР ---
        outer = QWidget(self)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(24, 20, 24, 16)
        outer_layout.setSpacing(12)

        # верхняя «полоса» (логотип + кнопки)
        header = self.build_header()
        outer_layout.addWidget(header)

        # тонкая линия
        top_line = QFrame()
        top_line.setFrameShape(QFrame.HLine)
        top_line.setObjectName("TopDivider")
        outer_layout.addWidget(top_line)

        # основной контент
        content = self.build_content()
        outer_layout.addWidget(content, 1)

        self.setCentralWidget(outer)

        # --- STATUS BAR ---
        status = QStatusBar()
        self.setStatusBar(status)
        self.statusBar().showMessage("Готово. Выберите папку проекта.")

        # плавное появление окна
        self.setup_fade_in_effect()

        # горячие клавиши
        self.setup_shortcuts()

        # начальное состояние кнопок экспорта
        self.update_export_buttons_state()

    # -----------------------
    # Эффект плавного появления
    # -----------------------

    def setup_fade_in_effect(self) -> None:
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self._fade_effect = effect

        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(280)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        anim.start()
        self._fade_anim = anim

    # -----------------------
    # Хоткеи
    # -----------------------

    def setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.choose_project)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, activated=self.choose_export_path)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.start_export_grouped)
        QShortcut(QKeySequence("Ctrl+Shift+E"), self, activated=self.start_export_single)

    # -----------------------
    # Верхняя панель
    # -----------------------

    def build_header(self) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Левая часть — название + подпись
        left_box = QVBoxLayout()
        left_box.setContentsMargins(0, 0, 0, 0)
        left_box.setSpacing(2)

        title = QLabel("AI Project Exporter")
        title.setFont(QFont("Segoe UI", 15, QFont.Bold))

        subtitle = QLabel("Экспорт кода проекта в аккуратные TXT-файлы для нейросетей")
        subtitle.setObjectName("HeaderSubtitle")

        left_box.addWidget(title)
        left_box.addWidget(subtitle)

        # Правая часть — кнопки
        buttons_box = QHBoxLayout()
        buttons_box.setContentsMargins(0, 0, 0, 0)
        buttons_box.setSpacing(10)

        self.btn_project = QPushButton("Выбрать проект")
        self.btn_project.setProperty("pill", True)

        self.btn_export = QPushButton("Папка для TXT")
        self.btn_export.setProperty("pill", True)

        self.btn_settings = QPushButton("Настройки")
        self.btn_settings.setProperty("pill_secondary", True)

        self.btn_project.clicked.connect(self.choose_project)
        self.btn_export.clicked.connect(self.choose_export_path)

        self.btn_project.setToolTip("Ctrl+O — выбрать папку проекта")
        self.btn_export.setToolTip("Ctrl+Shift+O — выбрать папку для TXT")

        buttons_box.addWidget(self.btn_project)
        buttons_box.addWidget(self.btn_export)
        buttons_box.addWidget(self.btn_settings)

        layout.addLayout(left_box)
        layout.addStretch(1)
        layout.addLayout(buttons_box)

        return wrapper

    # -----------------------
    # Основной контент
    # -----------------------

    def build_content(self) -> QSplitter:
        splitter = QSplitter(Qt.Horizontal)

        # ЛЕВАЯ КАРТОЧКА (структура проекта)
        left_card = QFrame()
        left_card.setProperty("card_soft", True)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(14, 12, 14, 12)
        left_layout.setSpacing(4)

        tree_title = QLabel("Структура проекта")
        tree_title.setProperty("section_title", True)

        tree_hint = QLabel("Отметьте файлы и папки, которые хотите включить в экспорт.")
        tree_hint.setObjectName("SectionHint")

        left_layout.addWidget(tree_title)
        left_layout.addWidget(tree_hint)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(18)
        self.tree.setUniformRowHeights(True)
        self.tree.setFrameStyle(QFrame.NoFrame)

        # только чекбоксы, без выделения строк
        self.tree.setSelectionMode(QAbstractItemView.NoSelection)
        self.tree.setFocusPolicy(Qt.NoFocus)

        self.tree.itemChanged.connect(self.on_item_changed)

        left_layout.addWidget(self.tree, 1)

        # ПРАВАЯ КАРТОЧКА (сводка + экспорт + лог)
        right_card = QFrame()
        right_card.setProperty("card_soft", True)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(14, 12, 14, 12)
        right_layout.setSpacing(8)

        # блок сводки
        self.card_info = QLabel()
        self.card_info.setWordWrap(True)
        self.card_info.setMinimumHeight(120)
        self.update_summary()

        # блок кнопок экспорта
        buttons_row = QHBoxLayout()
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(8)

        self.btn_run = QPushButton("Экспортировать")
        self.btn_run.setProperty("accent", True)
        self.btn_run.setFixedHeight(40)
        self.btn_run.clicked.connect(self.start_export_grouped)
        self.btn_run.setToolTip("Ctrl+E — экспортировать выбранные файлы в несколько TXT по папкам")

        self.btn_run_single = QPushButton("Экспорт в один файл")
        self.btn_run_single.setProperty("secondary", True)
        self.btn_run_single.setFixedHeight(40)
        self.btn_run_single.clicked.connect(self.start_export_single)
        self.btn_run_single.setToolTip("Ctrl+Shift+E — экспортировать выбранные файлы в один общий TXT")

        buttons_row.addWidget(self.btn_run, 1)
        buttons_row.addWidget(self.btn_run_single, 1)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)

        # лог
        log_label = QLabel("Лог действий")
        log_label.setProperty("section_title_small", True)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Здесь будет появляться ход экспорта...\n")

        right_layout.addWidget(self.card_info)
        right_layout.addSpacing(4)
        right_layout.addLayout(buttons_row)
        right_layout.addWidget(self.progress)
        right_layout.addSpacing(6)
        right_layout.addWidget(log_label)
        right_layout.addWidget(self.log, 1)

        splitter.addWidget(left_card)
        splitter.addWidget(right_card)
        splitter.setSizes([780, 420])

        return splitter

    # -----------------------
    # Статус готовности к экспорту
    # -----------------------

    def is_ready_for_export(self) -> bool:
        return bool(self.project_path and self.export_path and self.selected_files > 0)

    def update_export_buttons_state(self) -> None:
        ready = self.is_ready_for_export()
        for btn in (getattr(self, "btn_run", None), getattr(self, "btn_run_single", None)):
            if not btn:
                continue
            btn.setEnabled(ready)

    # -----------------------
    # Обновление информации (карточка справа)
    # -----------------------

    def update_summary(self) -> None:
        project = self.project_path if self.project_path else "не выбрано"
        export = self.export_path if self.export_path else "не выбрано"

        files = self.selected_files
        groups = self.selected_groups_count

        extra = ""
        if self.project_path:
            extra = (
                f"<br><span style='color:#A3ABB3'>Всего файлов в проекте: {self.total_files}, "
                f"папок: {self.total_dirs}</span>"
            )

        text = (
            f"<b>Проект</b><br>"
            f"<span style='color:#F5F7FA'>{project}</span><br><br>"
            f"<b>Папка для TXT</b><br>"
            f"<span style='color:#F5F7FA'>{export}</span><br><br>"
            f"<b>Выбрано файлов:</b> {files}<br>"
            f"<b>Групп (TXT по папкам):</b> {groups}"
            f"{extra}"
        )

        self.card_info.setText(text)

    # -----------------------
    # Выбор проекта / папки экспорта
    # -----------------------

    def choose_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Выберите папку проекта")
        if path:
            self.project_path = path
            self.statusBar().showMessage(f"Выбран проект: {path}")
            self.log.append(f"[INFO] Проект выбран: {path}")
            self.load_project_tree()
            self.update_export_buttons_state()

    def choose_export_path(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Папка для TXT")
        if path:
            self.export_path = path
            self.statusBar().showMessage(f"Папка TXT: {path}")
            self.log.append(f"[INFO] Папка для TXT: {path}")
            self.update_summary()
            self.update_export_buttons_state()

    # -----------------------
    # ЗАГРУЗКА ДЕРЕВА ИЗ ФС
    # -----------------------

    def load_project_tree(self) -> None:
        if not self.project_path:
            return

        self.tree.blockSignals(True)
        self.tree.clear()

        self.total_files = 0
        self.total_dirs = 0
        self.selected_files = 0
        self.selected_groups_count = 0

        root_name = os.path.basename(self.project_path.rstrip(os.sep)) or self.project_path
        root_item = QTreeWidgetItem([root_name])
        root_item.setData(0, Qt.UserRole, self.project_path)
        root_item.setData(0, Qt.UserRole + 1, True)  # is_dir
        root_item.setFlags(root_item.flags() | Qt.ItemIsUserCheckable)
        root_item.setCheckState(0, Qt.Unchecked)

        self.tree.addTopLevelItem(root_item)

        self._add_children(root_item, self.project_path)

        self.tree.expandItem(root_item)
        self.tree.blockSignals(False)

        self.recalc_selection_stats()
        self.update_export_buttons_state()

        self.statusBar().showMessage(
            f"Загружен проект: {self.project_path} "
            f"(файлов: {self.total_files}, папок: {self.total_dirs})"
        )
        self.log.append(
            f"[INFO] Загружен проект. Файлов: {self.total_files}, папок: {self.total_dirs}"
        )

    def _add_children(self, parent_item: QTreeWidgetItem, parent_path: str) -> None:
        try:
            entries = sorted(
                list(os.scandir(parent_path)),
                key=lambda e: (not e.is_dir(), e.name.lower())
            )
        except PermissionError:
            self.log.append(f"[WARN] Нет доступа: {parent_path}")
            return

        for entry in entries:
            name = entry.name

            if name in IGNORE_DIRS:
                continue
            if name.startswith(".") and entry.is_dir():
                continue

            full_path = os.path.join(parent_path, name)

            if entry.is_dir():
                item = QTreeWidgetItem([name])
                item.setData(0, Qt.UserRole, full_path)
                item.setData(0, Qt.UserRole + 1, True)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Unchecked)

                parent_item.addChild(item)
                self.total_dirs += 1

                self._add_children(item, full_path)

            else:
                item = QTreeWidgetItem([name])
                item.setData(0, Qt.UserRole, full_path)
                item.setData(0, Qt.UserRole + 1, False)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Unchecked)

                parent_item.addChild(item)
                self.total_files += 1

    # -----------------------
    # Работа с чекбоксами
    # -----------------------

    def on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if not self.project_path:
            return

        self.tree.blockSignals(True)

        state = item.checkState(0)
        is_dir = bool(item.data(0, Qt.UserRole + 1))

        if is_dir:
            self._set_children_check_state(item, state)

        self._update_parent_states(item)

        self.tree.blockSignals(False)

        self.recalc_selection_stats()
        self.update_export_buttons_state()

    def _set_children_check_state(self, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
            if child.childCount() > 0:
                self._set_children_check_state(child, state)

    def _update_parent_states(self, item: QTreeWidgetItem) -> None:
        parent = item.parent()
        if parent is None:
            return

        checked_count = 0
        partial_count = 0
        child_count = parent.childCount()

        for i in range(child_count):
            child = parent.child(i)
            st = child.checkState(0)
            if st == Qt.Checked:
                checked_count += 1
            elif st == Qt.PartiallyChecked:
                partial_count += 1

        if checked_count == child_count:
            parent.setCheckState(0, Qt.Checked)
        elif checked_count == 0 and partial_count == 0:
            parent.setCheckState(0, Qt.Unchecked)
        else:
            parent.setCheckState(0, Qt.PartiallyChecked)

        self._update_parent_states(parent)

    # -----------------------
    # Подсчёт выбранных файлов и групп
    # -----------------------

    def recalc_selection_stats(self) -> None:
        if not self.tree.topLevelItemCount() or not self.project_path:
            self.selected_files = 0
            self.selected_groups_count = 0
            self.update_summary()
            return

        selected_files = 0
        selected_groups: set[str] = set()

        root = self.tree.topLevelItem(0)

        def walk(item: QTreeWidgetItem) -> None:
            nonlocal selected_files
            for i in range(item.childCount()):
                child = item.child(i)
                is_dir = bool(child.data(0, Qt.UserRole + 1))
                full_path = child.data(0, Qt.UserRole)
                state = child.checkState(0)

                if is_dir:
                    walk(child)
                else:
                    if state == Qt.Checked and isinstance(full_path, str):
                        selected_files += 1
                        dir_path = os.path.dirname(full_path)
                        rel_dir = os.path.relpath(dir_path, self.project_path)
                        if rel_dir == ".":
                            rel_dir = "(корень проекта)"
                        selected_groups.add(rel_dir)

        walk(root)

        self.selected_files = selected_files
        self.selected_groups_count = len(selected_groups)
        self.update_summary()

    # -----------------------
    # Сбор всех выбранных файлов (относительный + абсолютный путь)
    # -----------------------

    def _collect_selected_files(self) -> list[tuple[str, str]]:
        if not self.project_path or not self.tree.topLevelItemCount():
            return []

        root = self.tree.topLevelItem(0)
        result: list[tuple[str, str]] = []

        def walk(item: QTreeWidgetItem) -> None:
            for i in range(item.childCount()):
                child = item.child(i)
                is_dir = bool(child.data(0, Qt.UserRole + 1))
                abs_path = child.data(0, Qt.UserRole)
                state = child.checkState(0)

                if is_dir:
                    walk(child)
                else:
                    if state == Qt.Checked and isinstance(abs_path, str):
                        rel_path = os.path.relpath(abs_path, self.project_path)
                        result.append((rel_path, abs_path))

        walk(root)
        return result

    # -----------------------
    # Формирование имени TXT-файла для группы
    # -----------------------

    def _make_group_filename(self, dir_key: str) -> str:
        if dir_key in ("", ".", "(корень проекта)"):
            base = os.path.basename(self.project_path.rstrip(os.sep)) or "root"
        else:
            base = dir_key.replace(os.sep, "-")

        safe_chars = "-_.() []{}"
        cleaned = []
        for ch in base:
            if ch.isalnum() or ch in safe_chars:
                cleaned.append(ch)
            else:
                cleaned.append("_")
        base_clean = "".join(cleaned).strip("._ ")
        if not base_clean:
            base_clean = "group"

        return base_clean + ".txt"

    # -----------------------
    # Безопасное чтение файла (текст / бинарники)
    # -----------------------

    def _read_file_safe(self, path: str) -> tuple[str, bool]:
        try:
            with open(path, "rb") as f:
                chunk = f.read(2048)
                if b"\x00" in chunk:
                    return "<<Бинарный файл, содержимое пропущено>>", True
        except OSError as e:
            return f"<<Ошибка чтения файла: {e}>>", False

        encodings = ("utf-8", "utf-8-sig", "cp1251", "cp866")

        for enc in encodings:
            try:
                with open(path, "r", encoding=enc) as f:
                    return f.read(), False
            except UnicodeDecodeError:
                continue
            except OSError as e:
                return f"<<Ошибка чтения файла: {e}>>", False

        try:
            with open(path, "rb") as f:
                data = f.read()
            return data.decode("utf-8", errors="replace"), False
        except OSError as e:
            return f"<<Ошибка чтения файла: {e}>>", False

    # -----------------------
    # Заголовок для TXT-файлов (инструкция для нейросетей)
    # -----------------------

    def _write_export_header(self, out) -> None:
        out.write(
            "ЭТОТ TXT-ФАЙЛ СФОРМИРОВАН АВТОМАТИЧЕСКИ ДЛЯ НЕЙРОСЕТЕЙ.\n"
            "\n"
            "Формат данных:\n"
            "- каждый блок соответствует одному исходному файлу проекта;\n"
            "- первая строка блока — относительный путь файла в проекте;\n"
            "- далее идёт исходное содержимое файла без изменений;\n"
            "- блоки разделяются строкой-маркером:\n"
            "  ===END OF THE FILE===\n"
            "\n"
            "Пожалуйста, при анализе кода опирайся на путь файла и номера строк,\n"
            "а маркер разделения воспринимай только как границу между файлами.\n"
            "\n"
        )

    # -----------------------
    # ЭКСПОРТ — ПО ГРУППАМ (как раньше)
    # -----------------------

    def start_export_grouped(self) -> None:
        if not self.project_path:
            self.statusBar().showMessage("Сначала выберите папку проекта.")
            self.log.append("[ERROR] Проект не выбран.")
            return

        if not self.export_path:
            self.statusBar().showMessage("Выберите папку для TXT.")
            self.log.append("[ERROR] Папка для TXT не выбрана.")
            return

        files = self._collect_selected_files()
        if not files:
            self.statusBar().showMessage("Нет выбранных файлов для экспорта.")
            self.log.append("[WARN] Нет выбранных файлов.")
            return

        groups: dict[str, list[tuple[str, str]]] = {}
        for rel_path, abs_path in files:
            dir_key = os.path.dirname(rel_path)
            if dir_key == ".":
                dir_key = ""
            groups.setdefault(dir_key, []).append((rel_path, abs_path))

        total_files = len(files)
        self.progress.setMaximum(total_files)
        self.progress.setValue(0)
        done_files = 0

        self.log.append(
            f"[INFO] Экспорт (по папкам). Групп: {len(groups)}, файлов: {total_files}."
        )

        for dir_key, file_list in groups.items():
            group_filename = self._make_group_filename(dir_key)
            target_path = os.path.join(self.export_path, group_filename)

            self.log.append(
                f"[INFO] Группа '{dir_key or '(корень проекта)'}' → {group_filename} "
                f"({len(file_list)} файлов)."
            )

            try:
                with open(target_path, "w", encoding="utf-8") as out:
                    # шапка для нейросети
                    self._write_export_header(out)

                    for index, (rel_path, abs_path) in enumerate(file_list):
                        rel_unix = rel_path.replace(os.sep, "/")

                        out.write(rel_unix + "\n\n")

                        content, is_binary = self._read_file_safe(abs_path)
                        out.write(content)

                        if index != len(file_list) - 1:
                            out.write("\n\n" + self.FILE_SEPARATOR + "\n\n")

                        done_files += 1
                        self.progress.setValue(done_files)
                        QApplication.processEvents()

                        out.write(rel_unix + "\n\n")

                        content, is_binary = self._read_file_safe(abs_path)
                        out.write(content)

                        if index != len(file_list) - 1:
                            out.write("\n\n" + "-" * 80 + "\n\n")

                        done_files += 1
                        self.progress.setValue(done_files)
                        QApplication.processEvents()
            except OSError as e:
                self.log.append(f"[ERROR] Не удалось записать '{target_path}': {e}")

        self.progress.setValue(self.progress.maximum())
        msg = (
            f"Экспорт по папкам завершён. TXT файлов: {len(groups)}, файлов внутри: {done_files}."
        )
        self.statusBar().showMessage(msg)
        self.log.append("[INFO] " + msg)

    # -----------------------
    # ЭКСПОРТ — В ОДИН ФАЙЛ
    # -----------------------

    def start_export_single(self) -> None:
        if not self.project_path:
            self.statusBar().showMessage("Сначала выберите папку проекта.")
            self.log.append("[ERROR] Проект не выбран (один файл).")
            return

        if not self.export_path:
            self.statusBar().showMessage("Выберите папку для TXT.")
            self.log.append("[ERROR] Папка для TXT не выбрана (один файл).")
            return

        files = self._collect_selected_files()
        if not files:
            self.statusBar().showMessage("Нет выбранных файлов для экспорта.")
            self.log.append("[WARN] Нет выбранных файлов (один файл).")
            return

        files_sorted = sorted(files, key=lambda x: x[0])

        total_files = len(files_sorted)
        self.progress.setMaximum(total_files)
        self.progress.setValue(0)

        project_name = os.path.basename(self.project_path.rstrip(os.sep)) or "project"
        target_name = project_name + "_all.txt"
        target_path = os.path.join(self.export_path, target_name)

        self.log.append(
            f"[INFO] Экспорт в один файл: {target_name} (файлов: {total_files})."
        )

        done_files = 0
        try:
            with open(target_path, "w", encoding="utf-8") as out:
                # шапка для нейросети (главное именно здесь, для общего файла)
                self._write_export_header(out)

                for index, (rel_path, abs_path) in enumerate(files_sorted):
                    rel_unix = rel_path.replace(os.sep, "/")
                    out.write(rel_unix + "\n\n")

                    content, is_binary = self._read_file_safe(abs_path)
                    out.write(content)

                    if index != len(files_sorted) - 1:
                        out.write("\n\n" + self.FILE_SEPARATOR + "\n\n")

                    done_files += 1
                    self.progress.setValue(done_files)
                    QApplication.processEvents()

                    done_files += 1
                    self.progress.setValue(done_files)
                    QApplication.processEvents()
        except OSError as e:
            self.log.append(f"[ERROR] Не удалось записать '{target_path}': {e}")
            self.statusBar().showMessage("Ошибка записи TXT.")
            return

        self.progress.setValue(self.progress.maximum())
        msg = (
            f"Экспорт в один файл завершён. Файлов внутри: {done_files}. "
            f"Файл: {target_name}"
        )
        self.statusBar().showMessage(msg)
        self.log.append("[INFO] " + msg)


# -----------------------
# ТЕМА
# -----------------------

def setup_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")

    bg = QColor("#2E3440")
    fg = QColor("#ECEFF4")
    accent = QColor("#20C997")

    palette = QPalette()
    palette.setColor(QPalette.Window, bg)
    palette.setColor(QPalette.WindowText, fg)
    palette.setColor(QPalette.Base, bg)
    palette.setColor(QPalette.AlternateBase, bg)
    palette.setColor(QPalette.Text, fg)
    palette.setColor(QPalette.Button, bg)
    palette.setColor(QPalette.ButtonText, fg)
    palette.setColor(QPalette.Highlight, accent)
    palette.setColor(QPalette.HighlightedText, QColor("#0F1113"))

    app.setPalette(palette)

    app.setStyleSheet(f"""
        QWidget {{
            background-color: {bg.name()};
            color: {fg.name()};
            font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
            font-size: 10pt;
        }}

        QMainWindow {{
            background-color: {bg.name()};
        }}

        #HeaderSubtitle {{
            color: #B5BDC5;
        }}

        #SectionHint {{
            color: #A0A7AF;
        }}

        QLabel[section_title="true"] {{
            font-size: 10pt;
            font-weight: 600;
        }}

        QLabel[section_title_small="true"] {{
            font-size: 9pt;
            font-weight: 500;
            color: #B0B6BD;
        }}

        QFrame[card_soft="true"] {{
            background-color: transparent;
            border-radius: 12px;
            border: 1px solid #3E4550;
        }}

        #TopDivider {{
            color: #3E4550;
            background-color: #3E4550;
            max-height: 1px;
        }}

        QPushButton {{
            background-color: #3B4252;
            border-radius: 8px;
            padding: 6px 16px;
            border: 1px solid #4C566A;
        }}

        QPushButton:hover {{
            background-color: #434C5E;
            border-color: {accent.name()};
        }}

        QPushButton:pressed {{
            background-color: #2F3744;
            border-color: #16A085;
        }}

        QPushButton[accent="true"] {{
            background-color: {accent.name()};
            color: #0D1115;
            border: none;
            font-weight: bold;
        }}

        QPushButton[accent="true"]:hover:enabled {{
            background-color: #21D3A0;
        }}

        QPushButton[accent="true"]:disabled {{
            background-color: #3B4252;
            color: #6B7280;
            border: 1px solid #4C566A;
        }}

        QPushButton[secondary="true"] {{
            background-color: transparent;
            border-radius: 8px;
            padding: 6px 16px;
            border: 1px solid #4C566A;
            color: #E5E9F0;
        }}

        QPushButton[secondary="true"]:hover:enabled {{
            background-color: #3B4252;
            border-color: #7C848E;
        }}

        QPushButton[secondary="true"]:disabled {{
            color: #6B7280;
            border-color: #4C566A;
        }}

        QPushButton[pill="true"] {{
            border-radius: 999px;
        }}

        QPushButton[pill_secondary="true"] {{
            border-radius: 999px;
            background-color: transparent;
            border: 1px solid #5B636D;
            color: #E0E5EA;
        }}

        QPushButton[pill_secondary="true"]:hover {{
            background-color: #3B4252;
            border-color: #7C848E;
        }}

        QTreeWidget {{
            background-color: transparent;
            border: none;
        }}

        QTreeView::item {{
            padding: 3px 4px;
        }}

        QTreeView::item:selected {{
            background-color: transparent;
            color: inherit;
        }}

        QTreeView::indicator {{
            width: 15px;
            height: 15px;
            border-radius: 4px;
        }}

        QTreeView::indicator:unchecked {{
            border: 2px solid #D8DEE9;
            background-color: transparent;
        }}

        QTreeView::indicator:unchecked:hover {{
            border: 2px solid {accent.name()};
            background-color: #2E4E46;
        }}

        QTreeView::indicator:checked {{
            border: none;
            background-color: {accent.name()};
        }}

        QTreeView::indicator:indeterminate {{
            border: none;
            background-color: #0F7F63;
        }}

        QTextEdit {{
            background-color: #3B4252;
            border-radius: 10px;
            border: 1px solid #4C566A;
            padding: 6px;
        }}

        QProgressBar {{
            background-color: #3B4252;
            border-radius: 4px;
            height: 6px;
        }}

        QProgressBar::chunk {{
            background-color: {accent.name()};
            border-radius: 4px;
        }}

        QStatusBar {{
            background-color: {bg.name()};
            border-top: 1px solid #3E4550;
            color: #C7CCD1;
            font-size: 9pt;
        }}
    """)


# -----------------------
# ТОЧКА ВХОДА
# -----------------------

def main() -> None:
    app = QApplication(sys.argv)
    setup_dark_theme(app)

    w = MainWindow()
    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()