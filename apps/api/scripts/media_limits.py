"""Set child limits before exec, without unsafe preexec_fn in threaded workers."""
import os
import sys
from pathlib import Path


def main():
    import resource
    memory, cpu, file_size = map(int, sys.argv[1:4])
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_size, file_size))
    command = sys.argv[4:]
    if not command or Path(command[0]).name not in {'ffmpeg', 'ffprobe', 'packager'}:
        raise ValueError('Unsupported media executable')
    os.execvp(command[0], command)


if __name__ == '__main__':
    main()
