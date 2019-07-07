#!/usr/bin/python
import os
import re

from jinja2.filters import do_mark_safe as safe


class FilterModule(object):
    def filters(self):
        return dict(
            remember=self.remember,
            as_role_name=self.as_role_name,
            as_fact_name=self.as_fact_name,
            column_count=self.column_count,
            fg=self.fg,
            bg=self.bg,
            center=self.center,
            table=self.table,
            horizontalize=self.horizontalize,
            validate=self.validate,
        )

    def as_role_name(self, rolename):
        """Makes your.role out of github.com/you/your.role."""
        return rolename.rstrip('/').split('/')[-1].split(',')[0]

    def as_fact_name(self, rolename):
        """Replace dots with underscore for same fact name."""
        return self.as_role_name(rolename).replace('.', '_')

    def fg(self, color):
        if color:
            ret = "\33[38;5;" + str(color) + "m"
        else:
            ret = "\33[0m"
        return safe(ret)

    def bg(self, color):
        if color:
            ret = "\33[48;5;" + str(color) + "m"
        else:
            ret = "\33[0m"
        return safe(ret)

    def center(self, text):
        """Center text in the middle of the screen."""
        res = []
        for text in text.strip().split('\n'):
            width = self.column_count()
            padding = int((width - len(text)) / 2)
            res.append(' ' * padding + text)
        return '\n'.join(res)

    def table(self, left, right):
        spaces = self.column_count() - len(left) - len(right)
        if spaces <= 3:
            return left + '\n' + right
        return left + (' ' * spaces) + right

    def column_count(self):
        """Return the number of columns on the terminal according to python."""
        cnt = int(os.get_terminal_size(0)[0])
        if cnt > 98:  # my arbitrary taste hope you like it ...
            cnt = 98
        return cnt

    def horizontalize(self, caracter):
        """Multiply caracter by screen width."""
        return str(caracter) * self.column_count()

    def validate(self, value, rule):
        """Return True if value passes rule."""
        if not rule:
            return True

        if re.match(rule, value):
            return True

        return False

    def remember(self, facts, rolename, varname, default=None):
        """Do not use unless the top of your tasks include this role !"""
        factname = self.as_fact_name(rolename)

        if factname not in facts['ansible_local']:
            return default

        fact = facts['ansible_local'][factname]

        if varname not in fact:
            return default

        return fact[varname]
