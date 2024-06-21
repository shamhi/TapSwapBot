import glob
import os

from bot.utils import logger

import pathlib
import shutil
from selenium import webdriver
from multiprocessing import Queue


def get_session_names() -> list[str]:
    session_names = glob.glob("sessions/*.session")
    session_names = [
        os.path.splitext(os.path.basename(file))[0] for file in session_names
    ]

    return session_names


if os.name == "posix":
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from webdriver_manager.firefox import GeckoDriverManager

    web_options = FirefoxOptions
    web_service = FirefoxService
    web_manager = GeckoDriverManager
    web_driver = webdriver.Firefox
else:
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from webdriver_manager.chrome import ChromeDriverManager

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

options = web_options()
options.add_argument("--headless")
driver = None

session_queue = Queue()


def escape_html(text: str) -> str:
    return text.replace('<', '\\<').replace('>', '\\>')


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
