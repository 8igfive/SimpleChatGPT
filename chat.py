import openai
import threading
import os
import sys
import mdv
import time
import json
import logging
import argparse
import readline
from typing import List, Dict, Tuple

OPENAI_API_TOKEN = "" # You can place your OPENAI_API_KEY here.
PROGRAM_NAME = "Simple ChatGPT"
MODELS = ["gpt-3.5-turbo", "gpt-3.5-turbo-0301"]
ACTIONS = ["help", "cache", "quit", "save", "load", "back", "clear", "change"]
ACTION2DESCRIPTION = {
    "help": "Show available actions.", 
    "cache": "Show context cache.",
    "quit": f"Quit {PROGRAM_NAME}.",
    "save": "Save context cache.",
    "load": "Load context cache.", 
    "back": "Return to last context.",
    "clear": "Clear the whole context.", 
    "change": "Change used model."
}
DUMP_DIR = "dump"
logger = logging.getLogger(__name__)


class Context:
    cache: List[Dict[str, str]]
    num_tokens: Dict[str, int]
    
    def __init__(self, cache_path: str = None):
        if cache_path:
            self.load(cache_path)
        else:
            logger.info("Initialize empty cache.")
            self.cache = []

        self.num_tokens = {
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "total_tokens": 0
        }

    def get_context(self) -> List[Dict[str, str]]:
        return self.cache

    def get_last_line(self) -> Dict[str, str]:
        return self.cache[-1]

    def cache_backward(self, n: int = 0, all: bool = False):
        if all:
            self.cache.clear()
        else:
            for i in range(n):
                self.cache.pop()

    def add_user_input(self, user_input):
        self.cache.append(user_input)

    def add_response(self, response):
        try:
            for choice in response.choices:
                if "message" in choice:
                    self.cache.append({
                        "role": choice["message"]["role"],
                        "content": choice["message"]["content"]
                    })
            for key, value in response.usage.items():
                self.num_tokens[key] += value
        except Exception as e:
            logger.error(f"Error occured when updating:\n{e}\n")
            raise Exception("Cannot parse response.")

    def dump(self, dump_dir: str):
        try:
            if not dump_dir:
                dump_dir = DUMP_DIR
            os.makedirs(DUMP_DIR, exist_ok=True)
            dump_path = os.path.join(DUMP_DIR, time.strftime("%a-%b-%d-%H:%M:%S-%Y", time.localtime()))

            with open(dump_path, 'w', encoding="utf8") as fo:
                json.dump(self.cache, fo)
        except Exception as e:
            logger.error(f"Error occured when dumping:\n{e}\n")
            raise Exception("Cannot dump context cache.")

    def load(self, cache_path: str):
        try:
            with open(cache_path, 'r', encoding='utf8') as fi:
                cache = json.load(fi)
                assert isinstance(cache, list) and \
                        (len(cache) == 0 or all(map(lambda x: isinstance(x, dict), cache))), \
                        "Cache should be List[Dict[str, str]]"
                self.cache = cache
        except Exception as e:
            logger.error(f"Error occured when loading cache:\n{e}\n")
            raise Exception("Cannot load cache.")

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
        class StopFlag:
            def __init__(self):
                self.stop_flag = False
        stop_flag = StopFlag()
        def start_rotation():
            print_i = 0
            print_tokens = ["|", "/", "-", "\\"]
            while not stop_flag.stop_flag:
                print(f"{print_tokens[print_i % 4]}\r", end='')
                time.sleep(0.2)
                print_i += 1
            sys.stdout.write("\033[K") # 清空当前行
        t = threading.Thread(target=start_rotation)
        t.start()
        def end_rotation():
            stop_flag.stop_flag = True
            t.join()
        return end_rotation

    def clear_screen(self):
        os.system("cls" if os.name == "nt" else "clear")
    
    def show_context(self, context: List[Dict[str, str]]):
        for line in context:
            self._print_header(line['role'])
            content = line["content"]
            content = content[2: ] if content.startswith("\n\n") else content
            content += "\n\n"
            print(mdv.main(content))
        
 
