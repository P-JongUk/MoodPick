import os, re, json, sys
from supabase import create_client

# Load minimal env from backend/.env.local
env = {}
with open('backend/.env.local', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

SUPABASE_URL = env.get('SUPABASE_URL')
SUPABASE_KEY = env.get('SUPABASE_SERVICE_ROLE_KEY') or env.get('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print(json.dumps({'error': 'missing_supabase_config'}))
    sys.exit(1)

try:
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    res = client.table('emotion_records').select('*').order('created_at', desc=True).limit(10).execute()
    out = {'status': 'ok', 'count': getattr(res, 'count', None), 'data': res.data}
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
except Exception as e:
    print(json.dumps({'error': str(e)}))
    sys.exit(2)
