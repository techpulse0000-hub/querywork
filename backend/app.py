import csv
import io
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv, set_key
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field, SecretStr

from . import engine

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / '.env'
load_dotenv(ENV_FILE)
DATA = Path(os.getenv('QUERYWORK_DATA', str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
TOKEN_PATH = DATA / 'api-token'
if not TOKEN_PATH.exists():
    TOKEN_PATH.write_text(secrets.token_urlsafe(32), encoding='utf-8')
TOKEN = TOKEN_PATH.read_text(encoding='utf-8').strip()
LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=1)


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    db = sqlite3.connect(DATA / 'querywork.sqlite3', timeout=30)
    db.execute('CREATE TABLE IF NOT EXISTS records(kind TEXT, id TEXT, body TEXT, PRIMARY KEY(kind,id))')
    return db


def save(kind, value):
    with LOCK, connect() as db:
        db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)', (kind, value['id'], json.dumps(value)))
    return value


def get(kind, key):
    with LOCK, connect() as db:
        row = db.execute('SELECT body FROM records WHERE kind=? AND id=?', (kind, key)).fetchone()
    if not row:
        raise HTTPException(404, 'Record not found')
    return json.loads(row[0])


def all_records(kind):
    with LOCK, connect() as db:
        return [json.loads(r[0]) for r in db.execute('SELECT body FROM records WHERE kind=? ORDER BY rowid DESC', (kind,))]


def ident():
    return uuid.uuid4().hex


def defaults():
    for role, system in [('generator', engine.GENERATOR), ('grader', engine.GRADER)]:
        if not any(p['role'] == role and p['name'] == engine.search_prompts.VERSION + ' - ' + role for p in all_records('prompt')):
            save('prompt', dict(id=ident(), role=role, name=engine.search_prompts.VERSION + ' - ' + role, system=system,
                                user_template=engine.TEMPLATE if role == 'generator' else '', created=now()))


@asynccontextmanager
async def lifespan(app):
    defaults()
    for job in all_records('job'):
        if job['status'] in ('queued', 'running'):
            job.update(status='interrupted', stage='Application restarted; retry the job', finished=now())
            save('job', job)
            if job.get('operation')=='optimize':
                try:
                    e=get('experiment',job['experiment_id'])
                    state=e.get('optimization',{})
                    if state.get('id')==job['id'] and state.get('status')=='running':
                        state.update(status='interrupted',stop_reason='interrupted',finished=now())
                        save('experiment',e)
                except HTTPException:
                    pass
    yield


app = FastAPI(title='Querywork local API', version='1.0.0', lifespan=lifespan)


@app.middleware('http')
async def local_access(request: Request, call_next):
    host = request.url.hostname
    if host not in ('127.0.0.1', 'localhost', 'testserver'):
        return JSONResponse({'detail': 'Local access only'}, status_code=403)
    origin = request.headers.get('origin')
    if origin and origin not in ('http://127.0.0.1:8766', 'http://localhost:8766', 'http://127.0.0.1:5173'):
        return JSONResponse({'detail': 'Origin rejected'}, status_code=403)
    if request.url.path.startswith('/api/'):
        bearer = request.headers.get('authorization', '').removeprefix('Bearer ')
        cookie = request.cookies.get('querywork_session', '')
        if not (secrets.compare_digest(bearer, TOKEN) or secrets.compare_digest(cookie, TOKEN)):
            return JSONResponse({'detail': 'Local API token required'}, status_code=401)
    return await call_next(request)


class Case(BaseModel):
    original_search: str = Field(min_length=1, max_length=2000)
    outcome: str = Field(min_length=1, max_length=5000)
    requirements: list[str] = Field(default_factory=list, max_length=20)
    mode: Literal['live', 'demo'] = 'live'


class Prompt(BaseModel):
    role: Literal['generator', 'grader']
    name: str = Field(min_length=1, max_length=120)
    system: str = Field(min_length=1, max_length=20000)
    user_template: str = Field(default='', max_length=10000)


