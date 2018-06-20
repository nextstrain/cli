from sys import stderr

def warn(*args):
    print(*args, file = stderr)
