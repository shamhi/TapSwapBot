import asyncio
from time import time
from random import randint
from urllib.parse import unquote

import aiohttp
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.types import User
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered
from pyrogram.raw.functions.messages import RequestWebView
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import settings
from bot.utils import logger
from bot.exceptions import InvalidSession
from db.functions import get_user_proxy, get_user_agent, save_log
from .headers import headers


local_db = {}


class Tapper:
    def __init__(self, tg_client: Client, db_pool: async_sessionmaker, user_data: User):
        self.session_name = tg_client.name
        self.tg_client = tg_client
        self.db_pool = db_pool
        self.user_data = user_data

    async def get_tg_web_data(self, proxy: str | None) -> str:
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

            web_view = await self.tg_client.invoke(RequestWebView(
                peer=await self.tg_client.resolve_peer('tapswap_bot'),
                bot=await self.tg_client.resolve_peer('tapswap_bot'),
                platform='android',
                from_bot_menu=False,
                url='https://app.tapswap.ai/'
            ))

            auth_url = web_view.url
            tg_web_data = unquote(
                string=unquote(
                    string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0]))

            if with_tg is False:
                await self.tg_client.disconnect()

            return tg_web_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=3)

    async def login(self, http_client: aiohttp.ClientSession, tg_web_data: str) -> tuple[dict[str], str]:
        try:
            response = await http_client.post(url='https://api.tapswap.ai/api/account/login',
                                              json={"init_data": tg_web_data, "referrer": ""})
            response.raise_for_status()

            response_json = await response.json()
            access_token = response_json['access_token']
            profile_data = response_json

            return profile_data, access_token
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error while getting Access Token: {error}")
            await asyncio.sleep(delay=3)

    async def apply_boost(self, http_client: aiohttp.ClientSession, boost_type: str) -> bool:
        try:
            response = await http_client.post(url='https://api.tapswap.ai/api/player/apply_boost',
                                              json={'type': boost_type})
            response.raise_for_status()

            return True
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when Apply {boost_type} Boost: {error}")
            await asyncio.sleep(delay=3)

            return False

    async def upgrade_boost(self, http_client: aiohttp.ClientSession, boost_type: str) -> bool:
        try:
            response = await http_client.post(url='https://api.tapswap.ai/api/player/upgrade',
                                              json={'type': boost_type})
            response.raise_for_status()

            return True
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when Upgrade {boost_type} Boost: {error}")
            await asyncio.sleep(delay=3)

            return False


    async def claim_reward(self, http_client: aiohttp.ClientSession, task_id: str) -> bool:
        try:
            response = await http_client.post(url='https://api.tapswap.ai/api/player/claim_reward',
                                              json={'task_id': task_id})
            response.raise_for_status()

            return True
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when Claim {task_id} Reward: {error}")
            await asyncio.sleep(delay=3)

            return False

    async def send_taps(self, http_client: aiohttp.ClientSession, taps: int) -> dict[str]:
        try:
            response = await http_client.post(url='https://api.tapswap.ai/api/player/submit_taps',
                                              json={'taps': taps, 'time': time()})
            response.raise_for_status()

            response_json = await response.json()
            player_data = response_json['player']

            return player_data
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when Tapping: {error}")
            await asyncio.sleep(delay=3)

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")

    async def run(self, proxy: str | None) -> None:
        turbo_time = 0
        active_turbo = False

        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        user_agent = await get_user_agent(db_pool=self.db_pool, phone_number=self.user_data.phone_number)
        headers['User-Agent'] = user_agent

        async with aiohttp.ClientSession(headers=headers, connector=proxy_conn) as http_client:
            if proxy:
                await self.check_proxy(http_client=http_client, proxy=proxy)

            try:
                local_token = local_db[self.session_name]['Token']
                if not local_token:
                    tg_web_data = await self.get_tg_web_data(proxy=proxy)
                    profile_data, access_token = await self.login(http_client=http_client, tg_web_data=tg_web_data)

                    http_client.headers["Authorization"] = f"Bearer {access_token}"
                    headers["Authorization"] = f"Bearer {access_token}"

                    local_db[self.session_name]['Token'] = access_token

                    tap_bot = profile_data['player']['tap_bot']
                    if tap_bot:
                        bot_earned = profile_data['bot_shares']

                        logger.success(f"{self.session_name} | Tap bot earned +{bot_earned} coins!")

                    balance = profile_data['player']['shares']

                    local_db[self.session_name]['Balance'] = balance

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
                else:
                    http_client.headers["Authorization"] = f"Bearer {local_token}"

                    balance = local_db[self.session_name]['Balance']

                taps = randint(a=settings.RANDOM_TAPS_COUNT[0], b=settings.RANDOM_TAPS_COUNT[1])

                if active_turbo:
                    taps += settings.ADD_TAPS_ON_TURBO
                    if time() - turbo_time > 20:
                        active_turbo = False
                        turbo_time = 0

                player_data = await self.send_taps(http_client=http_client, taps=taps)

                if not player_data:
                    await save_log(
                        db_pool=self.db_pool,
                        phone=self.user_data.phone_number,
                        status="ERROR",
                        amount=balance,
                    )

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
                               f"Balance: <c>{balance}</c> (<g>+{calc_taps}</g>) | Total: <e>{total}</e>")

                await save_log(
                    db_pool=self.db_pool,
                    phone=self.user_data.phone_number,
                    status="TAP",
                    amount=balance,
                )

                if active_turbo is False:
                    if (energy_boost_count > 0
                            and available_energy < settings.MIN_AVAILABLE_ENERGY
                            and settings.APPLY_DAILY_ENERGY is True):
                        logger.info(f"{self.session_name} | Sleep 5s before activating the daily energy boost")
                        await asyncio.sleep(delay=5)

                        status = await self.apply_boost(http_client=http_client, boost_type="energy")
                        if status is True:
                            logger.success(f"{self.session_name} | Energy boost applied")

                            await save_log(
                                db_pool=self.db_pool,
                                phone=self.user_data.phone_number,
                                status="APPLY ENERGY BOOST",
                                amount=balance,
                            )

                            await asyncio.sleep(delay=1)

                    if turbo_boost_count > 0 and settings.APPLY_DAILY_TURBO is True:
                        logger.info(f"{self.session_name} | Sleep 5s before activating the daily turbo boost")
                        await asyncio.sleep(delay=5)

                        status = await self.apply_boost(http_client=http_client, boost_type="turbo")
                        if status is True:
                            logger.success(f"{self.session_name} | Turbo boost applied")

                            await save_log(
                                db_pool=self.db_pool,
                                phone=self.user_data.phone_number,
                                status="APPLY TURBO BOOST",
                                amount=balance,
                            )

                            await asyncio.sleep(delay=1)

                            active_turbo = True
                            turbo_time = time()

                    if (settings.AUTO_UPGRADE_TAP is True
                            and balance > tap_prices.get(next_tap_level, 0)
                            and next_tap_level <= settings.MAX_TAP_LEVEL):
                        logger.info(f"{self.session_name} | Sleep 5s before upgrade tap to {next_tap_level} lvl")
                        await asyncio.sleep(delay=5)

                        status = await self.upgrade_boost(http_client=http_client, boost_type="tap")
                        if status is True:
                            logger.success(f"{self.session_name} | Tap upgraded to {next_tap_level} lvl")

                            await save_log(
                                db_pool=self.db_pool,
                                phone=self.user_data.phone_number,
                                status="UPGRADE TAP",
                                amount=balance,
                            )

                            await asyncio.sleep(delay=1)

                    if (settings.AUTO_UPGRADE_ENERGY is True
                            and balance > energy_prices.get(next_energy_level, 0)
                            and next_energy_level <= settings.MAX_ENERGY_LEVEL):
                        logger.info(
                            f"{self.session_name} | Sleep 5s before upgrade energy to {next_energy_level} lvl")
                        await asyncio.sleep(delay=5)

                        status = await self.upgrade_boost(http_client=http_client, boost_type="energy")
                        if status is True:
                            logger.success(f"{self.session_name} | Energy upgraded to {next_energy_level} lvl")

                            await save_log(
                                db_pool=self.db_pool,
                                phone=self.user_data.phone_number,
                                status="UPGRADE ENERGY",
                                amount=balance,
                            )

                            await asyncio.sleep(delay=1)

                    if (settings.AUTO_UPGRADE_CHARGE is True
                            and balance > charge_prices.get(next_charge_level, 0)
                            and next_charge_level <= settings.MAX_CHARGE_LEVEL):
                        logger.info(
                            f"{self.session_name} | Sleep 5s before upgrade charge to {next_charge_level} lvl")
                        await asyncio.sleep(delay=5)

                        status = await self.upgrade_boost(http_client=http_client, boost_type="charge")
                        if status is True:
                            logger.success(f"{self.session_name} | Charge upgraded to {next_charge_level} lvl")

                            await save_log(
                                db_pool=self.db_pool,
                                phone=self.user_data.phone_number,
                                status="UPGRADE CHARGE",
                                amount=balance,
                            )

                            await asyncio.sleep(delay=1)

                    if available_energy < settings.MIN_AVAILABLE_ENERGY:
                        logger.info(f"{self.session_name} | Minimum energy reached: {available_energy}")
                        logger.info(f"{self.session_name} | Sleep {settings.SLEEP_BY_MIN_ENERGY}s")

                        await asyncio.sleep(delay=settings.SLEEP_BY_MIN_ENERGY)

            except InvalidSession as error:
                raise error

            except Exception as error:
                logger.error(f"{self.session_name} | Unknown error: {error}")
                await asyncio.sleep(delay=3)


async def run_tapper(tg_client: Client, db_pool: async_sessionmaker):
    try:
        async with tg_client:
            user_data = await tg_client.get_me()

        if not local_db.get(tg_client.name):
            local_db[tg_client.name] = {'Token': '', 'Balance': 0}

        proxy = None
        if settings.USE_PROXY_FROM_DB:
            proxy = await get_user_proxy(db_pool=db_pool, phone_number=user_data.phone_number)

        await Tapper(tg_client=tg_client, db_pool=db_pool, user_data=user_data).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
