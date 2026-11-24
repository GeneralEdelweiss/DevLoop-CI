import copy
import unittest
from ci_admission import verify_run

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.rev='a'*40
        self.repo='example/synthetic'
        self.workflow='.github/workflows/test.yml'
        self.run={'id':1,'run_attempt':2,'head_sha':self.rev,'head_branch':'main',
                  'event':'push','path':self.workflow,'status':'completed','conclusion':'success',
                  'head_repository':{'full_name':self.repo,'private':False}}
        self.jobs={'total_count':2,'jobs':[
            {'name':name,'run_id':1,'run_attempt':2,'head_sha':self.rev,
             'status':'completed','conclusion':'success','labels':[label]}
            for name,label in [('linux','ubuntu-latest'),('windows','windows-latest')]]}
    def verify(self,run=None,jobs=None):
        return verify_run(self.run if run is None else run,
                          self.jobs if jobs is None else jobs,
                          repository=self.repo,revision=self.rev,workflow=self.workflow,
                          required_jobs={'linux':'ubuntu-latest','windows':'windows-latest'})
    def test_good(self):
        self.assertTrue(self.verify())
    def test_wrong_run(self):
        for key,value in [('head_sha','b'*40),('event','pull_request'),('path','other'),
                          ('status','in_progress'),('conclusion','failure'),('head_branch','dev')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.verify(run={**self.run,key:value})
    def test_private_or_wrong_repo(self):
        for repo in [{'full_name':self.repo,'private':True},{'full_name':'other','private':False}]:
            with self.assertRaises(ValueError):
                self.verify(run={**self.run,'head_repository':repo})
    def test_missing_or_truncated(self):
        for jobs in [{'total_count':3,'jobs':self.jobs['jobs']},
                     {'total_count':1,'jobs':self.jobs['jobs'][:1]}]:
            with self.assertRaises(ValueError):
                self.verify(jobs=jobs)
    def test_wrong_job(self):
        for key,value in [('run_id',3),('run_attempt',1),('head_sha','b'*40),('conclusion','skipped'),
                          ('labels',['self-hosted','windows-latest']),('labels',['ubuntu-latest']),
                          ('name','linux')]:
            jobs=copy.deepcopy(self.jobs)
            jobs['jobs'][1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.verify(jobs=jobs)
