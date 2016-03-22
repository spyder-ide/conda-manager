# -*- coding: utf-8 -*-

def human_bytes(n):
    """
    Return the number of bytes n in more human readable form.
    """
    if n < 1024:
        return '%d B' % n
    k = n/1024
    if k < 1024:
        return '%d KB' % round(k)
    m = k/1024
    if m < 1024:
        return '%.1f MB' % m
    g = m/1024
    return '%.2f GB' % g


def split_canonical_name(cname):
    """
    Split a canonical package name into (name, version, build) strings.
    """
    return tuple(cname.rsplit('-', 2))
