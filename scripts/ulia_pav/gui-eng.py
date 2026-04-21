import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional
import threading


class ParsingApp:
    def __init__(
        self,
        root: tk.Tk,
        process_func: Callable[[str, str, Callable[[str], None]], None]
    ) -> None:
        self.root = root
        self.process_func = process_func
        self.source_path: Optional[str] = None
        self.target_path: Optional[str] = None
        self.is_running: bool = False
        self.stop_flag: threading.Event = threading.Event()
        self.style = ttk.Style()
        self.style.theme_use('clam')

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.root.title("Article Parsing")
        self.root.geometry("600x500")

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        source_label = tk.Label(main_frame, text="Articles folder:")
        source_label.grid(row=0, column=0, sticky=tk.W, pady=5)

        self.source_btn = ttk.Button(
            main_frame,
            text="Select folder",
            command=self._select_source
        )
        self.source_btn.grid(row=0, column=1, pady=5)

        self.source_path_label = ttk.Label(main_frame, text="")
        self.source_path_label.grid(row=0, column=2, sticky=tk.W, padx=5)

        target_label = ttk.Label(main_frame, text="Target folder:")
        target_label.grid(row=1, column=0, sticky=tk.W, pady=5)

        self.target_btn = ttk.Button(
            main_frame,
            text="Select folder",
            command=self._select_target
        )
        self.target_btn.grid(row=1, column=1, pady=5)

        self.target_path_label = ttk.Label(main_frame, text="")
        self.target_path_label.grid(row=1, column=2, sticky=tk.W, padx=5)

        self.start_btn = ttk.Button(
            main_frame,
            text="Start",
            command=self._toggle_parsing,
            state=tk.DISABLED
        )
        self.start_btn.grid(row=2, column=0, columnspan=2, pady=10)

        progress_label = ttk.Label(main_frame, text="Progress:")
        progress_label.grid(row=3, column=0, sticky=tk.W, pady=5)

        self.progress_bar = ttk.Progressbar(
            main_frame,
            mode="determinate",
            length=400
        )
        self.progress_bar.grid(row=3, column=1, columnspan=2, pady=5)

        self.progress_label = ttk.Label(main_frame, text="0 / 0")
        self.progress_label.grid(row=4, column=1, columnspan=2, pady=5)

        log_label = ttk.Label(main_frame, text="Log:")
        log_label.grid(row=5, column=0, sticky=tk.W, pady=5)

        self.log_text = tk.Text(main_frame, width=70, height=15)
        self.log_text.grid(row=6, column=0, columnspan=3, pady=5)

        log_scroll = ttk.Scrollbar(
            main_frame,
            orient=tk.VERTICAL,
            command=self.log_text.yview
        )
        log_scroll.grid(row=6, column=3, sticky=(tk.N, tk.S))
        self.log_text.config(yscrollcommand=log_scroll.set)

        log_btn_frame = ttk.Frame(main_frame)
        log_btn_frame.grid(row=7, column=0, columnspan=3, pady=5)

        self.save_log_btn = ttk.Button(
            log_btn_frame,
            text="Save",
            command=self._save_log
        )
        self.save_log_btn.pack(side=tk.LEFT, padx=5)

        self.clear_log_btn = ttk.Button(
            log_btn_frame,
            text="Clear",
            command=self._clear_log
        )
        self.clear_log_btn.pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(2, weight=1)

    def _select_source(self) -> None:
        path = filedialog.askdirectory(title="Select articles folder")
        if path:
            self.source_path = path
            self.source_path_label.config(text=path)
            self._validate_folders()

    def _select_target(self) -> None:
        path = filedialog.askdirectory(title="Select target folder")
        if path:
            self.target_path = path
            self.target_path_label.config(text=path)
            self._validate_folders()

    def _validate_folders(self) -> None:
        if self.source_path and self.target_path:
            if os.path.isdir(self.source_path) and os.path.isdir(self.target_path):
                files = [f for f in os.listdir(self.source_path)
                         if os.path.isfile(os.path.join(self.source_path, f))]
                if files:
                    self.start_btn.config(state=tk.NORMAL)
                    return
        self.start_btn.config(state=tk.DISABLED)

    def _toggle_parsing(self) -> None:
        if self.is_running:
            self.stop_flag.set()
        else:
            self._start_parsing()

    def _start_parsing(self) -> None:
        if not self.source_path or not self.target_path:
            return

        files = [f for f in os.listdir(self.source_path)
                 if os.path.isfile(os.path.join(self.source_path, f))]
        total = len(files)

        if total == 0:
            messagebox.showwarning("Warning", "Folder is empty")
            return

        self.is_running = True
        self.stop_flag.clear()
        self.start_btn.config(text="Stop")

        def log_func(message: str) -> None:
            self.root.after(0, lambda msg=message: self._append_log(msg))

        def worker() -> None:
            for i, filename in enumerate(files):
                if self.stop_flag.is_set():
                    self.root.after(0, self._parsing_stopped)
                    return

                source_file = os.path.join(self.source_path, filename)
                target_file = os.path.join(self.target_path, filename)

                try:
                    self.process_func(source_file, target_file, log_func)
                except Exception as e:
                    err_msg = str(e)
                    self.root.after(0, lambda: self._append_log(f"Error: {err_msg}"))

                current_num = i + 1
                self.root.after(0, lambda cur=current_num, tot=total: self._update_progress(cur, tot))

            self.root.after(0, self._parsing_complete)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _update_progress(self, current: int, total: int) -> None:
        self.progress_bar["value"] = (current / total) * 100
        self.progress_label.config(text=f"{current} / {total}")

    def _append_log(self, message: str) -> None:
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def _save_log(self) -> None:
        content = self.log_text.get("1.0", tk.END)
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

    def _clear_log(self) -> None:
        self.log_text.delete("1.0", tk.END)

    def _parsing_stopped(self) -> None:
        self.is_running = False
        self.start_btn.config(text="Start")
        self._append_log("Parsing stopped")

    def _parsing_complete(self) -> None:
        self.is_running = False
        self.start_btn.config(text="Start")
        self._append_log("Parsing complete")
        messagebox.showinfo("Done", "Article parsing complete")