class Action(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=120)
    prompt_id: str | None = None
    feedback: str = Field(default='', max_length=5000)
    target_score: float = Field(default=90, ge=1, le=100)
    batch_size: Literal[5,10] = 5
    max_rounds: int | None = Field(default=None, ge=1, le=100)
    max_queries: int = Field(default=100, ge=1, le=500)
    grader_prompt_id: str | None = None


class Edit(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=6)


class SessionConnection(BaseModel):
    openai_key: SecretStr | None = None
    tavily_key: SecretStr | None = None
    generator_model: str = Field(min_length=1, max_length=200)
    grader_model: str = Field(min_length=1, max_length=200)


class EnvironmentConnection(BaseModel):
    openai_key: SecretStr | None = None
    tavily_key: SecretStr | None = None
    generator_model: str = Field(default='', max_length=200)
    grader_model: str = Field(default='', max_length=200)
    input_usd_per_million: float | None = Field(default=None, ge=0)
    output_usd_per_million: float | None = Field(default=None, ge=0)
    tavily_usd_per_credit: float | None = Field(default=None, ge=0)


@app.post('/api/v1/config/environment')
def save_environment(body: EnvironmentConnection):
    import tempfile
    with LOCK:
        if any(j['status'] in ('queued', 'running') for j in all_records('job')):
            raise HTTPException(409, 'Wait for running jobs before changing the environment')
        updates = {}
        for value, key in ((body.input_usd_per_million,'INPUT_USD_PER_MILLION'),
                           (body.output_usd_per_million,'OUTPUT_USD_PER_MILLION'),
                           (body.tavily_usd_per_credit,'TAVILY_USD_PER_CREDIT')):
            if value is not None:
                updates[key] = str(value)
        for value, key in ((body.openai_key.get_secret_value() if body.openai_key else '', 'OPENAI_API_KEY'),
                           (body.tavily_key.get_secret_value() if body.tavily_key else '', 'TAVILY_API_KEY'),
                           (body.generator_model, 'GENERATOR_MODEL'), (body.grader_model, 'GRADER_MODEL')):
            if value.strip():
                if len(value) > 1024 or any(c in value for c in ('\n', '\r', '\x00')):
                    raise HTTPException(422, 'Environment values must be single-line values under 1024 characters')
                updates[key] = value.strip()
        fd, temporary = tempfile.mkstemp(prefix='.env-', suffix='.tmp', dir=ENV_FILE.parent)
        os.close(fd)
        temporary = Path(temporary)
        try:
            if ENV_FILE.exists():
                temporary.write_bytes(ENV_FILE.read_bytes())
            for key, value in updates.items():
                set_key(temporary, key, value, quote_mode='always')
            os.replace(temporary, ENV_FILE)
        except OSError:
            raise HTTPException(500, 'Could not save the local environment file') from None
        finally:
            temporary.unlink(missing_ok=True)
        load_dotenv(ENV_FILE, override=True)
        return {**configuration(), 'saved': True}


@app.post('/api/v1/config/session')
def session_connection(body: SessionConnection):
    with LOCK:
        if any(j['status'] in ('queued', 'running') for j in all_records('job')):
            raise HTTPException(409, 'Wait for running jobs or cancel them before changing connections')
        for field, key in ((body.openai_key, 'OPENAI_API_KEY'), (body.tavily_key, 'TAVILY_API_KEY')):
            if field and field.get_secret_value().strip():
                os.environ[key] = field.get_secret_value().strip()
        os.environ['GENERATOR_MODEL'] = body.generator_model.strip()
        os.environ['GRADER_MODEL'] = body.grader_model.strip()
        return configuration()


def configuration():
    names = ('OPENAI_API_KEY', 'TAVILY_API_KEY', 'GENERATOR_MODEL', 'GRADER_MODEL')
    missing = [n for n in names if not os.getenv(n)]
    return dict(ready=not missing, missing=missing, openai_configured=bool(os.getenv('OPENAI_API_KEY')), tavily_configured=bool(os.getenv('TAVILY_API_KEY')), generator_model=os.getenv('GENERATOR_MODEL', ''),
                grader_model=os.getenv('GRADER_MODEL', ''), data_directory=str(DATA),
                token_file=str(TOKEN_PATH), live_validation='not_checked',
                input_usd_per_million=os.getenv('INPUT_USD_PER_MILLION',''),
                output_usd_per_million=os.getenv('OUTPUT_USD_PER_MILLION',''),
                tavily_usd_per_credit=os.getenv('TAVILY_USD_PER_CREDIT',''))


