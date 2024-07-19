import json
import asyncio
from time import time
from random import randint

import aiohttp
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.functions.messages import RequestWebView

from bot.config import settings
from bot.utils import logger
from bot.utils.scripts import escape_html, login_in_browser
from bot.exceptions import InvalidSession
from .headers import headers


class Tapper:
    def __init__(self, tg_client: Client, lock: asyncio.Lock):
        self.session_name = tg_client.name
        self.tg_client = tg_client
        self.user_id = 0
        self.lock = lock

    async def get_auth_url(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            with_tg = True

            if not self.tg_client.is_connected:
                with_tg = False
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            while True:
                try:
                    peer = await self.tg_client.resolve_peer('tapswap_bot')
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f"{self.session_name} | FloodWait {fl}")
                    logger.info(f"{self.session_name} | Sleep {fls}s")

                    await asyncio.sleep(fls + 3)

            web_view = await self.tg_client.invoke(RequestWebView(
                peer=peer,
                bot=peer,
                platform='android',
                from_bot_menu=False,
                url='https://app.tapswap.club/'
            ))

            auth_url = web_view.url.replace('tgWebAppVersion=6.7', 'tgWebAppVersion=7.2')

            self.user_id = (await self.tg_client.get_me()).id

            if with_tg is False:
                await self.tg_client.disconnect()

            return auth_url

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error during Authorization: {escape_html(error)}")
            await asyncio.sleep(delay=3)

    async def login(self, http_client: aiohttp.ClientSession, auth_url: str, proxy: str) -> tuple[dict[str], str]:
        response_text = ''
        try:
            async with self.lock:
                response_text, x_cv, x_touch = login_in_browser(auth_url, proxy=proxy)

            response_json = json.loads(response_text)
            access_token = response_json.get('access_token', '')
            profile_data = response_json

            if headers:
                http_client.headers['X-Cv'] = x_cv
                http_client.headers['X-Touch'] = x_touch

            return profile_data, access_token
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error while Login: {escape_html(error)} | "
                         f"Response text: {escape_html(response_text)}...")
            await asyncio.sleep(delay=3)

            return {}, ''

    async def apply_boost(self, http_client: aiohttp.ClientSession, boost_type: str) -> bool:
        response_text = ''
        try:
            response = await http_client.post(url='https://api.tapswap.club/api/player/apply_boost',
                                              json={'type': boost_type})
            response_text = await response.text()
            response.raise_for_status()

            return True
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when Apply {boost_type} Boost: {escape_html(error)} | "
                         f"Response text: {escape_html(response_text)[:128]}...")
            await asyncio.sleep(delay=3)

            return False

    async def upgrade_boost(self, http_client: aiohttp.ClientSession, boost_type: str) -> bool:
        response_text = ''
        try:
            response = await http_client.post(url='https://api.tapswap.club/api/player/upgrade',
                                              json={'type': boost_type})
            response_text = await response.text()
            response.raise_for_status()

            return True
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when Upgrade {boost_type} Boost: {escape_html(error)} | "
                         f"Response text: {escape_html(response_text)[:128]}...")
            await asyncio.sleep(delay=3)

            return False

    async def claim_reward(self, http_client: aiohttp.ClientSession, task_id: str) -> bool:
        response_text = ''
        try:
            response = await http_client.post(url='https://api.tapswap.club/api/player/claim_reward',
                                              json={'task_id': task_id})
            response_text = await response.text()
            response.raise_for_status()

            return True
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when Claim {task_id} Reward: {escape_html(error)} | "
                         f"Response text: {escape_html(response_text)[:128]}...")
            await asyncio.sleep(delay=3)

            return False

    async def send_taps(self, http_client: aiohttp.ClientSession, taps: int) -> dict[str]:
        response_text = ''
        try:
            timestamp = int(time() * 1000)
            content_id = int((timestamp * self.user_id * self.user_id / self.user_id) % self.user_id % self.user_id)

            json_data = {'taps': taps, 'time': timestamp}

            http_client.headers['Content-Id'] = str(content_id)

            response = await http_client.post(url='https://api.tapswap.club/api/player/submit_taps', json=json_data)
            response_text = await response.text()
            response.raise_for_status()

            response_json = await response.json()
            player_data = response_json['player']

            return player_data
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when Tapping: {escape_html(error)} | "
                         f"Response text: {escape_html(response_text)[:128]}...")
            await asyncio.sleep(delay=3)

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {escape_html(error)}")

    async def run(self, proxy: str | None) -> None:
        access_token_created_time = 0
        turbo_time = 0
        active_turbo = False

        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)

        if proxy:
            await self.check_proxy(http_client=http_client, proxy=proxy)

        auth_url = await self.get_auth_url(proxy=proxy)

        while True:
            try:
                if http_client.closed:
                    if proxy_conn:
                        if not proxy_conn.closed:
                            proxy_conn.close()

                    proxy_conn = ProxyConnector().from_url(proxy) if proxy else None
                    http_client = aiohttp.ClientSession(headers=headers, connector=proxy_conn)

                if time() - access_token_created_time >= 1800:
                    profile_data, access_token = await self.login(http_client=http_client, auth_url=auth_url, proxy=proxy)

                    if not access_token:
                        continue

                    http_client.headers["Authorization"] = f"Bearer {access_token}"

                    access_token_created_time = time()

                    tap_bot = profile_data['player']['tap_bot']
                    if tap_bot:
                        bot_earned = profile_data['bot_shares']

                        logger.success(f"{self.session_name} | Tap bot earned +{bot_earned:,} coins!")

                    balance = profile_data['player']['shares']

                    tap_prices = {index + 1: data['price'] for index, data in
                                  enumerate(profile_data['conf']['tap_levels'])}
                    energy_prices = {index + 1: data['price'] for index, data in
                                     enumerate(profile_data['conf']['energy_levels'])}
                    charge_prices = {index + 1: data['price'] for index, data in
                                     enumerate(profile_data['conf']['charge_levels'])}

                    claims = profile_data['player']['claims']
                    if claims:
                        for task_id in claims:
                            logger.info(f"{self.session_name} | Sleep 5s before claim <m>{task_id}</m> reward")
                            await asyncio.sleep(delay=5)

                            status = await self.claim_reward(http_client=http_client, task_id=task_id)
                            if status is True:
                                logger.success(f"{self.session_name} | Successfully claim <m>{task_id}</m> reward")

                                await asyncio.sleep(delay=1)

                taps = randint(a=settings.RANDOM_TAPS_COUNT[0], b=settings.RANDOM_TAPS_COUNT[1])

                if active_turbo:
                    taps += settings.ADD_TAPS_ON_TURBO
                    if time() - turbo_time > 20:
                        active_turbo = False
                        turbo_time = 0

                player_data = await self.send_taps(http_client=http_client, taps=taps)

                if not player_data:
                    continue

                available_energy = player_data['energy']
                new_balance = player_data['shares']
                calc_taps = abs(new_balance - balance)
                balance = new_balance
                total = player_data['stat']['earned']

                turbo_boost_count = player_data['boost'][1]['cnt']
                energy_boost_count = player_data['boost'][0]['cnt']

                next_tap_level = player_data['tap_level'] + 1
                next_energy_level = player_data['energy_level'] + 1
                next_charge_level = player_data['charge_level'] + 1

                logger.success(f"{self.session_name} | Successful tapped! | "
                               f"Balance: <c>{balance:,}</c> (<g>+{calc_taps:,}</g>) | Total: <e>{total:,}</e>")

                if active_turbo is False:
                    if (energy_boost_count > 0
                            and available_energy < settings.MIN_AVAILABLE_ENERGY
                            and settings.APPLY_DAILY_ENERGY is True):
                        logger.info(f"{self.session_name} | Sleep 5s before activating the daily energy boost")
                        await asyncio.sleep(delay=5)

                        status = await self.apply_boost(http_client=http_client, boost_type="energy")
                        if status is True:
                            logger.success(f"{self.session_name} | Energy boost applied")

                            await asyncio.sleep(delay=1)

                        continue

                    if turbo_boost_count > 0 and settings.APPLY_DAILY_TURBO is True:
                        logger.info(f"{self.session_name} | Sleep 5s before activating the daily turbo boost")
                        await asyncio.sleep(delay=5)

                        status = await self.apply_boost(http_client=http_client, boost_type="turbo")
                        if status is True:
                            logger.success(f"{self.session_name} | Turbo boost applied")

                            await asyncio.sleep(delay=1)

                            active_turbo = True
                            turbo_time = time()

                        continue

                    if (settings.AUTO_UPGRADE_TAP is True
                            and balance > tap_prices.get(next_tap_level, 0)
                            and next_tap_level <= settings.MAX_TAP_LEVEL):
                        logger.info(f"{self.session_name} | Sleep 5s before upgrade tap to {next_tap_level} lvl")
                        await asyncio.sleep(delay=5)

                        status = await self.upgrade_boost(http_client=http_client, boost_type="tap")
                        if status is True:
                            logger.success(f"{self.session_name} | Tap upgraded to {next_tap_level} lvl")

                            await asyncio.sleep(delay=1)

                        continue

                    if (settings.AUTO_UPGRADE_ENERGY is True
                            and balance > energy_prices.get(next_energy_level, 0)
                            and next_energy_level <= settings.MAX_ENERGY_LEVEL):
                        logger.info(
                            f"{self.session_name} | Sleep 5s before upgrade energy to {next_energy_level} lvl")
                        await asyncio.sleep(delay=5)

                        status = await self.upgrade_boost(http_client=http_client, boost_type="energy")
                        if status is True:
                            logger.success(f"{self.session_name} | Energy upgraded to {next_energy_level} lvl")

                            await asyncio.sleep(delay=1)

                        continue

                    if (settings.AUTO_UPGRADE_CHARGE is True
                            and balance > charge_prices.get(next_charge_level, 0)
                            and next_charge_level <= settings.MAX_CHARGE_LEVEL):
                        logger.info(
                            f"{self.session_name} | Sleep 5s before upgrade charge to {next_charge_level} lvl")
                        await asyncio.sleep(delay=5)

                        status = await self.upgrade_boost(http_client=http_client, boost_type="charge")
                        if status is True:
                            logger.success(f"{self.session_name} | Charge upgraded to {next_charge_level} lvl")

                            await asyncio.sleep(delay=1)

                        continue

                    if available_energy < settings.MIN_AVAILABLE_ENERGY:
                        await http_client.close()
                        if proxy_conn:
                            if not proxy_conn.closed:
                                proxy_conn.close()

                        random_sleep = randint(settings.SLEEP_BY_MIN_ENERGY[0], settings.SLEEP_BY_MIN_ENERGY[1])

                        logger.info(f"{self.session_name} | Minimum energy reached: {available_energy}")
                        logger.info(f"{self.session_name} | Sleep {random_sleep:,}s")

                        await asyncio.sleep(delay=random_sleep)

                        access_token_created_time = 0

            except InvalidSession as error:
                raise error

            except Exception as error:
                logger.error(f"{self.session_name} | Unknown error: {escape_html(error)}")
                await asyncio.sleep(delay=3)

            else:
                sleep_between_clicks = randint(a=settings.SLEEP_BETWEEN_TAP[0], b=settings.SLEEP_BETWEEN_TAP[1])

                if active_turbo is True:
                    sleep_between_clicks = 4

                logger.info(f"Sleep {sleep_between_clicks}s")
                await asyncio.sleep(delay=sleep_between_clicks)


async def run_tapper(tg_client: Client, proxy: str | None, lock: asyncio.Lock):
    try:
        await Tapper(tg_client=tg_client, lock=lock).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
