import abc
import inflect
import openai
import logging
from typing import Dict, Tuple, List
from .context import Context
from .display import Display
from . import MODELS

logger = logging.getLogger(__name__)
inflect_engine = inflect.engine()


class BasicCommand:
    args_check_error_template: str = "\n\nArgument number for command {}"
    def __init__(self, opcode: str, *args: List[str]):
        self.opcode = opcode
        self.args = args

    @abc.abstractmethod    
    def handle(self, client, context: Context, display: Display) -> Dict[str, str]:
        pass

class Factory:
    commands: List[str] = []
    command2description: Dict[str, str] = {}
    registry: Dict[str, BasicCommand] = {}

    @classmethod
    def _get_command(cls, op: str) -> str:
        for command in cls.commands:
            if command.startswith(op):
                return command
        return ""

    @classmethod
    def register(cls, cmd_name: str, cmd_description: str):
        def inner_wrapper(wrapper: BasicCommand):
            cls.commands.append(cmd_name)
            cls.registry[cmd_name] = wrapper
            cls.command2description[cmd_name] = cmd_description
            return wrapper
        return inner_wrapper

    @classmethod
    def create_cmd(cls, cmdstr: str):
        tokens = cmdstr.split()
        if tokens:
            op, args = tokens[0], tokens[1:]
        else:
            op, args = "", []
        command = cls._get_command(op)
        if command:
            exec_class = cls.registry[command]
            cmd  = exec_class(command,*args)
        else:
            exec_class = cls.registry[cls.commands[-1]]
            cmd = exec_class(cls.commands[-1], cmdstr) # send
        return cmd


class Client:
    def __init__(self, api_key: str, model: str, retry: int = 1, dump_dir: str = None, cache_path: str = None):
        openai.api_key = api_key
        self.model = model
        self.retry = retry
        self.dump_dir = dump_dir
        self.context = Context(cache_path)
        self.display = Display()
        self.should_end = False
    
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

        command = Factory.create_cmd(user_input)

        return command.handle(self, self.context, self.display)

    def _step_output(self, output: Dict[str, str]):
        self.display.system_output(output)

    def _exit(self):
        self.display.log_statistics(self.context.num_tokens)

    def end(self):
        self.should_end = True

    def start(self):
        
        while not self.should_end:
            output = self._step_input()
            self._step_output(output)

        self._exit()

@Factory.register(r"\help", "Show available commands.")
class HelpCommand(BasicCommand):  
    def handle(self, client: Client, context: Context, display: Display) -> Dict[str, str]:
        if len(self.args) > 0:
            return {"role": "kernel", "content": self.args_check_error_template.format(self.opcode)}
        return {"role": "kernel", "content": "\n\n" + \
                '\n'.join(map(lambda command: f"+ {command}: {Factory.command2description[command]}", Factory.commands))}

@Factory.register(r"\quit", "Quit program.")
class QuitCommand(BasicCommand): 
    def handle(self, client: Client, context: Context, display: Display) -> Dict[str, str]:
        if len(self.args) > 0:
            return {"role": "kernel", "content": self.args_check_error_template.format(self.opcode)}
        client.end()
        return {"role": "kernel", "content": "\n\nQuit."}

@Factory.register(r"\save", "Save context cache.")
class SaveCommand(BasicCommand):
    def handle(self, client: Client, context: Context, display: Display) -> Dict[str, str]:
        if len(self.args) == 0:
            dump_dir = client.dump_dir
        elif len(self.args) == 1:
            dump_dir = self.args[0]
        else:
            return {"role": "kernel", "content": self.args_check_error_template.format(self.opcode)}
        if not dump_dir:
            dump_dir = display.get_input("Specify a dump directory")
        context.dump(dump_dir)
        return {"role": "kernel", "content": "\n\nCache saved."}

@Factory.register(r"\load", "Load context cache.")
class LoadCommand(BasicCommand):
    def handle(self, client: Client, context: Context, display: Display) -> Dict[str, str]:
        if len(self.args) == 0:
            cache_path = display.get_input("Specify a cache path")
        elif len(self.args) == 1:
            cache_path = self.args[0]
        else:
            return {"role": "kernel", "content": self.args_check_error_template.format(self.opcode)}
        context.load(cache_path)
        display.clear_screen()
        display.show_context(context.get_context())
        return {"role": "kernel", "content": "\n\nContext is changed."}

@Factory.register(r"\back", "Return to last context.")
class BackCommand(BasicCommand):
    def handle(self, client: Client, context: Context, display: Display) -> Dict[str, str]:
        if len(self.args) > 0:
            return {"role": "kernel", "content": self.args_check_error_template.format(self.opcode)}
        context.cache_backward(n=2)
        display.clear_screen()
        display.show_context(context.get_context())
        return {"role": "kernel", "content": "\n\nNow at last context."}
    
@Factory.register(r"\clear", "Clear the whole context.")
class ClearCommand(BasicCommand):
    def handle(self, client: Client, context: Context, display: Display) -> Dict[str, str]:
        if len(self.args) > 0:
            return {"role": "kernel", "content": self.args_check_error_template.format(self.opcode)}
        context.cache_backward(all=True)
        display.clear_screen()
        return {"role": "kernel", "content": "\n\nNow at a new context."}

@Factory.register(r"\change", "Change used model.")
class ChangeCommand(BasicCommand):
    def handle(self, client: Client, context: Context, display: Display) -> Dict[str, str]:
        if len(self.args) == 0:
            model = display.get_input(f"Specify a model within [{', '.join(MODELS)}]")
        elif len(self.args) == 1:
            model = self.args[0]
        else:
            return {"role": "kernel", "content": self.args_check_error_template.format(self.opcode)}
        client.model = model
        return {"role": "kernel", "content": "\n\nModel is changed."}

@Factory.register(r"\request", "Request OpenAI to get a response.")
class RequestCommand(BasicCommand):
    def __init__(self, opcode: str, *args: List[str]):
        super().__init__(opcode, *args)
        if len(self.args) > 1:
            self.args = [' '.join(self.args)]
  
    def handle(self, client: Client, context: Context, display: Display) -> Dict[str, str]:
        context.add_user_input({
            "role": "user",
            "content": self.args[0]
        })
        waiting_callback = display.waiting()
        try:
            for retry_time in range(client.retry):
                response = client._request()
                if response and "choices" in response and "usage" in response:
                    break
                waiting_callback(stop=False, 
                    postfix=f"Request failed, {inflect_engine.ordinal(retry_time + 1)} retrying.")
            context.add_response(response)
            last_line = context.get_last_line()
        except Exception as e:
            logger.error(f"Error occured when processing request:\n{e}\n")
            context.cache_backward(n=1)
            last_line = {"role": "kernel", "content": "\n\nError receiving response from OpenAI."}
        finally:
            waiting_callback(stop=True)
        return last_line