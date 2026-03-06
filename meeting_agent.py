from notion_client import Client
from dotenv import load_dotenv
import os

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

notion = Client(auth=NOTION_TOKEN)

tasks = [
    {"task": "Frontend dizájn véglegesítése", "assignee": "Kovács Anna", "deadline": "2025-03-15"},
    {"task": "API dokumentáció megírása", "assignee": "Nagy Péter", "deadline": "2025-03-20"},
    {"task": "Tesztesetek elkészítése", "assignee": "Szabó Balázs", "deadline": "2025-03-18"},
]

for t in tasks:
    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties={
            "Name": {
                "title": [{"text": {"content": t["task"]}}]
            },
            "Assignee": {
                "rich_text": [{"text": {"content": t["assignee"]}}]
            },
            "Date of Meeting": {
                "date": {"start": t["deadline"]}
            }
        }
    )
    print(f"Létrehozva: {t['task']}")