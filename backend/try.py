from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# create a sample row (table must exist already); if not, use SQL Editor
res = supabase.table("news").insert({
    "title": "Test article",
    "url": "https://example.com/test",
    "source": "Example",
    "published_at": "2025-10-08T00:00:00Z",
    "raw_text": "This is a sample article used to test Supabase table connectivity."
}).execute()
print(res.status_code, res.data)
