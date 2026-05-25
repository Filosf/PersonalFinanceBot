import asyncio

import asyncpg

from app.core.config import get_settings


async def main() -> None:
    url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        version = await conn.fetchval("select version()")
        print(f"Connected: {version}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
