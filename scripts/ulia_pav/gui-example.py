import random
import time
from typing import Callable

from gui import ParsingApp
import tkinter as tk

def process_article(source_path: str, target_path: str, logger_func: Callable[[str], None]):
    '''функция-заглушка для демонстрации'''
    logger_func(f"Processing article: {source_path}")
    
    if random.random() < 0.25:
        raise ValueError("Random simulation error")
    
    time.sleep(1)


if __name__ == "__main__":
    root = tk.Tk()
    root.tk.call('encoding', 'system', 'utf-8')
    app = ParsingApp(root, process_article)
    root.mainloop()