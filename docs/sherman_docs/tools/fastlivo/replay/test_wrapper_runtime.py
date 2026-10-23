"""Execute wrapper safety functions with fake commands; never access Docker."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


@unittest.skipUnless(shutil.which('timeout') and shutil.which('flock'), 'requires GNU timeout and flock')
class WrapperRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = Path(__file__).with_name('run_replay.sh').read_text()

    def function(self, name):
        start = self.source.index(name + '() {')
        return self.source[start:self.source.index('\n}', start) + 2]

    def command(self, name, body):
        path = self.root / name
        path.write_text('#!/usr/bin/env bash\n' + body)
        path.chmod(0o700)

    def run_shell(self, body):
        env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ['PATH'],
                   DOCKER_PID_FILE=str(self.root / 'docker.pid'))
        return subprocess.run(['bash', '-c', body], env=env, cwd=self.root,
                              text=True, capture_output=True, timeout=8)

    def test_follower_releases_lock_and_collect_reaps_only_its_client(self):
        self.command('sudo', '[[ "$1" == -n ]] && shift\nexec "$@"\n')
        self.command('docker', 'echo $$ > "$DOCKER_PID_FILE"\nexec sleep 5\n')
        # Extract the real follower command and cleanup function, not replicas.
        follower = next(line for line in self.source.splitlines() if 'docker logs --follow' in line)
        script = '\n'.join([
            'OUT="$PWD"; C=owned-test-container; created=0',
            self.function('collect'),
            'exec 9>"$PWD/lock"', 'flock -n 9', follower, 'log_pid=$!',
            'for i in {1..100}; do [[ -s "$DOCKER_PID_FILE" ]] && break; sleep 0.01; done',
            '[[ -s "$DOCKER_PID_FILE" ]] || exit 3',
            'exec 9>&-', 'flock -n "$PWD/lock" true || exit 4',
            'true', 'collect',
        ])
        started = time.monotonic()
        result = self.run_shell(script)
        self.assertLess(time.monotonic() - started, 3, 'cleanup must stop follower, not await natural exit')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        pid = int((self.root / 'docker.pid').read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_failed_noninteractive_sudo_cannot_confirm_stopped(self):
        self.command('sudo', 'echo "sudo: a password is required" >&2\nexit 1\n')
        result = self.run_shell('\n'.join([
            'OUT="$PWD"; C=owned-test-container', self.function('confirm_stopped'),
            'if confirm_stopped; then exit 7; fi',
            'grep -q "password is required" "$OUT/state-check.stderr.log"',
        ]))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
