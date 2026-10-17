"""Validate saved ordinary-container inspection before start and before commit."""
import json
from pathlib import Path
import sys


def validate(data: dict, phase: str, name: str = 't59-fastlivo-build') -> None:
    """Reject missing/mismatched limits, elevated access, and unsuccessful state."""
    if phase not in ('pre', 'post'):
        raise ValueError('Unknown validation phase')
    if data.get('Name') != '/' + name:
        raise ValueError('Unexpected container name')
    config = data.get('HostConfig', {})
    expected = dict(Memory=8589934592, MemorySwap=8589934592,
                    NanoCpus=2000000000, CpuQuota=0, CpuPeriod=0,
                    PidsLimit=512, Privileged=False, NetworkMode='bridge')
    for key, value in expected.items():
        if key not in config or config[key] != value:
            raise ValueError(f'HostConfig.{key}: expected {value!r}, got {config.get(key)!r}')
    for key in ('Binds', 'Mounts', 'Devices', 'DeviceRequests', 'CapAdd', 'VolumesFrom'):
        if config.get(key) not in (None, []):
            raise ValueError(f'Unexpected or missing HostConfig.{key}')
    if data.get('Mounts') != []:
        raise ValueError('Container has mounts or inspection is incomplete')
    state = data.get('State', {})
    for key, value in dict(Status='created' if phase == 'pre' else 'exited',
                           Running=False, ExitCode=0, OOMKilled=False, Error='').items():
        if key not in state or state[key] != value:
            raise ValueError(f'Unexpected State.{key}: {state.get(key)!r}')


if __name__ == '__main__':
    records = json.loads(Path(sys.argv[2]).read_text())
    if len(records) != 1:
        raise ValueError('Expected exactly one container inspection')
    validate(records[0], sys.argv[1], sys.argv[3] if len(sys.argv) > 3 else 't59-fastlivo-build')
    print(f'{sys.argv[1]} container validation passed')
