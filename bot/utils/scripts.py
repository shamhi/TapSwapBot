import os
import glob
import time
import random
import shutil
import asyncio
import pathlib
from typing import Union
from contextlib import contextmanager

from pyrogram import Client
from pyrogram.types import Message
from better_proxy import Proxy
from multiprocessing import Queue

from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager

from bot.config import settings
from bot.utils import logger
from bot.utils.emojis import num, StaticEmoji


def get_session_names() -> list[str]:
    session_names = [os.path.splitext(os.path.basename(file))[0] for file in glob.glob("sessions/*.session")]

    return session_names


def get_proxies() -> list[Proxy]:
    if settings.USE_PROXY_FROM_FILE:
        with open(file="bot/config/proxies.txt", encoding="utf-8-sig") as file:
            proxies = [Proxy.from_str(proxy=row.strip()).as_url for row in file]
    else:
        proxies = []

    return proxies


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


def escape_html(text: str) -> str:
    text = str(text)
    return text.replace('<', '\\<').replace('>', '\\>')


web_options = ChromeOptions
web_service = ChromeService
web_manager = ChromeDriverManager
web_driver = webdriver.Chrome

if not pathlib.Path("webdriver").exists() or len(list(pathlib.Path("webdriver").iterdir())) == 0:
    logger.info("Downloading webdriver. It may take some time...")
    pathlib.Path("webdriver").mkdir(parents=True, exist_ok=True)
    webdriver_path = pathlib.Path(web_manager().install())
    shutil.move(webdriver_path, f"webdriver/{webdriver_path.name}")
    logger.info("Webdriver downloaded successfully")

webdriver_path = next(pathlib.Path("webdriver").iterdir()).as_posix()

device_metrics = {"width": 375, "height": 812, "pixelRatio": 3.0}
user_agent = "Mozilla/5.0 (Linux; Android 13; RMX3630 Build/TP1A.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/125.0.6422.165 Mobile Safari/537.36"

mobile_emulation = {
    "deviceMetrics": device_metrics,
    "userAgent": user_agent,
}

options = web_options()

options.add_experimental_option("mobileEmulation", mobile_emulation)

options.add_argument("--headless")
options.add_argument("--log-level=3")
if os.name == 'posix':
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')


@contextmanager
def create_webdriver():
    driver = web_driver(service=web_service(webdriver_path), options=options)
    try:
        yield driver
    finally:
        driver.quit()


def extract_chq(chq: str) -> int:
    with create_webdriver() as driver:
        chq_length = len(chq)

        bytes_array = bytearray(chq_length // 2)
        xor_key = 157

        for i in range(0, chq_length, 2):
            bytes_array[i // 2] = int(chq[i:i + 2], 16)

        xor_bytes = bytearray(t ^ xor_key for t in bytes_array)
        decoded_xor = xor_bytes.decode('utf-8')

        driver.execute_script("""
            window.ctx = {}
            window.ctx.api = {}
            window.ctx.d_headers = new Map()
            window.ctx.api.setHeaders = function(entries) { for (const [W, U] of Object.entries(entries)) window.ctx.d_headers.set(W, U) }
            var chrStub = document.createElement("div");
            chrStub.id = "_chr_";
            document.body.appendChild(chrStub);
        """)

        fixed_xor = repr(decoded_xor).replace("`", "\\`")

        chr_key = driver.execute_script(f"""
            try {{
                return eval(`{fixed_xor[1:-1]}`);
            }} catch (e) {{
                return e;
            }}
        """)

        cache_id = driver.execute_script(f"""
            try {{
                return window.ctx.d_headers.get('Cache-Id');
            }} catch (e) {{
                return e;
            }}
        """)

    return chr_key, cache_id


# Other way
def login_in_browser(auth_url: str, proxy: str) -> tuple[str, str, str]:
    with create_webdriver() as driver:
        if proxy:
            proxy_options = {
                'proxy': {
                    'http': proxy,
                    'https': proxy,
                }
            }
        else:
            proxy_options = None

        driver = web_driver(service=web_service(webdriver_path), options=options, seleniumwire_options=proxy_options)

        driver.get(auth_url)

        time.sleep(random.randint(7, 15))

        try:
            skip_button = driver.find_element(By.XPATH, '//*[@id="app"]/div[2]/button')
            if skip_button:
                skip_button.click()
                time.sleep(random.randint(2, 5))
        except:
            ...

        try:
            coin = driver.find_element(By.XPATH, '//*[@id="ex1-layer"]')
            if coin:
                coin.click()
        except:
            ...

        time.sleep(5)

        response_text = '{}'
        x_cv = '651'
        x_touch = '1'

        for request in driver.requests:
            request_body = request.body.decode('utf-8')
            if request.url == "https://api.tapswap.club/api/account/challenge" and 'chr' in request_body:
                response_text = request.response.body.decode('utf-8')

            if request.url == "https://api.tapswap.club/api/player/submit_taps":
                headers = dict(request.headers.items())
                x_cv = headers.get('X-Cv') or headers.get('x-cv')
                x_touch = headers.get('X-Touch', '') or headers.get('x-touch', '')

    return response_text, x_cv, x_touch
