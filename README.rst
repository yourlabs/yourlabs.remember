yourlabs.roleonce
=================

Ansible role that includes another role OAOO (Once And Only Once).

For example you want the next command to execute the docker/nginx/etc roles
once only by default:

    bigsudo github.com/your/repo @somehost dns=something

Then first add to your requirements.yml::

    - src: yourlabs.roleonce

And replace include_role with::

    - name: Put docker being a secure firewall
      include_role: name=yourlabs.roleonce
      vars:
        name: yourlabs.firewall

With this trick, your are going to be able to chain deep dependency graph
because bigsudo does a recursive requirements install. Every time
yourlabs.roleonce executes a role, it will write a fact with the role name.
Every time yourlabs.roleonce finds such a fact, it skips the role inclusion.

As such, you your first run will include all roles, but subsequent runs will
skip them, considering that you can upgrade them components explicitely by
calling their own roles.
