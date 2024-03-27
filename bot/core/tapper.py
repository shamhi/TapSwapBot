import asyncio
from time import time
from random import randint
from urllib.parse import unquote

import aiohttp
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered
from pyrogram.raw.functions.messages import RequestWebView

from bot.config import settings
from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers


class Tapper:
    def __init__(self, tg_client: Client):
        self.session_name = tg_client.name
        self.tg_client = tg_client

    async def get_tg_web_data(self):
        try:
            if not self.tg_client.is_connected:
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

            return tg_web_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error during authorization: {error}")
            await asyncio.sleep(delay=3)

    async def login(self, http_client: aiohttp.ClientSession, tg_web_data: str):
        try:
            response = await http_client.post(url='https://api.tapswap.ai/api/account/login',
                                              json={"init_data": tg_web_data, "referrer": ""})
            response.raise_for_status()

            response_json = await response.json()
            access_token = response_json['access_token']
            profile_data = response_json

            return profile_data, access_token
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error while retrieving Access Token: {error}")
            await asyncio.sleep(delay=3)

    async def send_taps(self, http_client: aiohttp.ClientSession, taps: int, balance: int):
        try:
            response = await http_client.post(url='https://api.tapswap.ai/api/player/submit_taps',
                                              json={'taps': taps, 'time': time()})
            response.raise_for_status()

            response_json = await response.json()
            player_data = response_json['player']

            return player_data
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when tapping: {error}")
            await asyncio.sleep(delay=3)

    async def apply_boost(self, http_client: aiohttp.ClientSession, boost_type: str):
        try:
            response = await http_client.post(url='https://api.tapswap.ai/api/player/apply_boost',
                                              json={'type': boost_type})
            response.raise_for_status()

            return True
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when tapping: {error}")
            await asyncio.sleep(delay=3)

            return False

    async def run(self):
        access_token_created_time = 0
        active_turbo = False

        async with (aiohttp.ClientSession(headers=headers) as http_client):
            while True:
                try:
                    if time() - access_token_created_time >= 3 * 60 * 60:
                        tg_web_data = await self.get_tg_web_data()
                        profile_data, access_token = await self.login(http_client=http_client, tg_web_data=tg_web_data)

                        http_client.headers["Authorization"] = f"Bearer {access_token}"
                        headers["Authorization"] = f"Bearer {access_token}"

                        access_token_created_time = time()

                        balance = profile_data['player']['shares']

                    taps = randint(a=settings.RANDOM_TAPS_COUNT[0], b=settings.RANDOM_TAPS_COUNT[1])

                    if active_turbo:
                        taps += 500
                        active_turbo = False

                    player_data = await self.send_taps(http_client=http_client, taps=taps, balance=balance)

                    available_energy = player_data['energy']
                    new_balance = player_data['shares']
                    calc_taps = abs(new_balance - balance)
                    balance = new_balance
                    total = player_data['stat']['earned']
                    energy_boost_count = player_data['boost'][0]['cnt']
                    turbo_boost_count = player_data['boost'][1]['cnt']

                    logger.success(f"Successful tapped! | Balance: {balance} (+{calc_taps}) | Total: {total}")

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
                                continue

                        if available_energy < settings.MIN_AVAILABLE_ENERGY:
                            logger.info(f"{self.session_name} | Minimum energy reached: {settings.MIN_AVAILABLE_ENERGY}")
                            logger.info(f"{self.session_name} | Sleep {settings.SLEEP_BY_MIN_ENERGY}s")

                            await asyncio.sleep(delay=settings.SLEEP_BY_MIN_ENERGY)

                            continue


                except InvalidSession as error:
                    raise error

                except Exception as error:
                    logger.error(f"{self.session_name} | Unknown error: {error}")
                    await asyncio.sleep(delay=3)

                else:
                    sleep_between_clicks = randint(a=settings.SLEEP_BETWEEN_TAP[0], b=settings.SLEEP_BETWEEN_TAP[1])

                    if active_turbo:
                        sleep_between_clicks = 4

                    logger.info(f"Sleep {sleep_between_clicks}s")
                    await asyncio.sleep(delay=sleep_between_clicks)


async def run_tapper(tg_client: Client):
    try:
        await Tapper(tg_client=tg_client).run()
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
