#!/usr/bin/python3
"""Verificação offline usando apenas chaves públicas; não instala nem publica."""
from publication_verify import main
import sys

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Verificação recusada: {exc}', file=sys.stderr)
        raise SystemExit(1)
