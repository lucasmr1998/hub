import re
import logging


class PIIFilter(logging.Filter):
    """Mascara dados pessoais (CPF, email, telefone) nos logs."""

    PATTERNS = [
        (re.compile(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b'), 'XXX.XXX.XXX-XX'),  # CPF
        (re.compile(r'\b\d{11}\b'), 'XXXXXXXXXXX'),  # CPF sem formatação
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[email]'),  # Email
        (re.compile(r'\b(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}[\s-]?\d{4}\b'), '[telefone]'),  # Telefone BR
    ]

    def filter(self, record):
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern, replacement in self.PATTERNS:
                        arg = pattern.sub(replacement, arg)
                new_args.append(arg)
            record.args = tuple(new_args)
        return True
