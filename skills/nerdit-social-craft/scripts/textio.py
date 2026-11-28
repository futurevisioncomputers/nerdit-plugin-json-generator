"""Console output for the social-craft CLIs: the Windows console is cp1252, so every line is printed ASCII-safe."""


def say(line: str) -> None:
    print(line.encode("ascii", "replace").decode())
