import asyncio
from sqlalchemy import text
from app.database import engine

async def inspect_db():
    async with engine.connect() as conn:
        for tbl in ['users', 'resumes', 'jobs', 'applications', 'agent_runs']:
            query = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{tbl}' ORDER BY ordinal_position;"
            res = await conn.execute(text(query))
            cols = res.fetchall()
            print(f"=== TABLE: {tbl} ===")
            for c in cols:
                print(f"  {c[0]} ({c[1]})")
            print()

if __name__ == "__main__":
    asyncio.run(inspect_db())
