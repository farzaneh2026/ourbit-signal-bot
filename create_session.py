import asyncio
import os
from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    api_id = int(os.environ.get('TG_API_ID', '0'))
    api_hash = os.environ.get('TG_API_HASH', '')
    if not api_id or not api_hash:
        raise SystemExit('Set TG_API_ID and TG_API_HASH first.')

    # This script is run locally once. It prints a StringSession only;
    # no .session file is written to the project.
    c = TelegramClient(StringSession(), api_id, api_hash)
    await c.start()
    session = c.session.save()

    print('\nTG_SESSION=')
    print(session)
    print('\nCopy the value above into Railway variable TG_SESSION.')
    print('Do NOT commit this value, a .session file, or your .env file to GitHub.')

    await c.disconnect()


asyncio.run(main())
