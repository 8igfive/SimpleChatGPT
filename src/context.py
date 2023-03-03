import os
import time
import json
import logging
from typing import List, Dict
from . import DUMP_DIR

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
                json.dump(self.cache, fo, indent=4, ensure_ascii=False)
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