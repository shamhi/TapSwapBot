import asyncio
from typing import Union

from pyrogram import Client
from pyrogram.types import Message
from bs4 import BeautifulSoup

from bot.utils.emojis import num, StaticEmoji


def get_command_args(
        message: Union[Message, str],
        command: Union[str, list[str]] = None,
        prefixes: str = "/",
) -> str:
    if isinstance(message, str):
        return message.split(f"{prefixes}{command}", maxsplit=1)[-1].strip()

    if isinstance(command, str):
        args = message.text.split(f"{prefixes}{command}", maxsplit=1)[-1].strip()
        return args

    elif isinstance(command, list):
        for cmd in command:
            args = message.text.split(f"{prefixes}{cmd}", maxsplit=1)[-1]

            if args != message.text:
                return args.strip()

    return ""


def with_args(text: str):
    def decorator(func):
        async def wrapped(client: Client, message: Message):
            if message.text and len(message.text.split()) == 1:
                await message.edit(f"<emoji id=5210952531676504517>❌</emoji>{text}")
            else:
                return await func(client, message)

        return wrapped

    return decorator


def get_help_text():
    return f"""<b>
{StaticEmoji.FLAG} [Demo version]

{num(1)} /help - Displays all available commands
{num(2)} /tap [on|start, off|stop] - Starts or stops the tapper

</b>"""


async def stop_tasks(client: Client = None) -> None:
    if client:
        all_tasks = asyncio.all_tasks(loop=client.loop)
    else:
        loop = asyncio.get_event_loop()
        all_tasks = asyncio.all_tasks(loop=loop)

    clicker_tasks = [task for task in all_tasks
                     if isinstance(task, asyncio.Task) and task._coro.__name__ == 'run_tapper']

    for task in clicker_tasks:
        try:
            task.cancel()
        except:
            ...


def extract_chq(chq: str) -> int:
    chq_length = len(chq)

    bytes_array = bytearray(chq_length // 2)
    xor_key = 157

    for i in range(0, chq_length, 2):
        bytes_array[i // 2] = int(chq[i:i + 2], 16)

    xor_bytes = bytearray(t ^ xor_key for t in bytes_array)
    decoded_xor = xor_bytes.decode('utf-8')

    js_code = (decoded_xor.split('try {eval("document.getElementById");} catch {return 0xC0FEBABE;}')[1].split('})')[0]
               .strip())

    html = js_code.split('rt["inner" + "HTM" + "L"] = ')[1].split('\n')[0]
    soup = BeautifulSoup(html, 'html.parser')

    div_elements = soup.find_all('div')
    codes = {}
    for div in div_elements:
        if 'id' in div.attrs and '_d_' in div.attrs:
            codes[div['id']] = div['_d_']

    va = None
    vb = None
    for k, v in codes.items():
        if k in js_code.split('\n')[5]:
            va = v
        if k in js_code.split('\n')[6]:
            vb = v

    code_to_execute = js_code.split('return ')[1].split(';')[0].replace('va', va).replace('vb', vb)

    return eval(code_to_execute)