class Client:
    def __init__(self, api_key: str, model: str, dump_dir: str = None, cache_path: str = None, ):
        openai.api_key = api_key
        self.model = model
        self.dump_dir = dump_dir
        self.context = Context(cache_path)
        self.display = Display()

    
    def _get_input(self) -> str:
        total_input = []
        step_input = input("  ")
        while step_input:
            total_input.append(step_input)
            step_input = input()
        print('')
        return '\n'.join(total_input)

    def _request(self):
        try:
            return openai.ChatCompletion.create(
                model=self.model,
                messages=self.context.get_context()
            )
        except Exception as e:
            logger.error(f"Error occured when sending request:\n{e}\n")

    def _step_input(self) -> Tuple[Dict[str, str], int]:
        self.display.user_output()
        user_input = self._get_input()

        if rf"\{ACTIONS[0]}".startswith(user_input): # help
            return {"role": "Kernel", "content": "\n\n" + \
                    '\n'.join(map(lambda action: f"+ {action}: {ACTION2DESCRIPTION[action]}", ACTIONS))}, 0
        elif rf"\{ACTIONS[1]}".startswith(user_input): # cache
            return {"role": "Kernel", "content": "\n\nShow cache."}, 0 # TODO: implement show cache
        elif rf"\{ACTIONS[2]}".startswith(user_input): # quit
            return {"role": "Kernel", "content": "\n\nQuit."}, 1
        elif rf"\{ACTIONS[3]}".startswith(user_input): # save
            dump_dir = self.dump_dir
            if not dump_dir:
                dump_dir = self.display.get_input("Specify a dump directory")
            self.context.dump(dump_dir)
            return {"role": "Kernel", "content": "\n\nCache saved."}, 0
        elif rf"\{ACTIONS[4]}".startswith(user_input): # load
            cache_path = self.display.get_input("Specify a cache path")
            self.context.load(cache_path)
            self.display.clear_screen()
            self.display.show_context(self.context.get_context())
            return {"role": "Kernel", "content": "\n\nContext is changed."}, 0
        elif rf"\{ACTIONS[5]}".startswith(user_input): # back
            self.context.cache_backward(n=2)
            self.display.clear_screen()
            self.display.show_context(self.context.get_context())
            return {"role": "Kernel", "content": "\n\nNow at last context."}, 0
        elif rf"\{ACTIONS[6]}".startswith(user_input): # clear
            self.context.cache_backward(all=True)
            self.display.clear_screen()
            return {"role": "Kernel", "content": "\n\nNow at a new context."}, 0
        elif rf"\{ACTIONS[7]}".startswith(user_input): # change
            model = self.display.get_input(f"Specify a model within [{', '.join(MODELS)}]")
            self.model = model
            return {"role": "Kernel", "content": "\n\nModel is changed."}, 0
        else:
            self.context.add_user_input({
                "role": "user",
                "content": user_input
            })
            waiting_callback = self.display.waiting()
            try:
                response = self._request()
                # time.sleep(0.5)
                self.context.add_response(response)
                last_line = self.context.get_last_line()
            except Exception as e:
                logger.error(f"Error occured when processing request:\n{e}\n")
                self.context.cache_backward(n=1)
                last_line = {"role": "Kernel", "content": "\n\nError receiving response from openai."}
            finally:
                waiting_callback()
            return last_line, 0


    def _step_output(self, output: Dict[str, str]):
        self.display.system_output(output)

    def _exit(self):
        self.display.log_statistics(self.context.num_tokens)

    def start(self):
        
        while True:
            output, code = self._step_input()
            self._step_output(output)
            if code:
                break

        self._exit()


def main():
    parser = argparse.ArgumentParser(PROGRAM_NAME)
    parser.add_argument("-k", "--api_key", type=str, default=OPENAI_API_TOKEN,
                        help="OpenAI API KEY.")
    parser.add_argument("-m", "--model", type=str, choices=MODELS, default=MODELS[0],
                        help="Model to use.")
    parser.add_argument("-d", "--dump_dir", type=str, default=DUMP_DIR,
                        help="Directory to save context cache.")
    parser.add_argument("-c", "--cache_path", type=str, default=None, 
                        help="Path to load context path")

    args = parser.parse_args()

    client = Client(args.api_key, args.model, args.dump_dir, args.cache_path)
    client.start()

if __name__ == "__main__":
    main()