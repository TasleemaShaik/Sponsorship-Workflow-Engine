# sponsorship_sync/app.py
"""
Install dependencies:
    pip install flask apscheduler

A Flask app that combines tasks from three sources:
- Salesforce
- Asana
- Google Calendar

Features:
1. POST /sync-tasks: Accepts sponsor_id, fetches mock tasks, stores them in-memory.
2. GET  /tasks: Returns stored tasks; supports filtering by sponsor_id and/or status.
3. PATCH /tasks/<int:idx>: Update status of a stored task.
4. Background job: Periodically re-syncs tasks for configured sponsors.
5. Simple API key auth on all endpoints.

Data Model (in-memory for prototype):
- Each task is a dict with:
    * sponsor_id (str)
    * source (str)
    * name (str)
    * due_date (YYYY-MM-DD)
    * status (str)

Usage examples:
  # Sync tasks for a sponsor:
  curl -X POST http://localhost:5000/sync-tasks \
       -H "Content-Type: application/json" \
       -H "X-API-KEY: secret-token-123" \
       -d '{"sponsor_id":"sponsor-abc"}'

  # List all stored tasks:
  curl http://localhost:5000/tasks \
       -H "X-API-KEY: secret-token-123"

To extend:
- Replace mocks with real API calls (Salesforce REST, Asana SDK, Google Calendar API).
- Persist tasks in SQLite / SQLAlchemy.
- Use OAuth2 or JWT for auth.
- Containerize and scale with a scheduler or serverless functions.
- Future AI: smart reminders, priority predictions.
"""

from flask import Flask, request, jsonify, abort
from datetime import date, datetime
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)

# ======== Authentication ========
API_KEY = 'secret-token-123'

def check_api_key():
    key = request.headers.get('X-API-KEY')
    if key != API_KEY:
        abort(401, 'Invalid or missing API key')

# ======== In-memory Store ========
# List to hold tasks; in real app, swap for DB
TASK_STORE = []
SYNC_SPONSORS = set()  # sponsors to auto-sync

# ======== Mock Integration Functions ========
def get_salesforce_tasks(sponsor_id):
    return [
        {'sponsor_id': sponsor_id, 'source': 'salesforce', 'name': 'Finalize contract', 'due_date': '2025-08-01', 'status': 'pending'},
        {'sponsor_id': sponsor_id, 'source': 'salesforce', 'name': 'Upload logo', 'due_date': '2025-08-05', 'status': 'pending'},
    ]

def get_asana_tasks(sponsor_id):
    return [
        {'sponsor_id': sponsor_id, 'source': 'asana', 'name': 'Post campaign assets', 'due_date': '2025-07-30', 'status': 'done'},
        {'sponsor_id': sponsor_id, 'source': 'asana', 'name': 'Review creative brief', 'due_date': '2025-08-03', 'status': 'pending'},
    ]

def get_google_calendar_tasks(sponsor_id):
    return [
        {'sponsor_id': sponsor_id, 'source': 'google_calendar', 'name': 'Activation deadline', 'due_date': '2025-08-10', 'status': 'pending'},
        {'sponsor_id': sponsor_id, 'source': 'google_calendar', 'name': 'Post-event report', 'due_date': '2025-08-20', 'status': 'pending'},
    ]

# ======== Core Endpoints ========
@app.route('/sync-tasks', methods=['POST'])
def sync_tasks():
    """
    Manually trigger a sync for one sponsor.
    Body: { "sponsor_id": "..." }
    """
    check_api_key()
    data = request.get_json() or {}
    sponsor_id = data.get('sponsor_id')
    if not sponsor_id:
        abort(400, 'Missing sponsor_id')

    # Mark for periodic sync
    SYNC_SPONSORS.add(sponsor_id)

    # Fetch and store tasks
    tasks = []
    tasks += get_salesforce_tasks(sponsor_id)
    tasks += get_asana_tasks(sponsor_id)
    tasks += get_google_calendar_tasks(sponsor_id)

    # Overwrite old tasks for this sponsor
    global TASK_STORE
    TASK_STORE = [t for t in TASK_STORE if t['sponsor_id'] != sponsor_id]
    TASK_STORE.extend(tasks)

    return jsonify({'tasks': tasks}), 200

@app.route('/tasks', methods=['GET'])
def list_tasks():
    """
    List all tasks, with optional filters:
    ?sponsor_id=...  &status=pending/done
    """
    check_api_key()
    sponsor = request.args.get('sponsor_id')
    status = request.args.get('status')

    results = TASK_STORE
    if sponsor:
        results = [t for t in results if t['sponsor_id'] == sponsor]
    if status:
        results = [t for t in results if t['status'] == status]

    return jsonify({'tasks': results}), 200

@app.route('/tasks', methods=['PATCH'])
def update_task_by_fields():
    check_api_key()
    data = request.get_json() or {}
    sponsor = data.get('sponsor_id')
    source  = data.get('source')
    name    = data.get('name')
    new_status = data.get('status')
    if not all([sponsor, source, name, new_status]):
        abort(400, 'Must include sponsor_id, source, name, and status')
    matched = False
    for task in TASK_STORE:
        if (task['sponsor_id']==sponsor 
            and task['source']==source 
            and task['name']==name):
            task['status'] = new_status
            matched = True
    if not matched:
        abort(404, 'No matching task found')
    return jsonify({'updated': True}), 200

# ======== Background Sync Job ========
def periodic_sync():
    """
    Runs every 5 minutes to re-sync tasks for all sponsors in SYNC_SPONSORS.
    """
    for sponsor_id in list(SYNC_SPONSORS):
        tasks = []
        tasks += get_salesforce_tasks(sponsor_id)
        tasks += get_asana_tasks(sponsor_id)
        tasks += get_google_calendar_tasks(sponsor_id)
        # Replace in store
        global TASK_STORE
        TASK_STORE = [t for t in TASK_STORE if t['sponsor_id'] != sponsor_id]
        TASK_STORE.extend(tasks)

# Start scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=periodic_sync, trigger='interval', minutes=5)
scheduler.start()
# Clean up on exit
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    # Run the app on http://localhost:5000
    app.run(debug=True)
