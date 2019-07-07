#!/usr/bin/python

from ansible.module_utils.basic import *

def main():
    import epdb; epdb.serve()
    module = AnsibleModule(argument_spec=dict(
        rolename=dict(
            required=True,
            type="str",
        ),
    ))
    response = {"hello": "world"}
    module.exit_json(changed=False, meta=response)


if __name__ == '__main__':
    main()
