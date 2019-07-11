yourlabs.remember
`````````````````

Meta-Role for Ansible Automation Architects.

This role provides the magic to smarten Ansible role workflows:

- **massive speedup**: require a dependency role Once And Only Once
- **inventoryless dry**: remember variables injected from the CLI on the host
- **CLI variable prompt**: interactive questioning of the user for facts

.. note:: This role does not automatically download dependency roles: that's
          the job of bigsudo command.

Demo
====

The easiest way to try it out::

   pip install --user bigsudo
   ~/.local/bin/bigsudo yourlabs.fqdn user@somehost

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
of ``your.child/tasks/main.yml``::

   - name: Install your.parent if never done on this host
     include_role: name=yourlabs.remember tasks_from=require_once
     vars:
       rolename: your.parent

As such, running ``bigsudo your.parent`` (also works with ansible) will create
``/etc/ansible/facts.d/your_parent.fact`` with such content::

   #!/bin/sh
   echo '{
      "state": "success"
   }'

This is how ``yourlabs.remember`` will skip including the role next time. Read
on to add your custom persistent role variables with interactive configuration.

Interactive role configuration
------------------------------

In ``your.parent/vars/main.yml``, define ``rolevars`` as such::

  ---
  rolevars:
    - name: domain_enable
      question: Enable a custom domain ?
      default: false
      regexp: 'true|false'
    - name: domain
      question: What domain do you want to setup ?
      regexp: '\w+\.[\w+.]+'
      default: '{{ inventory_hostname }}'

  # the when for variables must be set in global variables to leverage lazy
  # initialization
  domain_when: '{{ domain_enable }}'

  # required to namespace the persistent fact properly
  rolename: your.parent

Then, in ``your.parent/tasks/main.yml``, you can include
``yourlabs.remember`` and it will load up the variables and ask user for new
variables interactively::

   - include_role: name=yourlabs.remember

The prompt itself is pretty self-explanatory, it can look like::

   [yourlabs.remember : Asking for role variable fqdn]
   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

                          What is the host FQDN ?
       A FQDN consists of a short host name and the DNS domain name.
         If you choose www.foo.com, then the hostname will be www.
     If you choose staging.foo.com, then the hostname will be staging.

                         Currently: fqdn="lol.bar"
   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   Your answer will be saved on the host in:
   /etc/ansible/facts.d/yourlabs_fqdn.fact

   We won't ask you again for localhost, but you can see this again using
   forceask=fqdn or forceask=all or change it directly in the role's .fact file.

   Enter two single quotes for blank value as such: ''
   Press Enter (leave blank) to leave CURRENT value "lol.bar"
   <CTRL+C> <A>    To abort play
   Your input has to validate against: \w+\.[\w+.]+

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
