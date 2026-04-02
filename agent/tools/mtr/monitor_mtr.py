"""MTR (My Traceroute) wrapper — parses mtr JSON output for ICMP/TCP/UDP modes."""
import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MtrHop:
    """Single hop in an MTR result."""
    hop: int
    host: str
    loss_percent: float
    sent: int
    recv: int
    last: float  # ms
    avg: float   # ms
    best: float  # ms
    worst: float # ms
    stdev: float # ms


@dataclass
class MtrResult:
    """Full MTR result."""
    success: bool = False
    hops: List[MtrHop] = field(default_factory=list)
    error: Optional[str] = None
    src: str = ''
    dst: str = ''


def run_mtr(target: str, protocol: str = 'icmp', port: int = None,
            count: int = 5, timeout: int = 10) -> MtrResult:
    """Run mtr and return parsed result.

    Args:
        target: destination host/IP
        protocol: 'icmp', 'tcp', or 'udp'
        port: target port (required for tcp/udp)
        count: number of pings per hop
        timeout: timeout in seconds
    """
    cmd = ['mtr', '--json', '-c', str(count),
           '-G', '0.5', '-Z', '1', '-i', '0.1']

    if protocol == 'tcp':
        cmd.append('--tcp')
        if port:
            cmd.extend(['-P', str(port)])
        else:
            cmd.extend(['-P', '80'])
    elif protocol == 'udp':
        cmd.append('--udp')
        if port:
            cmd.extend(['-P', str(port)])
        else:
            cmd.extend(['-P', '53'])
    # icmp is the default, no flag needed

    cmd.append(target)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 30
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            return MtrResult(success=False, error=f'mtr failed (rc={result.returncode}): {stderr[:200]}')

        return _parse_mtr_json(result.stdout)

    except subprocess.TimeoutExpired:
        return MtrResult(success=False, error='mtr timed out')
    except FileNotFoundError:
        return MtrResult(success=False, error='mtr command not found')
    except Exception as e:
        return MtrResult(success=False, error=str(e)[:200])


def _parse_mtr_json(raw_output: str) -> MtrResult:
    """Parse mtr --json output."""
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as e:
        return MtrResult(success=False, error=f'Failed to parse mtr JSON: {e}')

    report = data.get('report', data)
    mtr_meta = report.get('mtr', {})
    src = mtr_meta.get('src', '')
    dst = mtr_meta.get('dst', '')
    hubs = report.get('hubs', [])

    if not hubs:
        return MtrResult(success=False, error='No hops in mtr output')

    hops = []
    for hub in hubs:
        hop = MtrHop(
            hop=hub.get('count', 0),
            host=hub.get('host', '???'),
            loss_percent=hub.get('Loss%', hub.get('Loss', 0.0)),
            sent=hub.get('Snt', 0),
            recv=hub.get('Snt', 0) - int(hub.get('Snt', 0) * hub.get('Loss%', hub.get('Loss', 0.0)) / 100),
            last=hub.get('Last', 0.0),
            avg=hub.get('Avg', 0.0),
            best=hub.get('Best', 0.0),
            worst=hub.get('Wrst', hub.get('Worst', 0.0)),
            stdev=hub.get('StDev', 0.0),
        )
        hops.append(hop)

    return MtrResult(success=True, hops=hops, src=src, dst=dst)


def check_mtr_available() -> tuple[bool, str]:
    """Check if mtr is installed and accessible."""
    try:
        result = subprocess.run(['mtr', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, f'mtr returned error code {result.returncode}'
    except FileNotFoundError:
        return False, 'mtr command not found'
    except Exception as e:
        return False, str(e)
