import os
import sys
import mdv
import time
import readline
import logging
import threading
from typing import Dict, List

logger = logging.getLogger(__name__)

class Display:
    min_boarder_len: int = 20

    welcome_msg: str = \
"""
================================================
  ___ _       ___ _         _    ___ ___ _____ 
 / __(_)_ __ / __| |_  __ _| |_ / __| _ \_   _|
 \__ \ | '  \ (__| ' \/ _` |  _| (_ |  _/ | |  
 |___/_|_|_|_\___|_||_\__,_|\__|\___|_|   |_|  
================================================                                              
"""
    def __init__(self):
        terminal_width = os.get_terminal_size().columns
        welcome_msg_width = len(self.welcome_msg.split()[0])
        if terminal_width < welcome_msg_width:
            self.system_output({
                "role": "system",
                "content": f"Change terminal width to no less than {welcome_msg_width} to get a better experience."
            })
        else:
            print(self.welcome_msg, end='')

    def _print_boarder(self):
        terminal_size = os.get_terminal_size()
        width = terminal_size.columns
        print('=' * width + '\n')

    def _print_header(self, head_name: str):
        role = f"# {head_name.upper()} >"
        role += ' ' * (self.min_boarder_len - len(role) + 2) if len(role) <= self.min_boarder_len + 2 else role
        role += "\n\n"
        print(mdv.main(role), end='')

    def user_output(self):
        self._print_header("user")
    
    def system_output(self, output: Dict[str, str]):
        self._print_header(output['role'])
        content = output['content']
        content = content[2:] if content.startswith('\n\n') else content
        content += "\n\n"
        formated = mdv.main(content)
        print(formated, end='')
    
    def log_statistics(self, statistics: Dict[str, int]):
        logger.info(statistics)

    def get_input(self, msg: str) -> str:
        return input(f"  {msg}: ")

    def waiting(self):
        class ComVar:
            def __init__(self):
                self.stop_flag = False
                self.display_postfix = ""
        com_var = ComVar()
        def start_rotation():
            print_i = 0
            print_tokens = ["|", "/", "-", "\\"]
            while not com_var.stop_flag:
                print(f"{print_tokens[print_i % 4]}{com_var.display_postfix}\r", end='')
                time.sleep(0.2)
                print_i += 1
            sys.stdout.write("\033[K") # 清空当前行
        t = threading.Thread(target=start_rotation)
        t.start()
        def waiting_callback(stop: bool = False, postfix: str = ""):
            com_var.stop_flag = stop
            com_var.display_postfix = postfix
            if stop:
                t.join()
        return waiting_callback

    def clear_screen(self):
        os.system("cls" if os.name == "nt" else "clear")
    
    def show_context(self, context: List[Dict[str, str]]):
        for line in context:
            self._print_header(line['role'])
            content = line["content"]
            content = content[2: ] if content.startswith("\n\n") else content
            content += "\n\n"
            print(mdv.main(content))