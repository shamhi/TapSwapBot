import os
import glob
import time
import random
import shutil
import asyncio
import pathlib

from multiprocessing import Queue

from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager

from bot.config import settings
from bot.utils import logger


def get_session_names() -> list[str]:
    session_names = glob.glob("sessions/*.session")
    session_names = [
        os.path.splitext(os.path.basename(file))[0] for file in session_names
    ]

    return session_names


def escape_html(text: str) -> str:
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
driver = None

session_queue = Queue()


def extract_chq(chq: str) -> int:
    global driver

    if driver is None:
        driver = web_driver(service=web_service(webdriver_path), options=options)

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

    session_queue.put(1)

    if len(get_session_names()) == session_queue.qsize():
        logger.info("All sessions are closed. Quitting driver...")
        driver.quit()
        driver = None
        while session_queue.qsize() > 0:
            session_queue.get()

    return chr_key, cache_id


# Other way
def login_in_browser(auth_url: str, proxy: str) -> tuple[str, str, str]:
    global driver

    if driver is None:
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
    x_cv = '631'
    x_touch = '1'

    for request in driver.requests:
        request_body = request.body.decode('utf-8')
        if request.url == "https://api.tapswap.ai/api/account/login" and 'chr' in request_body:
            response_text = request.response.body.decode('utf-8')

        if request.url == "https://api.tapswap.ai/api/player/submit_taps":
            headers = dict(request.headers.items())
            x_cv = headers.get('X-Cv') or headers.get('x-cv')
            x_touch = headers.get('X-Touch', '') or headers.get('x-touch', '')

    session_queue.put(1)

    if len(get_session_names()) == session_queue.qsize():
        logger.info("All sessions are closed. Quitting driver...")
        driver.quit()
        driver = None
        while session_queue.qsize() > 0:
            session_queue.get()

    return response_text, x_cv, x_touch
