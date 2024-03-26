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

    async def get_access_token(self, http_client: aiohttp.ClientSession, tg_web_data: str):
        try:
            response = await http_client.post(url='https://api.tapswap.ai/api/account/login',
                                              json={"init_data": tg_web_data, "referrer": ""})
            response.raise_for_status()

            response_json = await response.json()
            access_token = response_json["access_token"]

            return access_token
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error while retrieving Access Token: {error}")
            await asyncio.sleep(delay=3)

    async def send_taps(self, http_client: aiohttp.ClientSession, taps: int):
        try:
            response = await http_client.post(url='https://api.tapswap.ai/api/player/submit_taps',
                                              json={'taps': taps, 'time': time()})

            response_json = await response.json()
            player_data = response_json['player']

            available_energy = player_data['energy']
            balance = player_data['shares']
            tap_level = player_data['tap_level']
            energy_boost_count = player_data['boost'][0]['cnt']
            turbo_boost_count = player_data['boost'][1]['cnt']

            return available_energy, balance, taps * tap_level, energy_boost_count, turbo_boost_count
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when tapping: {error}")
            await asyncio.sleep(delay=3)

    async def run(self):
        access_token_created_time = 0

        async with (aiohttp.ClientSession(headers=headers) as http_client):
            try:
                while True:
                    if time() - access_token_created_time >= 3 * 60 * 60:
                        tg_web_data = await self.get_tg_web_data()
                        access_token = await self.get_access_token(http_client=http_client, tg_web_data=tg_web_data)

                        http_client.headers["Authorization"] = f"Bearer {access_token}"
                        headers["Authorization"] = f"Bearer {access_token}"

                        access_token_created_time = time()

                    taps = randint(a=settings.RANDOM_CLICKS_COUNT[0], b=settings.RANDOM_CLICKS_COUNT[1])

                    available_energy, balance, calc_taps, energy_boost_count, turbo_boost_count = \
                        await self.send_taps(http_client=http_client, taps=taps)

                    logger.success(f"Successful tapped! | Balance: {balance} (+{calc_taps}) | Available: {available_energy}")
                    logger.info(f"Sleep 10s")

                    await asyncio.sleep(delay=10)
            except Exception as error:
                logger.error(f"{self.session_name} | Unknown error: {error}")
                await asyncio.sleep(delay=3)



async def run_tapper(tg_client: Client):
    try:
        await Tapper(tg_client=tg_client).run()
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