@app.get('/api/v1/config')
def config():
    return configuration()


@app.post('/api/v1/config/validate')
def validate_config():
    if not configuration()['ready']:
        raise HTTPException(400, 'Configure the missing values in .env and restart')
    try:
        for model in {os.environ['GENERATOR_MODEL'], os.environ['GRADER_MODEL']}:
            engine.request('GET', 'https://api.openai.com/v1/models/' + model,
                           headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']})
        engine.request('GET', 'https://api.tavily.com/usage',
                       headers={'Authorization': 'Bearer ' + os.environ['TAVILY_API_KEY']})
    except Exception:
        raise HTTPException(400, 'Credential/model validation failed. Check keys, model access, and provider connectivity.') from None
    save('settings', dict(id='validation', valid=True, fingerprint=configuration_fingerprint()))
    return {'valid': True}


def configuration_fingerprint():
    import hashlib
    return hashlib.sha256('|'.join(os.getenv(n, '') for n in
          ('OPENAI_API_KEY', 'TAVILY_API_KEY', 'GENERATOR_MODEL', 'GRADER_MODEL')).encode()).hexdigest()


@app.get('/api/v1/prompts')
def prompts():
    return all_records('prompt')


@app.post('/api/v1/prompts', status_code=201)
def create_prompt(body: Prompt):
    return save('prompt', dict(id=ident(), created=now(), **body.model_dump()))


@app.post('/api/v1/experiments', status_code=201)
def create_case(body: Case):
    defaults()
    requirements = list(dict.fromkeys(r.strip() for r in body.requirements if r.strip()))
    return save('experiment', dict(id=ident(), created=now(), **body.model_dump(exclude={'requirements'}),
        requirements=requirements, models={'generator': os.getenv('GENERATOR_MODEL', ''), 'grader': os.getenv('GRADER_MODEL', '')},
        search_settings=engine.SEARCH_SETTINGS, grader_prompt_id=next(p['id'] for p in all_records('prompt') if p['role']=='grader'), rounds=[], feedback=[], jobs=[]))


@app.get('/api/v1/experiments')
def experiments():
    return [{k: e[k] for k in ('id', 'created', 'original_search', 'outcome', 'mode')} for e in all_records('experiment')]


@app.get('/api/v1/experiments/{eid}')
def experiment(eid: str):
    with LOCK:
        e = get('experiment', eid)
        return {**e, 'job_states': [get('job', jid) for jid in e['jobs']]}


@app.put('/api/v1/experiments/{eid}/queries')
def edit_queries(eid: str, body: Edit):
    with LOCK:
        e = get('experiment', eid)
        ensure_idle(e)
        if not e['rounds'] or any('results' in q for q in e['rounds'][-1]['queries']):
            raise HTTPException(409, 'Generate a new round before editing searched terms')
        if any(not q.strip() or len(q) > 500 for q in body.queries):
            raise HTTPException(422, 'Query text must contain 1–500 characters')
        baseline = e['rounds'][-1]['queries'][0]
        old = {q['text']: q for q in e['rounds'][-1]['queries'][1:]}
        e['rounds'][-1]['queries'] = [baseline] + [old.get(q.strip(), dict(id=ident(), text=q.strip(), note='Manually edited', status='ready')) for q in body.queries]
        return save('experiment', e)


def ensure_idle(e):
    if any(get('job', jid)['status'] in ('queued', 'running') for jid in e['jobs']):
        raise HTTPException(409, 'An operation is already running')


def submit(eid, operation, body):
    with LOCK:
        e = get('experiment', eid)
        previous = next((j for j in all_records('job') if j.get('experiment_id') == eid and j.get('key') == body.idempotency_key), None)
        if previous:
            return previous
        ensure_idle(e)
        if e['mode'] == 'live':
            if not configuration()['ready']:
                raise HTTPException(400, 'API configuration is incomplete. Open Settings or use demo mode.')
            validation = next((s for s in all_records('settings') if s['id'] == 'validation'), {})
            if validation.get('fingerprint') != configuration_fingerprint():
                raise HTTPException(400, 'Validate credentials in Settings before starting live operations')
            if not e['rounds']:
                e['models'] = {'generator': os.environ['GENERATOR_MODEL'], 'grader': os.environ['GRADER_MODEL']}
        if operation == 'refine' and (not body.feedback.strip() or not e['rounds']):
            raise HTTPException(400, 'A previous round and feedback are required')
        if operation == 'refine' and not any(q.get('evaluation') for q in e['rounds'][-1]['queries']):
            raise HTTPException(409, 'Evaluate the current round before refining')
        if operation in ('generate', 'refine') and len(e['rounds']) >= 3:
            raise HTTPException(409, 'The two-refinement limit has been reached; create a new experiment')
        if operation in ('run', 'regrade') and not e['rounds']:
            raise HTTPException(409, 'Generate terms first')
        role = 'generator' if operation in ('generate', 'refine','optimize') else 'grader'
        prompt_id = body.prompt_id or (e.get('grader_prompt_id') if role == 'grader' else None)
        prompt = get('prompt', prompt_id) if prompt_id else next(p for p in all_records('prompt') if p['role'] == role)
        if prompt['role'] != role:
            raise HTTPException(400, 'Wrong prompt role')
        job = dict(id=ident(), experiment_id=eid, key=body.idempotency_key, operation=operation,
            prompt=prompt, feedback=body.feedback, status='queued', stage='Queued', created=now(), cancel=False)
        if operation == 'optimize':
            selected_grader = body.grader_prompt_id or e.get('grader_prompt_id')
            grader = get('prompt', selected_grader) if selected_grader else next(p for p in all_records('prompt') if p['role']=='grader')
            if grader['role'] != 'grader':
                raise HTTPException(400,'Wrong grader prompt role')
            job.update(options=body.model_dump(), grader_prompt=grader)
        save('job',job)
        e['jobs'].append(job['id'])
        save('experiment', e)
        POOL.submit(work, job['id'])
        return job


@app.post('/api/v1/experiments/{eid}/{operation}', status_code=202)
def action(eid: str, operation: Literal['generate', 'run', 'refine', 'regrade','optimize'], body: Action):
    return submit(eid, operation, body)


@app.get('/api/v1/jobs/{jid}')
def job(jid: str):
    return get('job', jid)


@app.post('/api/v1/jobs/{jid}/cancel')
def cancel(jid: str):
    with LOCK:
        j = get('job', jid)
        j['cancel'] = True
        return save('job', j)


def checkpoint(jid, stage):
    with LOCK:
        j = get('job', jid)
        if j['cancel']:
            raise InterruptedError('Canceled; completed results have been retained')
        j.update(stage=stage, status='running')
        save('job', j)


def work(jid):
    job = get('job', jid)
    started = time.monotonic()
    try:
        checkpoint(jid, 'Preparing')
        e = get('experiment', job['experiment_id'])
        operation = job['operation']
        if operation == 'optimize':
            from .optimizer import optimize
            optimize(e, job, checkpoint, lambda value: save('experiment',value), now, ident)
        elif operation in ('generate', 'refine'):
            checkpoint(jid, 'Generating search terms')
            packet = []
            for r in e['rounds']:
                packet.extend(dict(query=q['text'], evaluation=q.get('evaluation'), error=q.get('error')) for q in r['queries'])
            generation_context = {**e, 'feedback': {'user': job['feedback'], 'previous': packet}}
            queries, usage = engine.generate(generation_context, job['prompt'])
            e['rounds'].append(dict(id=ident(), created=now(), generator_prompt=job['prompt'], generator_usage=usage,
                feedback=job['feedback'], queries=[dict(id=ident(), text=e['original_search'], note='Original baseline', status='ready')] +
                [dict(id=ident(), status='ready', **q) for q in queries]))
            if job['feedback']:
                e['feedback'].append(dict(text=job['feedback'], created=now()))
            save('experiment', e)
        else:
            r = e['rounds'][-1]
            r['grader_prompt'] = job['prompt']
            failures = 0
            for i, q in enumerate(r['queries']):
                checkpoint(jid, f'Query {i+1}/{len(r["queries"])}: preparing')
                if operation == 'run' and q.get('status') == 'complete':
                    continue
                q.pop('error', None)
                t = time.monotonic()
                try:
                    if 'results' not in q:
                        if operation == 'regrade':
                            q.update(status='search_failed', error='No saved evidence to regrade')
                            failures += 1
                            continue
                        checkpoint(jid, f'Query {i+1}: searching Tavily')
                        q['results'], q['search_usage'] = engine.search(e, q, i)
                        q['retrieved_at'] = now()
                        q['status'] = 'retrieved'
                        save('experiment', e)
                    checkpoint(jid, f'Query {i+1}: grading in isolated context')
                    if q.get('evaluation'):
                        q.setdefault('evaluation_history', []).append(dict(evaluation=q['evaluation'], prompt=q.get('grader_prompt'), usage=q.get('grader_usage')))
                        q.pop('evaluation')
                    q['evaluation'], q['grader_usage'] = engine.grade(e, q['results'], job['prompt'])
                    q['grader_prompt'] = job['prompt']
                    q['estimated_cost_usd'] = 0.0 if e['mode']=='demo' else engine.estimated_cost(q['grader_usage'], q.get('search_usage', {}).get('credits'))
                    q['status'] = 'complete'
                except InterruptedError:
                    raise
                except Exception as exc:
                    failures += 1
                    q.update(status='grading_failed' if 'results' in q else 'search_failed',
                             error=safe_error(exc))
                finally:
                    q['elapsed_seconds'] = round(time.monotonic() - t, 2)
                    save('experiment', e)
            if failures:
                finish_job(jid, 'partial', f'{failures} queries need attention', started)
                return
        checkpoint(jid, 'Finalizing')
        finish_job(jid, 'complete', 'Complete', started)
    except InterruptedError:
        finish_job(jid, 'canceled', 'Canceled; completed work retained', started)
    except Exception as exc:
        finish_job(jid, 'failed', safe_error(exc), started)


def safe_error(exc):
    if isinstance(exc, ValueError):
        return 'Invalid provider response: ' + str(exc)[:200]
    if isinstance(exc, engine.httpx.HTTPStatusError):
        return f'Provider returned HTTP {exc.response.status_code}. Check API settings and retry.'
    return 'Operation failed. Check provider connectivity and configuration, then retry.'


def finish_job(jid, status, stage, started):
    with LOCK:
        j = get('job', jid)
        j.update(status=status, stage=stage, finished=now(), elapsed_seconds=round(time.monotonic()-started, 2))
        save('job', j)


@app.get('/api/v1/experiments/{eid}/export/{format}')
def export(eid: str, format: Literal['json', 'csv']):
    e = get('experiment', eid)
    headers = {'Content-Disposition': f'attachment; filename="querywork-{eid}.{format}"'}
    if format == 'json':
        return Response(json.dumps(e, indent=2), media_type='application/json', headers=headers)
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['round', 'query', 'score', 'result', 'url', 'grade', 'reason', 'evidence_mode'])
    def safe(value):
        text = str(value)
        return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text
    for n, r in enumerate(e['rounds']):
        for q in r['queries']:
            grades = {j['id']: j for j in q.get('evaluation', {}).get('judgments', [])}
            for result in q.get('results', []):
                j = grades.get(result['id'], {})
                writer.writerow([safe(v) for v in [n+1, q['text'], q.get('evaluation', {}).get('score', ''),
                    result['title'], result['url'], j.get('grade', ''), j.get('reason', ''), 'search excerpts']])
    return Response(output.getvalue(), media_type='text/csv', headers=headers)


@app.get('/{path:path}', include_in_schema=False)
def frontend(path: str):
    base = ROOT / 'dist'
    target = (base / path).resolve()
    if not target.is_relative_to(base.resolve()):
        raise HTTPException(404)
    if not target.is_file():
        target = base / 'index.html'
    if not target.exists():
        return JSONResponse({'detail': 'Build the interface with npm run build; API docs are at /docs'})
    response = FileResponse(target)
    if target.name == 'index.html':
        response.set_cookie('querywork_session', TOKEN, httponly=True, samesite='strict')
    return response

