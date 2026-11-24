"""Generic fail-closed CI evidence validation; no product-specific data."""
import re


def verify_run(run, inventory, *, repository, revision, workflow, required_jobs):
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Invalid expected revision')
    if (run.get('head_sha') != revision or run.get('head_branch') != 'main'
            or run.get('event') != 'push' or run.get('path') != workflow
            or run.get('status') != 'completed' or run.get('conclusion') != 'success'
            or run.get('head_repository', {}).get('full_name') != repository
            or run.get('head_repository', {}).get('private') is not False
            or type(run.get('id')) is not int or type(run.get('run_attempt')) is not int):
        raise ValueError('Unverified public CI run')
    jobs = inventory.get('jobs')
    if not isinstance(jobs, list) or inventory.get('total_count') != len(jobs):
        raise ValueError('Incomplete CI job inventory')
    seen = set()
    for job in jobs:
        name = job.get('name')
        if (name in seen or job.get('run_id') != run['id']
                or job.get('run_attempt') != run['run_attempt']
                or job.get('head_sha') != revision
                or job.get('status') != 'completed' or job.get('conclusion') != 'success'
                or not isinstance(job.get('labels'), list)
                or 'self-hosted' in job['labels']):
            raise ValueError('Unverified CI job')
        seen.add(name)
        if name in required_jobs and required_jobs[name] not in job['labels']:
            raise ValueError('Incorrect hosted runner label')
    if not required_jobs or not set(required_jobs) <= seen:
        raise ValueError('Required hosted jobs missing')
    return True
