#!/usr/bin/python


class FilterModule(object):
    def filters(self):
        return dict(
            remember=self.remember,
            as_role_name=self.as_role_name,
            as_fact_name=self.as_fact_name,
        )

    def as_role_name(self, rolename):
        """Makes your.role out of github.com/you/your.role."""
        return rolename.rstrip('/').split('/')[-1].split(',')[0]

    def as_fact_name(self, rolename):
        """Replace dots with underscore for same fact name."""
        return self.as_role_name(rolename).replace('.', '_')

    def remember(self, facts, rolename, varname, default=None):
        """Do not use unless the top of your tasks include this role !"""
        factname = self.as_fact_name(rolename)

        if factname not in facts['ansible_local']:
            return default

        fact = facts['ansible_local'][factname]

        if varname not in fact:
            return default

        return fact[varname]
