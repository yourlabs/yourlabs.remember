yourlabs.remember
`````````````````

Meta-Role for Ansible Automation Architects.

This role provides the magic to smarten Ansible role workflows:

- **massive speedup**: require a dependency role Once And Only Once
- **inventoryless dry**: remember variables injected from the CLI on the host
- **CLI variable prompt**: interactive questioning of the user for facts

.. note:: This role does not automatically download dependency roles: that's
          the job of `bigsudo
          <https://pypi.org/project/bigsudo/>`_ command.

Demo
====

The easiest way to try it out::

   pip install --user bigsudo
   ~/.local/bin/bigsudo yourlabs.fqdn user@somehost
   # Or if you feel brave (skip hostname to apply on localhost)
   ~/.local/bin/bigsudo yourlabs.traefik

Of course you could also use ``ansible`` commands, but then it would be more
commands and options. We're getting inspiration from the *practice* of kubectl,
for little servers, non-HA services, and pizza teams. Even if, I would
personnaly still use ``bigsudo yourlabs.k8s`` to configure k8s instances if i
had to ...

Usage
=====

This role allows you to define what variables are needed in your own role,
along with things such as the description that will be displayed to the user,
defaults, regexp validation and so on.

OAOO role dependency injection
------------------------------

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
          recursively when you run ``bigsudo your.child``.

Without the ``remember`` role, you would normally include the ``your.parent``
role as such at the **top** of ``your.child/tasks/main.yml``::

   - name: Install your.parent prior to running our tasks
     include_role: name=your.parent

However, this will play the role everytime, making execution longer. If you
don't want to wait for ``your.parent`` to fully execute everytime when you
execute ``your.child``, you can transform the above task as such at the **top**
of ``your.child/tasks/main.yml``:

.. code-block:: yaml

   - name: Install your.parent if never done on this host
     include_role: name=your.parent
     when: ansible_facts['ansible_local']['your_parent']['state']|default('') != 'success'

For this to work, you will need to add the following at the end of
``your.parent/tasks/main.yml``:

.. code-block:: yaml

  - include_role: name=yourlabs.remember
    vars:
      remember_extra: {state: success}
      remember_fact: your_parent

As such, running ``bigsudo your.parent`` (also works with ansible) will create
``/etc/ansible/facts.d/your_parent.fact`` with such content::

   #!/bin/sh
   echo '{
      "state": "success"
   }'

This is how you can skip including the role next time.

Read on to add your custom persistent role variables with interactive
configuration.

Interactive role configuration
------------------------------

In ``your.parent/vars/main.yml``, define ``remember_fact`` that is the
namespaces for this role deployment variable as well as the variables your role
depends on as such::

  ---
  remember_fact: your_parent
  remember:
  - name: email_enable
    question: Enable a custom email ?
    default: false
    type: bool
  - name: email
    question: What email to use ?
    type: email
    default: '{{ lookup("env", "USER") }}@{{ inventory_hostname }}'
    when: email_enable

Then, in ``your.parent/tasks/main.yml``, you can include ``yourlabs.remember``
and it will load up the variables and ask user for new variables
interactively, pretty fast thanks to the Action Plugin::

   - include_role: name=yourlabs.remember

You can do more, refer to the ``test.yml`` playbook of course, which i run with
``ansible-playbook -c local -i localhost, test.yml -v --become``:

.. include:: test.yml

Multiple deployments: namespacing variables
-------------------------------------------

To enable multiple deployments of a role on the same host, ie. to enable
**eXtreme DevOps** you will need your ``remember_fact`` to depend on a variable.

For example, you want to deploy a docker-compose into different directories on
your host. As such, you will require a ``home`` variable:

.. code-block:: yaml

    remember:
    - name: home
      question: What home dir to deploy to ? (must start with /home for the regexp example)
      default: /home/test
      type: path
      regexp: /home.*

That means that if the user doesn't pass an ``home`` variable on the command
line (ie. with ``-e home=/home/bar``) it will prompt for the home directory.
Now, all we have to do is re-use that home variable into the ``remember_fact``
so that it will namespace variables per home directory:

.. code-black:: yaml

    remember_fact: your_role_j2((home))

As you can see, we use ``j2(( ))`` instead of ``{{ }}``, this is to prevent
Ansible from rendering this before getting a value for the home variable. In
fact, the remember action plugin will:

- try to render ``remember_fact`` to load existing variables if any,
- catch ``AnsibleUndefinedVariable`` exceptions,
- find the definitions for the undefined variables it needs in ``remember``,
- ask for them without saving
- load the existing variables
- and ask for any new variables

Conclusion
==========

Finnaly we're getting to the point where we have a clear and relatively easy way to:

- **dynamically inject** dependency roles to speed up subsequent executions of
  a role, effectively preventing un-necessary double execution of dependency
  roles (such as docker, load balancers, lower level automation ...)
- **suppress the inventory** because each server keeps its variables, it's also
  DRY by the way, so that's still one repo less you will have to worry about !
- **interactive fact prompt** no more need to read the docs before executing a
  role you found on internet as root !

Credits
=======

Thanks *totakoko* from ``beta.gouv.fr`` for the long discussions and for
demonstrating that my inventory was overkill and that it was possible without ;)

Thanks to ``#ansible``@``irc.freenode.net``, on of the best IRC channels, namely:

- agaffney
- mackerman
- jborean93

And thank *you* for reading my little adventure !
