import os
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable


class ParsingApp:
    def __init__(
        self,
        root: tk.Tk,
        process_func: Callable[[str, str, Callable[[str], None]], None],
    ):
        self._root = root
        self._root.title("Парсинг статей")

        self.style = ttk.Style()
        self.style.theme_use('clam')

        self._process_func = process_func
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

        self._source_var = tk.StringVar()
        self._target_var = tk.StringVar()

        self._build_ui()
        self._validate_source()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self._root, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        self._build_folder_row(frame, "Каталог статей:", self._source_var, 0)
        self._build_folder_row(frame, "Каталог результатов:", self._target_var, 1)

        self._progress = ttk.Progressbar(frame, mode="determinate")
        self._progress.grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=5)

        self._btn_start = ttk.Button(frame, text="Start", command=self._on_start)
        self._btn_start.grid(row=3, column=0, columnspan=3, pady=5)

        self._log_text = tk.Text(frame, height=10, state=tk.DISABLED, wrap=tk.WORD)
        self._log_text.grid(row=4, column=0, columnspan=3, sticky=tk.NSEW, pady=5)

        log_btn_frame = ttk.Frame(frame)
        log_btn_frame.grid(row=5, column=0, columnspan=3, sticky=tk.E)

        ttk.Button(log_btn_frame, text="Очистить", command=self._on_clear).pack(side=tk.LEFT, padx=2)
        ttk.Button(log_btn_frame, text="Сохранить", command=self._on_save).pack(side=tk.LEFT, padx=2)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

    def _build_folder_row(
        self,
        parent: ttk.Frame,
        label_text: str,
        var: tk.StringVar,
        row: int,
    ) -> None:
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky=tk.W)
        ttk.Entry(parent, textvariable=var, state="readonly").grid(
            row=row, column=1, sticky=tk.EW, padx=5
        )
        ttk.Button(
            parent,
            text="Выбрать",
            command=lambda: self._choose_folder(var),
        ).grid(row=row, column=2)

    def _choose_folder(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory()
        if path:
            var.set(path)
            self._validate_source()

    def _validate_source(self) -> None:
        source = self._source_var.get()
        has_files = bool(source) and bool(os.listdir(source))
        self._btn_start.config(state=tk.NORMAL if has_files else tk.DISABLED)

    def _on_start(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            self._stop_event.set()
            self._btn_start.config(text="Stopping...", state=tk.DISABLED)
            return

        source = self._source_var.get()
        target = self._target_var.get()

        if not source or not target:
            messagebox.showerror("Error", "Select both source and target folders")
            return

        if not os.path.isdir(source):
            messagebox.showerror("Error", f"Source folder does not exist: {source}")
            return

        if not os.path.isdir(target):
            messagebox.showerror("Error", f"Target folder does not exist: {target}")
            return

        files = [
            os.path.join(source, f)
            for f in os.listdir(source)
            if os.path.isfile(os.path.join(source, f))
        ]

        if not files:
            messagebox.showwarning("Warning", "Source folder is empty")
            return

        files.sort()
        self._stop_event.clear()
        self._progress["maximum"] = len(files)
        self._progress["value"] = 0
        self._btn_start.config(text="Stop", command=self._on_stop)

        self._worker_thread = threading.Thread(
            target=self._run_parsing, args=(files, target), daemon=True
        )
        self._worker_thread.start()

    def _run_parsing(self, files: list[str], target: str) -> None:
        for src_path in files:
            if self._stop_event.is_set():
                self._root.after(0, self._log, "Парсинг остановлен пользователем")
                break

            filename = os.path.basename(src_path)
            target_path = os.path.join(target, filename)

            def logger(msg: str) -> None:
                self._root.after(0, self._log, msg)

            try:
                self._process_func(src_path, target_path, logger)
            except Exception as e:
                self._root.after(0, self._log, f"Ошибка: {e}")

            self._root.after(0, lambda: self._progress.step(1))

        self._root.after(0, self._on_finished)

    def _on_finished(self) -> None:
        self._btn_start.config(text="Start", command=self._on_start)
        self._log("Готово")
        self._btn_start.config(state=tk.NORMAL)

    def _on_stop(self) -> None:
        self._stop_event.set()
        self._btn_start.config(text="Stopping...", state=tk.DISABLED)

    def _log(self, message: str) -> None:
        self._log_text.config(state=tk.NORMAL)
        self._log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self._log_text.see(tk.END)
        self._log_text.config(state=tk.DISABLED)

    def _on_clear(self) -> None:
        self._log_text.config(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.config(state=tk.DISABLED)

    def _on_save(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            with open(path, "w") as f:
                f.write(self._log_text.get("1.0", tk.END))
