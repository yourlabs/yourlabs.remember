yourlabs.remember
=================

Meta-Role for Ansible Automation Architects.

This role provides the magic to smarten Ansible role workflows:

- **massive speedup**: require a dependency role Once And Only Once
- **inventoryless dry**: remember variables injected from the CLI on the host

.. note:: This role does not automatically download dependency roles: that's
          the job of bigsudo command.

0. Dependency injection
-----------------------

0. a) Recursive dependency resolution
`````````````````````````````````````

I'll take the example of what happens with ``yourlabs.traefik`` (a docker based
load balancer) that requires ``yourlabs.docker`` which in turn just installs
docker.

However, for the sake of the example, i will use ``your.parent`` and
``your.child`` to represent the use case of ``yourlabs.docker`` and
``yourlabs.traefik`` respectively.

In ``your.child/requirements.yml``::

   - your.parent

In ``your.parent/requirements.yml``::

   - yourlabs.remember

As such, ``your.child`` depends on ``your.parent``, and ``your.parent``
depends on ``yourlabs.remember``.

.. note:: bigsudo transparently ensures that requirements are installed
          recursively, when you run ``bigsudo your.child``.

0. b) Conditional role inclusion
````````````````````````````````

Without the ``remember`` role, you would normally include the ``your.parent``
role as such at the **top** of ``your.child/tasks/main.yml``::

   - name: Install your.parent prior to running our tasks
     include_role: name=your.parent

However, if you don't want to wait for ``your.parent`` to fully execute
everytime when you execute ``your.child``, you can transform the above task as
such at the **top** of ``your.child/tasks/main.yml``::

   - name: Install your.parent if never done on this host
     include_role: name=yourlabs.remember tasks_from=require_once
     vars:
       rolename: your.parent

As such, running ``bigsudo your.parent`` will create
``/etc/ansible/facts.d/your_parent.fact`` with such content::

   #!/bin/sh
   echo '{
      "state": "installed"
   }'

And when executing ``bigsudo your.child`` will call
``yourlabs.remember/tasks/require_once.yml``, it will find ``"your_parent"`` in
``ansible_facts.ansible_local``, and simply skip including ``your.parent``,
making the execution of ``your.child`` much faster.

0. c) Making a role conditionnaly installable
`````````````````````````````````````````````

Given the above, what happens if you first run ``bigsudo your.parent`` and then
``bigsudo your.child`` ? Well, ``your.parent`` will be executed twice, because
executing ``your.parent`` has not left any trace of its execution.

**Unless**, you call the remember role at the **bottom** of
``your.parent/tasks/main.yml``::

   - name: Register the execution of your.parent on the host persistent facts
     include_role: name=yourlabs.remember
     vars:
       rolename: your.parent

As such, even executing ``your.parent`` outside of
``include_role: name=yourlabs.remember tasks_from=require_once`` will leave a
trace that ``yourlabs.remember`` will be able to pickup.

That's all for that ... but wait ! There's more following ;)

1. Inventory-less pattern
-------------------------

After a lot of discussion with some colleagues, in a mission where each of us
has a little project for a pizza team and a handful of servers, that having an
inventory was an un-necessary burden. For small projects like ours (but we have
many), we end up vaulting the handful of variables that differ from an
environment to another with a single passphrase that we then store in the CI
environment. We decided to try cutting that middleman, and just store an env
file in CI variables for each environment. It turned out this did the job just
as fine but will less effort.

1. a) Storing inventory variables on the host
`````````````````````````````````````````````

At the end of ``your.parent/tasks/main.yml``, add the variable names to
save it to a host fact::

   - name: Register the execution of your.parent on the host persistent facts
     include_role: name=yourlabs.remember
     vars:
       rolename: your.parent
       varnames:
       - url

As such, running ``bigsudo your.parent url=http://foo`` will create
``/etc/ansible/facts.d/your_parent.fact`` with such content::

   #!/bin/sh
   echo '{
      "url": "http://foo",
      "state": "installed"
   }'

This will still register your role as installed in a host fact, but also with
the ``url`` variable.

1. b) Remembering variables from host facts
```````````````````````````````````````````

Thanks to the fact that was created, you will be able to run
``bigsudo your.parent`` from now on without having to re-specify the ``url``
variable, **if** you have defined ``your.parent/vars/main.yml`` as such for
example::

   ---
   # note that dots are not acceptable in facts names last time i checked, so
   # we convert dots to underscores:
   url: '{{ ansible_facts.ansible_local.your_parent.url|default("example.com") }}'

In this position:

- You can still change ``url`` from the command line because command line extra
  variables have predecence over definitions.
- When not set in the command line, it will try to find it in the facts, and
  recover its state from last time the variable was set.
- Finnaly, if no CLI nor fact variable was found, it will set a default of
  ``"example.com"``.

From now on, you will only have to specify variables when you want to change
them, you don't need to store them in an inventory if you use this pattern.
Also note that you can still use ``yourlabs.remember`` with an inventory,
without variable in host facts (which look like SaltStack grains, except still
agent-less).

I recommend trying this out for small projects (pizza team, handful of servers
with different purpose).

Conclusion
==========

Finnaly we're getting to the point where we have a clear and relatively easy way to:

- **dynamically inject** dependency roles to speed up subsequent executions of
  a role, effectively preventing un-necessary double execution of dependency
  roles (such as docker, load balancers, lower level automation ...)
- **suppress the inventory** because each server keeps its variables, it's also
  DRY by the way, so that's still one repo less you will have to worry about !

Credits
=======

Thanks *totakoko* from ``beta.gouv.fr`` for the long discussions and for
demonstrating that my inventory was overkill and that it was possible without ;)

Thanks *agaffney* and *mackerman* from ``#ansible``@``irc.freenode.net``, on
of the best IRC channels !

And thank *you* for reading my little adventure !
