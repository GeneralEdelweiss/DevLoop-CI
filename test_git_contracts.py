"""Real, disposable Git repositories; no external repository or credentials."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class GitContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'Quell kopie'
        self.repo.mkdir()
        # Do not inherit signing, global filters, hooks or external Git state.
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        self.git('init', '-q', '-b', 'main')
        for key, value in [('user.name', 'Fixture'), ('user.email', 'fixture@example.invalid'),
                           ('core.autocrlf', 'false'), ('core.hooksPath', str(self.root / 'no-hooks'))]:
            self.git('config', key, value)
        self.commit('initial', {'a.txt': b'one\n', 'b.txt': b'control\n'})

    def git(self, *args, repo=None, check=True):
        result = subprocess.run(['git', '-C', str(repo or self.repo), *args], env=self.env,
                                capture_output=True, timeout=30, check=check)
        return result

    def output(self, *args, repo=None):
        return self.git(*args, repo=repo).stdout.decode('utf-8').strip()

    def commit(self, message, files):
        for name, raw in files.items():
            (self.repo / name).write_bytes(raw)
            self.git('add', '--', name)
        self.git('commit', '-qm', message)
        return self.output('rev-parse', 'HEAD')

    def test_frozen_blob_bytes_and_scope(self):
        parent = self.output('rev-parse', 'HEAD')
        child = self.commit('change', {'a.txt': b'two\n'})
        self.assertEqual(self.output('rev-parse', 'HEAD^'), parent)
        self.assertEqual(self.output('diff', '--name-only', parent, child), 'a.txt')
        self.assertEqual(self.git('show', parent + ':b.txt').stdout,
                         self.git('show', child + ':b.txt').stdout)
        self.assertEqual(self.git('show', child + ':a.txt').stdout, b'two\n')

    def test_stale_compare_and_swap_ref_is_rejected(self):
        parent = self.output('rev-parse', 'HEAD')
        self.git('branch', 'published', parent)
        child = self.commit('next', {'a.txt': b'two\n'})
        self.git('update-ref', 'refs/heads/published', child, parent)
        result = self.git('update-ref', 'refs/heads/published', parent, parent, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output('rev-parse', 'published'), child)

    def test_dirty_checkout_is_detected(self):
        self.assertEqual(self.output('status', '--porcelain'), '')
        (self.repo / 'a.txt').write_bytes(b'changed\n')
        self.assertIn('a.txt', self.output('status', '--porcelain', '--untracked-files=no'))
        self.assertEqual(self.git('show', 'HEAD:a.txt').stdout, b'one\n')

    def test_clone_does_not_change_original(self):
        parent = self.output('rev-parse', 'HEAD')
        target = self.root / 'candidate'
        self.git('-c', 'core.autocrlf=true', 'clone', '--no-local', '--no-hardlinks',
                 '--no-checkout', str(self.repo), str(target), repo=self.root)
        self.git('config', 'core.autocrlf', 'false', repo=target)
        self.git('remote', 'remove', 'origin', repo=target)
        self.git('checkout', '--detach', parent, repo=target)
        self.assertEqual(self.output('status', '--porcelain', repo=target), '')
        self.assertEqual(self.output('remote', repo=target), '')
        (target / 'a.txt').write_bytes(b'candidate\n')
        self.assertEqual((self.repo / 'a.txt').read_bytes(), b'one\n')
        self.assertEqual(self.output('rev-parse', 'HEAD'), parent)
